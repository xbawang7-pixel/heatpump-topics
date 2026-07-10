"""
给话题库里"新上榜、还没被LLM标注过"的条目，补充：
- 建议的目标长尾关键词
- 建议的内容形式（blog/case_study/whitepaper/comparison）
- 一句话说明为什么值得写
- 如果是Reddit这种没有区域标签的候选，让LLM帮忙猜一个最相关的区域

每次只处理最多 MAX_PER_RUN 条（控制调用量和运行时间），
处理过的会标记 enriched=true，之后不会重复调用，
这样即使话题库有几十上百条历史记录，每天的API开销也是可控的。

需要环境变量 GEMINI_API_KEY。
"""
import json
import os
from datetime import datetime, timezone

import google.generativeai as genai

MAX_PER_RUN = 10

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BANK_PATH = os.path.join(DATA_DIR, "topic_bank.json")
KEYWORD_POOL_PATH = os.path.join(DATA_DIR, "keyword_pool.json")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

SYSTEM_PROMPT = """你是一个专门服务B2B暖通(HVAC)出口企业的内容策略顾问，
覆盖两条产品线：热泵(heat pump) 和 空调(air conditioner)。
读者是采购商、经销商、工程公司，目标市场是欧洲、中东、亚洲、非洲、南美。

重要背景：不同区域的产品重心不一样——
- 欧洲：以热泵为主（补贴、能效法规、寒冷气候性能是核心议题）
- 中东：以空调/制冷为主，热泵话题相对少（当地更关心高温工况、电费、区域制冷、
  T3认证这类空调议题，判断相关性时不要用"热泵"的标准去卡空调话题）
- 亚洲/非洲/南美：热泵和空调都可能是重点，视具体新闻内容判断

你会收到一批"候选话题"，每个话题来自新闻或者Reddit热帖（部分Reddit话题已经
带有region标签，那是我们根据板块地区预先标注的，如果标签明显不合理可以纠正）。
请为每一条补充以下字段，返回严格的JSON数组，顺序和输入一致，不要漏项：

[
  {
    "id": "原样返回输入里的id",
    "region": "europe|middle_east|asia|africa|south_america|global",
    "product_category": "heat_pump|air_conditioner|both",
    "target_keyword": "建议的英文长尾关键词",
    "content_format": "blog|case_study|whitepaper|comparison",
    "why_relevant": "一句话说明为什么这个话题值得写（中文）"
  }
]

判断region时：如果标题内容明显跟某个区域的政策/市场相关就用那个区域；
如果是通用技术话题，没有明显区域指向，就用 global。
判断product_category时：标题明确是热泵内容就用heat_pump，明确是空调/制冷/
chiller/district cooling这类就用air_conditioner，两者都涉及或者是通用HVAC话题
（比如噪音、能效标签、安装认证这种）就用both。

只输出JSON数组本身，不要markdown代码块标记，不要任何多余文字。
"""


def load_bank():
    if not os.path.exists(BANK_PATH):
        return {}
    with open(BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bank(bank):
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)


def load_keyword_pool():
    if not os.path.exists(KEYWORD_POOL_PATH):
        return {}
    with open(KEYWORD_POOL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_keyword_pool(pool):
    with open(KEYWORD_POOL_PATH, "w", encoding="utf-8") as f:
        json.dump(pool, f, ensure_ascii=False, indent=2)


def add_to_keyword_pool(pool, entry, today):
    """把一个刚生成的目标长尾词记录进持久化关键词库。
    这个库不会因为对应话题掉出Top50就被清空——
    专门用来解决"话题下榜、关键词研究成果也跟着丢"的问题。"""
    kw = (entry.get("target_keyword") or "").strip()
    if not kw:
        return
    key = kw.lower()
    if key in pool:
        record = pool[key]
        record["times_seen"] = record.get("times_seen", 1) + 1
        record["last_seen"] = today
    else:
        pool[key] = {
            "keyword": kw,
            "region": entry.get("region"),
            "product_category": entry.get("product_category"),
            "content_format": entry.get("content_format"),
            "first_seen": today,
            "last_seen": today,
            "times_seen": 1,
            "sample_title": entry.get("title"),
            "sample_link": entry.get("link"),
            "keyword_validated": False,  # 每周人工用Google Ads核实后可以手动改成true
        }


def main():
    bank = load_bank()
    if not bank:
        print("[提示] 话题库为空，跳过")
        return

    pending = [
        e for e in bank.values()
        if e["status"] == "active" and not e.get("enriched")
    ]
    # 分数高的优先处理
    pending.sort(key=lambda e: e["score"], reverse=True)
    batch = pending[:MAX_PER_RUN]

    if not batch:
        print("[提示] 没有需要补充信息的新话题，跳过")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("没有找到环境变量 GEMINI_API_KEY，请先设置")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"},
    )

    payload = [
        {"id": e["id"], "title": e["title"], "source_name": e["source_name"],
         "source_type": e["source_type"], "summary": e.get("summary", "")}
        for e in batch
    ]

    response = model.generate_content(json.dumps(payload, ensure_ascii=False))
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]

    try:
        results = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[错误] LLM 输出不是合法JSON: {e}")
        print(raw[:1000])
        raise

    results_by_id = {r["id"]: r for r in results if "id" in r}

    pool = load_keyword_pool()
    today = datetime.now(timezone.utc).date().isoformat()

    updated = 0
    for entry in batch:
        r = results_by_id.get(entry["id"])
        if not r:
            continue
        entry["region"] = r.get("region") or entry.get("region")
        entry["product_category"] = r.get("product_category", "both")
        entry["target_keyword"] = r.get("target_keyword")
        entry["content_format"] = r.get("content_format")
        entry["why_relevant"] = r.get("why_relevant")
        entry["enriched"] = True
        add_to_keyword_pool(pool, entry, today)
        updated += 1

    save_bank(bank)
    save_keyword_pool(pool)
    print(f"[完成] 本次补充了 {updated} 条话题的关键词/形式建议，"
          f"累计关键词库共 {len(pool)} 条")


if __name__ == "__main__":
    main()
