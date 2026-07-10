"""
把 data/topic_bank.json 里 status=active 的条目（按分数Top50）
渲染成一个榜单网页 docs/index.html，每天更新。
"""
import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
BANK_PATH = os.path.join(DATA_DIR, "topic_bank.json")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "index.html")

REGION_LABELS = {
    "europe": "欧洲", "middle_east": "中东", "asia": "亚洲",
    "africa": "非洲", "south_america": "南美", "global": "通用",
}
PRODUCT_LABELS = {
    "heat_pump": "热泵", "air_conditioner": "空调", "both": "热泵/空调",
}
FORMAT_LABELS = {
    "blog": "技术博客", "case_study": "案例研究",
    "whitepaper": "白皮书", "comparison": "对比测评",
}
SOURCE_TYPE_LABELS = {"news": "新闻", "reddit": "Reddit热帖"}


def esc(s):
    return html.escape(s or "")


def movement_badge(entry):
    prev = entry.get("previous_rank")
    cur = entry.get("rank")
    if prev is None:
        return '<span class="tag new">NEW</span>'
    if cur is None:
        return ""
    diff = prev - cur
    if diff > 0:
        return f'<span class="tag up">↑{diff}</span>'
    if diff < 0:
        return f'<span class="tag down">↓{abs(diff)}</span>'
    return '<span class="tag flat">–</span>'


ROW_TEMPLATE = """
<tr data-region="{region_key}" data-product="{product_key}">
  <td class="rank">#{rank}</td>
  <td class="title-cell">
    <a href="{link}" target="_blank" rel="noopener">{title}</a>
    <div class="sub">
      <span class="tag source">{source_label}</span>
      <span class="tag region">{region_label}</span>
      <span class="tag product">{product_label}</span>
      {movement}
    </div>
  </td>
  <td class="kw">{target_keyword}</td>
  <td class="fmt">{content_format}</td>
  <td class="score">{score}</td>
</tr>
"""


def render_row(entry):
    target_keyword = entry.get("target_keyword") or "（待补充，下次运行会自动生成）"
    content_format = FORMAT_LABELS.get(entry.get("content_format"), "待定")
    region_key = entry.get("region") or "global"
    region_label = REGION_LABELS.get(region_key, "待定")
    product_key = entry.get("product_category") or "both"
    product_label = PRODUCT_LABELS.get(product_key, "待定")
    source_label = SOURCE_TYPE_LABELS.get(entry.get("source_type"), entry.get("source_type", ""))
    return ROW_TEMPLATE.format(
        rank=entry.get("rank"),
        region_key=esc(region_key),
        product_key=esc(product_key),
        link=esc(entry.get("link", "")),
        title=esc(entry.get("title", "")),
        source_label=esc(source_label),
        region_label=esc(region_label),
        product_label=esc(product_label),
        movement=movement_badge(entry),
        target_keyword=f"<code>{esc(target_keyword)}</code>",
        content_format=esc(content_format),
        score=round(entry.get("score", 0)),
    )


def main():
    if os.path.exists(BANK_PATH):
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            bank = json.load(f)
    else:
        bank = {}

    active = [e for e in bank.values() if e.get("status") == "active"]
    active.sort(key=lambda e: e.get("rank") or 9999)

    new_today = sum(1 for e in active if e.get("previous_rank") is None)
    pending_enrich = sum(1 for e in active if not e.get("enriched"))

    rows_html = "".join(render_row(e) for e in active) if active else \
        '<tr><td colspan="5" class="empty">话题库还是空的，等第一次运行完成后就会有数据。</td></tr>'

    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")

    active_regions = sorted(set((e.get("region") or "global") for e in active))
    filter_buttons = '<button class="filter-btn active" data-filter="all">全部</button>' + "".join(
        f'<button class="filter-btn" data-filter="{esc(r)}">{esc(REGION_LABELS.get(r, r))}</button>'
        for r in active_regions
    )
    active_products = sorted(set((e.get("product_category") or "both") for e in active))
    product_buttons = '<button class="pfilter-btn active" data-pfilter="all">全部品类</button>' + "".join(
        f'<button class="pfilter-btn" data-pfilter="{esc(p)}">{esc(PRODUCT_LABELS.get(p, p))}</button>'
        for p in active_products
    )

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>热泵+空调话题热度榜 Top 50</title>
<style>
  :root {{
    --bg: #14181a; --panel: #1d2224; --border: #2a3134;
    --text: #edebe6; --text-muted: #8b9296;
    --copper: #c9793d; --teal: #4fa8a0; --red: #b5544a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 2rem 1.5rem 4rem; background: var(--bg); color: var(--text);
    font-family: -apple-system, "PingFang SC", "Segoe UI", sans-serif;
  }}
  .header {{ max-width: 980px; margin: 0 auto 1.25rem; display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; }}
  .header h1 {{ margin: 0; font-size: 22px; font-weight: 500; }}
  .header .sub {{ color: var(--text-muted); font-size: 13px; margin-top: 4px; }}
  .header a.kwlink {{ font-size: 12.5px; color: var(--teal); text-decoration: none; border: 1px solid #4fa8a055; padding: 6px 12px; border-radius: 8px; white-space: nowrap; }}
  .header a.kwlink:hover {{ background: #4fa8a015; }}
  .stats {{ max-width: 980px; margin: 0 auto 1rem; display: flex; gap: 12px; flex-wrap: wrap; }}
  .stat {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px; min-width: 140px; }}
  .stat .label {{ font-size: 12px; color: var(--text-muted); }}
  .stat .value {{ font-size: 22px; font-weight: 500; margin-top: 2px; }}
  .filters {{ max-width: 980px; margin: 0 auto 1.25rem; display: flex; gap: 8px; flex-wrap: wrap; }}
  .filter-btn {{
    font-size: 12.5px; padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border);
    background: var(--panel); color: var(--text-muted); cursor: pointer; font-family: inherit;
  }}
  .filter-btn:hover {{ color: var(--text); }}
  .filter-btn.active {{ background: var(--teal); color: #0c1211; border-color: var(--teal); font-weight: 500; }}
  .pfilter-btn {{
    font-size: 12.5px; padding: 6px 14px; border-radius: 999px; border: 1px solid var(--border);
    background: var(--panel); color: var(--text-muted); cursor: pointer; font-family: inherit;
  }}
  .pfilter-btn:hover {{ color: var(--text); }}
  .pfilter-btn.active {{ background: var(--copper); color: #1a0f08; border-color: var(--copper); font-weight: 500; }}
  table {{ max-width: 980px; margin: 0 auto; width: 100%; border-collapse: collapse; }}
  th {{
    text-align: left; font-size: 12px; color: var(--text-muted); font-weight: 500;
    text-transform: uppercase; letter-spacing: 0.04em; padding: 8px 10px; border-bottom: 1px solid var(--border);
  }}
  td {{ padding: 10px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13.5px; }}
  td.rank {{ color: var(--text-muted); font-family: "SF Mono", Consolas, monospace; width: 40px; }}
  td.score {{ font-family: "SF Mono", Consolas, monospace; text-align: right; width: 60px; }}
  td.kw code {{ color: var(--teal); font-family: "SF Mono", Consolas, monospace; font-size: 12.5px; }}
  td.fmt {{ color: var(--text-muted); white-space: nowrap; }}
  a {{ color: var(--text); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .sub {{ margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap; }}
  .tag {{ font-size: 10.5px; padding: 1px 7px; border-radius: 6px; border: 1px solid var(--border); color: var(--text-muted); }}
  .tag.new {{ color: var(--copper); border-color: #c9793d55; }}
  .tag.up {{ color: var(--teal); border-color: #4fa8a055; }}
  .tag.down {{ color: var(--red); border-color: #b5544a55; }}
  .empty {{ text-align: center; color: var(--text-muted); padding: 2rem; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>热泵+空调话题热度榜 · Top 50</h1>
      <div class="sub">更新时间：{generated_at_display} · 覆盖欧洲/中东/亚洲/非洲/南美新闻 + Reddit近一年热帖</div>
    </div>
    <a class="kwlink" href="keywords.html">查看累计长尾关键词库 →</a>
  </div>
  <div class="stats">
    <div class="stat"><div class="label">在榜话题</div><div class="value">{len(active)}</div></div>
    <div class="stat"><div class="label">今日新上榜</div><div class="value">{new_today}</div></div>
    <div class="stat"><div class="label">待补充关键词</div><div class="value">{pending_enrich}</div></div>
  </div>
  <div class="filters">
    {filter_buttons}
  </div>
  <div class="filters">
    {product_buttons}
  </div>
  <table>
    <thead>
      <tr><th>排名</th><th>话题</th><th>目标长尾词</th><th>建议形式</th><th>热度分</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <script>
    var currentRegion = 'all';
    var currentProduct = 'all';
    function applyFilters() {{
      document.querySelectorAll('tbody tr').forEach(function(row) {{
        var regionOk = (currentRegion === 'all' || row.dataset.region === currentRegion);
        var productOk = (currentProduct === 'all' || row.dataset.product === currentProduct);
        row.style.display = (regionOk && productOk) ? '' : 'none';
      }});
    }}
    document.querySelectorAll('.filter-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        currentRegion = btn.dataset.filter;
        applyFilters();
      }});
    }});
    document.querySelectorAll('.pfilter-btn').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.pfilter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
        btn.classList.add('active');
        currentProduct = btn.dataset.pfilter;
        applyFilters();
      }});
    }});
  </script>
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 榜单已生成：{OUT_PATH}（在榜 {len(active)} 条）")


if __name__ == "__main__":
    main()
