"""
按内容集群分组展示三个榜单里的话题——不是孤立的一条条选题，
是按"商用热泵性价比""泳池加热""寒冷气候性能"这种主题分组，
帮助系统性地布局一组文章、建立某个细分领域的权威度，而不是打游击。

这套集群体系是专门针对Airproz的业务线设计的，如果以后产品线变了，
去 scripts/enrich_topics.py 里改CLUSTER相关的prompt就行。
"""
import json
import os
from datetime import datetime, timezone

from board_render import esc, REGION_LABELS, FORMAT_LABELS, render_nav, BASE_CSS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "clusters.html")

BANK_FILES = ["news_bank.json", "reddit_bank.json", "competitor_bank.json"]

CLUSTER_LABELS = {
    "cost_roi": "💰 性价比 / 回本周期",
    "pool_heating": "🏊 泳池加热",
    "cold_climate": "❄️ 寒冷气候性能",
    "district_heating_replacement": "🔥 区域供暖 / 燃气替代",
    "solar_integration": "☀️ 太阳能集成",
    "regulations_policy": "📋 政策法规",
    "installation_maintenance": "🔧 安装维护",
    "market_trends": "📈 市场动态",
    "other": "其他",
}
CLUSTER_ORDER = list(CLUSTER_LABELS.keys())


def load_all_entries():
    entries = []
    for bank_file in BANK_FILES:
        path = os.path.join(DATA_DIR, bank_file)
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            bank = json.load(f)
        for e in bank.values():
            if e.get("status") == "active" and e.get("enriched"):
                entries.append(e)
    return entries


ITEM_TEMPLATE = """
<a class="cluster-item" href="{link}" target="_blank" rel="noopener">
  <div class="cluster-item-title">{title_draft}{grounded_badge}</div>
  <div class="cluster-item-meta">{region_label} · <code>{target_keyword}</code></div>
</a>
"""


def render_item(entry):
    title_draft = entry.get("title_draft") or entry.get("title", "")
    grounded_badge = ' <span class="grounded-tag">🎯</span>' if entry.get("is_grounded") else ""
    return ITEM_TEMPLATE.format(
        link=esc(entry.get("link", "")),
        title_draft=esc(title_draft),
        grounded_badge=grounded_badge,
        region_label=esc(REGION_LABELS.get(entry.get("region"), entry.get("region") or "通用")),
        target_keyword=esc(entry.get("target_keyword") or "待补充"),
    )


def main():
    entries = load_all_entries()
    grouped = {c: [] for c in CLUSTER_ORDER}
    for e in entries:
        cluster = e.get("cluster") or "other"
        if cluster not in grouped:
            cluster = "other"
        grouped[cluster].append(e)

    for c in grouped:
        grouped[c].sort(key=lambda e: e.get("score", 0), reverse=True)

    sections_html = ""
    for cluster in CLUSTER_ORDER:
        items = grouped[cluster]
        if not items:
            continue
        items_html = "".join(render_item(e) for e in items[:12])
        sections_html += f"""
        <div class="cluster-section">
          <div class="cluster-header">
            <span class="cluster-title">{esc(CLUSTER_LABELS[cluster])}</span>
            <span class="cluster-count">{len(items)} 条</span>
          </div>
          <div class="cluster-items">
            {items_html}
          </div>
        </div>
        """

    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>内容集群</title>
<style>{BASE_CSS}
  .note {{
    max-width: 1080px; margin: 1rem auto 2rem; font-size: 16px; color: var(--text-muted);
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px;
  }}
  .cluster-section {{ max-width: 1080px; margin: 0 auto 2rem; }}
  .cluster-header {{
    display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 1px solid var(--border); padding-bottom: 8px; margin-bottom: 12px;
  }}
  .cluster-title {{ font-size: 22px; font-weight: 600; font-family: Georgia, "Songti SC", serif; }}
  .cluster-count {{ font-size: 15px; color: var(--text-muted); }}
  .cluster-items {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px;
  }}
  .cluster-item {{
    display: block; background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 12px 14px; text-decoration: none; transition: border-color 0.15s;
  }}
  .cluster-item:hover {{ border-color: var(--accent); }}
  .cluster-item-title {{ font-size: 17px; color: var(--text); line-height: 1.55; }}
  .cluster-item-meta {{ font-size: 14px; color: var(--text-muted); margin-top: 6px; }}
  .cluster-item-meta code {{ color: var(--accent); font-family: "SF Mono", Menlo, monospace; }}
  .grounded-tag {{ font-size: 14px; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>内容集群</h1>
      <div class="sub">更新时间：{generated_at_display} · 按主题分组，帮你系统性布局一组文章，而不是打游击</div>
    </div>
  </div>
  <div class="nav">
    {render_nav("home")}
  </div>
  <div class="note">
    每个集群最多展示12条（按热度排序）。带🎯的是"接地气"标记（对应真实买家决策问题）。
    集群体系是针对Airproz业务线设计的（商用热泵、泳池加热、太阳能集成这些），
    以后产品线变化了随时可以调整。
  </div>
  {sections_html if sections_html else '<div class="empty">还没有足够的已补充数据，等榜单积累几天再来看。</div>'}
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 内容集群页面已生成：{OUT_PATH}")


if __name__ == "__main__":
    main()
