"""
把当天新闻 + Trends 热度数据丢给 LLM，生成结构化的选题建议，
输出到 data/topics.json，供 render_dashboard.py 渲染成网页。

需要环境变量 OPENAI_API_KEY。
模型默认用 gpt-4o-mini（便宜、够用），可以用 OPENAI_MODEL 环境变量改。
"""
import json
import os
from datetime import datetime, timezone

from openai import OpenAI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
NEWS_PATH = os.path.join(DATA_DIR, "news.json")
TRENDS_PATH = os.path.join(DATA_DIR, "trends.json")
OUT_PATH = os.path.join(DATA_DIR, "topics.json")

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """你是一个专门服务B2B热泵出口企业的内容策略顾问。
你的读者是热泵采购商、经销商、工程公司，目标市场是欧洲、中东、亚洲。
你会收到：
1. 一批最近1-2天的热泵行业新闻标题和摘要（分欧洲/中东/亚洲三个区域）
2. 一批长尾关键词在Google Trends上的近7天热度走势分类（rising/flat/falling/unknown）

你的任务：为每个有新闻支撑的区域，生成1-3个内容选题建议。
选题要满足：
- 必须能关联到一条具体新闻（不能凭空编）
- 尽量关联到一个rising或flat（不是falling）的长尾词方向；如果现有种子词都不贴合，
  可以自己提出一个更贴合的长尾词方向，并标注 keyword_validated: false，
  提醒用户这个词还没有经过Google Trends/关键词规划师验证
- 说清楚建议写成什么形式：blog（技术博客）/ case_study（案例）/ whitepaper（白皮书）/ comparison（对比测评）
- 用一句话说明"为什么现在写这个有时效性价值"

只输出严格的JSON，不要任何多余文字，不要markdown代码块标记。格式：
{
  "generated_at": "ISO时间字符串",
  "topics": [
    {
      "region": "europe|middle_east|asia",
      "title": "选题标题（中文）",
      "trigger_news_title": "对应的新闻标题",
      "trigger_source": "新闻来源",
      "target_keyword": "建议的英文长尾词",
      "keyword_trend": "rising|flat|falling|unknown",
      "keyword_validated": true或false,
      "content_format": "blog|case_study|whitepaper|comparison",
      "why_now": "一句话说明时效性理由"
    }
  ]
}
如果某个区域今天没有值得写的新闻，就不要为那个区域强行编选题，输出的topics里可以少于3个区域都有。
"""


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    news = load_json(NEWS_PATH, [])
    trends = load_json(TRENDS_PATH, {})

    if not news:
        print("[提示] 今天没有抓到新闻，写入空 topics.json")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "topics": [],
            }, f, ensure_ascii=False, indent=2)
        return

    client = OpenAI()  # 从环境变量 OPENAI_API_KEY 读取

    user_content = json.dumps({
        "news": news,
        "keyword_trends": trends,
    }, ensure_ascii=False)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
    )

    raw = response.choices[0].message.content.strip()
    # 防止模型偶尔还是包了 markdown 代码块
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[错误] LLM 输出不是合法JSON: {e}")
        print(raw[:1000])
        raise

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(parsed, f, ensure_ascii=False, indent=2)

    print(f"[完成] 生成 {len(parsed.get('topics', []))} 个选题，写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
