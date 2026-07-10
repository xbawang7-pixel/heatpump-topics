"""
把 data/topics.json 渲染成静态网页 docs/index.html
GitHub Pages 默认从 docs/ 目录发布，所以直接写这里就行。
"""
import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TOPICS_PATH = os.path.join(DATA_DIR, "topics.json")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "index.html")

REGION_LABELS = {
    "europe": "欧洲",
    "middle_east": "中东",
    "asia": "亚洲",
}

TREND_LABELS = {
    "rising": ("升温中", "#c9793d"),
    "flat": ("平稳", "#8b9296"),
    "falling": ("降温中", "#6b7280"),
    "unknown": ("待观察", "#6b7280"),
}

CARD_TEMPLATE = """
<div class="card">
  <div class="badges">
    <span class="badge source">{trigger_source}</span>
    <span class="badge trend" style="color:{trend_color};border-color:{trend_color}44">{trend_label}</span>
    {validated_badge}
  </div>
  <h3>{title}</h3>
  <p class="trigger">触发新闻：{trigger_news_title}</p>
  <div class="meta">
    <div class="kw">目标词：<code>{target_keyword}</code></div>
    <div class="row">
      <span>建议形式：{content_format_label}</span>
    </div>
    <p class="why">{why_now}</p>
  </div>
</div>
"""

FORMAT_LABELS = {
    "blog": "技术博客",
    "case_study": "案例研究",
    "whitepaper": "白皮书",
    "comparison": "对比测评",
}


def esc(s):
    return html.escape(s or "")


def render_card(topic):
    trend = topic.get("keyword_trend", "unknown")
    trend_label, trend_color = TREND_LABELS.get(trend, TREND_LABELS["unknown"])
    validated_badge = ""
    if not topic.get("keyword_validated", False):
        validated_badge = '<span class="badge unverified">待人工复核</span>'
    return CARD_TEMPLATE.format(
        trigger_source=esc(topic.get("trigger_source", "")),
        trend_color=trend_color,
        trend_label=trend_label,
        validated_badge=validated_badge,
        title=esc(topic.get("title", "")),
        trigger_news_title=esc(topic.get("trigger_news_title", "")),
        target_keyword=esc(topic.get("target_keyword", "")),
        content_format_label=FORMAT_LABELS.get(topic.get("content_format", ""), topic.get("content_format", "")),
        why_now=esc(topic.get("why_now", "")),
    )


def main():
    if os.path.exists(TOPICS_PATH):
        with open(TOPICS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"generated_at": None, "topics": []}

    topics = data.get("topics", [])
    by_region = {"europe": [], "middle_east": [], "asia": []}
    for t in topics:
        region = t.get("region")
        if region in by_region:
            by_region[region].append(t)

    columns_html = ""
    for region, label in REGION_LABELS.items():
        cards = by_region[region]
        if cards:
            cards_html = "".join(render_card(t) for t in cards)
        else:
            cards_html = '<p class="empty">今天没有值得写的新闻，明天再看。</p>'
        columns_html += f"""
        <div class="column">
          <div class="column-header">{label}</div>
          {cards_html}
        </div>
        """

    generated_at = data.get("generated_at")
    if generated_at:
        try:
            dt = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            generated_at_display = dt.strftime("%Y年%m月%d日 %H:%M UTC")
        except ValueError:
            generated_at_display = generated_at
    else:
        generated_at_display = "尚未生成"

    total = len(topics)
    unverified_count = sum(1 for t in topics if not t.get("keyword_validated", False))

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>热泵选题看板</title>
<style>
  :root {{
    --bg: #14181a;
    --panel: #1d2224;
    --border: #2a3134;
    --text: #edebe6;
    --text-muted: #8b9296;
    --copper: #c9793d;
    --teal: #4fa8a0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 2rem 1.5rem 4rem;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif;
  }}
  .header {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 500; }}
  .header .sub {{ color: var(--text-muted); font-size: 13px; margin-top: 4px; }}
  .stats {{
    max-width: 1100px;
    margin: 0 auto 1.5rem;
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
  }}
  .stat {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px 16px;
    min-width: 140px;
  }}
  .stat .label {{ font-size: 12px; color: var(--text-muted); }}
  .stat .value {{ font-size: 22px; font-weight: 500; margin-top: 2px; }}
  .grid {{
    max-width: 1100px;
    margin: 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
  }}
  .column-header {{
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 10px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }}
  .card {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 12px;
  }}
  .badges {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }}
  .badge {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 6px;
    border: 1px solid var(--border);
    color: var(--text-muted);
  }}
  .badge.trend {{ border-width: 1px; }}
  .badge.unverified {{ color: var(--copper); border-color: #c9793d44; }}
  .card h3 {{ font-size: 15px; font-weight: 500; margin: 0 0 6px; line-height: 1.4; }}
  .trigger {{ font-size: 12px; color: var(--text-muted); margin: 0 0 10px; }}
  .meta {{ border-top: 1px solid var(--border); padding-top: 8px; font-size: 12px; color: var(--text-muted); }}
  .kw code {{ color: var(--teal); font-family: "SF Mono", Consolas, monospace; }}
  .row {{ margin-top: 6px; }}
  .why {{ margin: 8px 0 0; color: var(--text); font-size: 12.5px; line-height: 1.5; }}
  .empty {{ color: var(--text-muted); font-size: 13px; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>今日热泵选题看板</h1>
      <div class="sub">生成时间：{generated_at_display}</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><div class="label">今日候选选题</div><div class="value">{total}</div></div>
    <div class="stat"><div class="label">待人工复核</div><div class="value">{unverified_count}</div></div>
  </div>
  <div class="grid">
    {columns_html}
  </div>
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 看板已生成：{OUT_PATH}")


if __name__ == "__main__":
    main()
