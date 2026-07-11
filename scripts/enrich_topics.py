"""
给三个榜单（新闻/Reddit/同行动态）里"新上榜、还没被LLM标注过"的条目，补充：
- 建议的目标长尾关键词
- 建议的内容形式（blog/case_study/whitepaper/comparison）
- 一句话说明为什么值得写
- 区域和品类标签

每个榜单每次最多处理 MAX_PER_RUN 条（控制调用量和运行时间），
处理过的会标记 enriched=true，之后不会重复调用。

需要环境变量 GEMINI_API_KEY。
"""
import json
import os
from datetime import datetime, timezone

import google.generativeai as genai

MAX_PER_RUN = 15

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BANK_PATHS = [
    os.path.join(DATA_DIR, "news_bank.json"),
    os.path.join(DATA_DIR, "reddit_bank.json"),
    os.path.join(DATA_DIR, "competitor_bank.json"),
]
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
    "product_category": "heat_pump|air_conditioner|pool_heat_pump|both",
    "target_keyword": "建议的英文长尾关键词",
    "title_draft": "一个具体的英文blog标题草稿，要能直接拿去当文章标题用。
      优先框架成'回答一个真实买家会搜索的具体问题'，而不是'报道一条行业新闻'——
      即使原始素材是一条企业公关新闻（比如某公司换CEO、周年庆、获奖），
      也要往'买家真正关心的角度'去改写标题，比如别写成'XX公司庆祝成立120周年'，
      而是写成能回应'我该怎么判断一个热泵厂商靠不靠谱'这类买家决策问题的角度。
      如果原始素材本身就是纯人事变动/纯庆典新闻，实在扯不出买家角度，
      就如实标注is_grounded为false，不要硬编",
    "content_format": "blog|case_study|whitepaper|comparison|buyer_faq",
    "cluster": "cost_roi|pool_heating|cold_climate|district_heating_replacement|
      solar_integration|regulations_policy|installation_maintenance|market_trends|other",
    "is_grounded": "true或false（布尔值，不要加引号）——true表示这条内容能直接
      对应真实买家/终端用户会问的具体问题（价格、效果对比、维护成本、
      该选哪种型号、多久回本这类），false表示这本质是企业公关新闻/行业动态汇报
      （高管任命、周年庆典、协会年报这类），跟具体购买决策关系不大",
    "why_relevant": "一句话说明为什么这个话题值得写（中文）",
    "summary_cn": "用中文概述这篇文章/帖子在讲什么，大约100字左右，
      让不点开原文的人也能看懂具体内容（不是选题建议，是内容摘要本身）"
  }
]

判断region时：如果标题内容明显跟某个区域的政策/市场相关就用那个区域；
如果是通用技术话题，没有明显区域指向，就用 global。
判断product_category时：标题明确是热泵内容就用heat_pump，明确是空调/制冷/
chiller/district cooling这类就用air_conditioner，明确是泳池加热/游泳池热泵/
swimming pool heat pump/pool heating相关就用pool_heat_pump（这是一个独立
细分品类，泳池热泵相关内容不要归进普通heat_pump里），两者都涉及或者是通用
HVAC话题（比如噪音、能效标签、安装认证这种）就用both。

只输出JSON数组本身，不要markdown代码块标记，不要任何多余文字。

补充说明cluster这个字段——这是针对一个叫Airproz的商用热泵制造商设计的内容
集群体系（他们的业务线：商用热泵、空调、泳池加热、太阳能光伏集成、
区域供暖燃气替代项目），按下面这个对照表判断：
- cost_roi：价格、性价比、回本周期、运行成本对比相关
- pool_heating：泳池加热、游泳池热泵相关（专门归到这一类，不要跟heat_pump混）
- cold_climate：寒冷气候下的性能、结霜、低温效率相关
- district_heating_replacement：用热泵替代燃气锅炉/区域供暖相关
- solar_integration：太阳能光伏与热泵/空调集成相关
- regulations_policy：政策、补贴、法规、认证标准相关
- installation_maintenance：安装、维护、故障排查相关
- market_trends：市场数据、企业动态、行业趋势相关（不好归进上面几类的行业新闻）
- other：都不沾边的归这里
"""


def load_bank(bank_path):
    if not os.path.exists(bank_path):
        return {}
    with open(bank_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_bank(bank_path, bank):
    with open(bank_path, "w", encoding="utf-8") as f:
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


def enrich_one_bank(bank_path, model, pool, today):
    bank = load_bank(bank_path)
    if not bank:
        print(f"[提示] {os.path.basename(bank_path)} 是空的，跳过")
        return 0

    pending = [
        e for e in bank.values()
        if e["status"] == "active" and not e.get("enriched")
    ]
    pending.sort(key=lambda e: e["score"], reverse=True)
    batch = pending[:MAX_PER_RUN]

    if not batch:
        print(f"[提示] {os.path.basename(bank_path)} 没有需要补充信息的新条目")
        return 0

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
        print(f"[错误] {os.path.basename(bank_path)} LLM输出不是合法JSON: {e}")
        print(raw[:1000])
        return 0

    results_by_id = {r["id"]: r for r in results if "id" in r}

    updated = 0
    for entry in batch:
        r = results_by_id.get(entry["id"])
        if not r:
            continue
        entry["region"] = r.get("region") or entry.get("region")
        entry["product_category"] = r.get("product_category", "both")
        entry["target_keyword"] = r.get("target_keyword")
        entry["title_draft"] = r.get("title_draft")
        entry["content_format"] = r.get("content_format")
        entry["why_relevant"] = r.get("why_relevant")
        entry["is_grounded"] = bool(r.get("is_grounded", True))
        entry["cluster"] = r.get("cluster", "other")
        entry["summary_cn"] = r.get("summary_cn")
        entry["enriched"] = True
        add_to_keyword_pool(pool, entry, today)
        updated += 1

    save_bank(bank_path, bank)
    print(f"[完成] {os.path.basename(bank_path)}：补充了 {updated} 条")
    return updated


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("没有找到环境变量 GEMINI_API_KEY，请先设置")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"},
    )

    pool = load_keyword_pool()
    today = datetime.now(timezone.utc).date().isoformat()

    total_updated = 0
    for bank_path in BANK_PATHS:
        total_updated += enrich_one_bank(bank_path, model, pool, today)

    save_keyword_pool(pool)
    print(f"[完成] 三个榜单本次共补充 {total_updated} 条，累计关键词库共 {len(pool)} 条")


if __name__ == "__main__":
    main()
