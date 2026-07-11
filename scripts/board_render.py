"""
三个榜单页面（新闻/Reddit/同行动态）共用的渲染逻辑，样式统一走白色简约风格。
"""
import html
import json
import os
from datetime import datetime, timezone

REGION_LABELS = {
    "europe": "欧洲", "middle_east": "中东", "asia": "亚洲",
    "africa": "非洲", "south_america": "南美", "global": "通用",
    "international_brand": "国际品牌", "china_peer": "国产同行",
}
PRODUCT_LABELS = {
    "heat_pump": "热泵", "air_conditioner": "空调", "pool_heat_pump": "泳池加热", "both": "热泵/空调",
}
FORMAT_LABELS = {
    "blog": "技术博客", "case_study": "案例研究",
    "whitepaper": "白皮书", "comparison": "对比测评",
}


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
<tr data-region="{region_key}" data-product="{product_key}" data-id="{entry_id}" class="topic-row">
  <td class="rank">{rank:02d}</td>
  <td class="title-cell">
    <a href="{link}" target="_blank" rel="noopener">{title}</a>
    {title_draft_html}
    <div class="sub">
      <span class="tag source">{source_label}</span>
      <span class="tag region">{region_label}</span>
      <span class="tag product">{product_label}</span>
      {movement}
    </div>
  </td>
  <td class="summary">{summary_cn}</td>
  <td class="kw">{target_keyword}</td>
  <td class="fmt">{content_format}</td>
  <td class="score">{score}</td>
  <td class="used-col">
    <label class="used-checkbox">
      <input type="checkbox" class="mark-used" data-id="{entry_id}">
      <span>已用</span>
    </label>
  </td>
</tr>
"""


def render_row(entry):
    target_keyword = entry.get("target_keyword") or "待补充"
    content_format = FORMAT_LABELS.get(entry.get("content_format"), "待定")
    region_key = entry.get("region") or "global"
    region_label = REGION_LABELS.get(region_key, region_key or "待定")
    product_key = entry.get("product_category") or "both"
    product_label = PRODUCT_LABELS.get(product_key, "待定")
    source_label = esc(entry.get("source_name", ""))
    summary_cn = entry.get("summary_cn") or "（待补充，下次运行会自动生成）"
    title_draft = entry.get("title_draft")
    title_draft_html = (
        f'<div class="title-draft">💡 {esc(title_draft)}</div>' if title_draft else ""
    )
    return ROW_TEMPLATE.format(
        rank=entry.get("rank") or 0,
        region_key=esc(region_key),
        product_key=esc(product_key),
        entry_id=esc(entry.get("id", "")),
        link=esc(entry.get("link", "")),
        title=esc(entry.get("title", "")),
        title_draft_html=title_draft_html,
        source_label=source_label,
        region_label=esc(region_label),
        product_label=esc(product_label),
        movement=movement_badge(entry),
        summary_cn=esc(summary_cn),
        target_keyword=f"<code>{esc(target_keyword)}</code>",
        content_format=esc(content_format),
        score=round(entry.get("score", 0)),
    )


NAV_TEMPLATE = (
    '<a class="kwlink{active_home}" href="index.html">首页</a>'
    '<a class="kwlink{active_picks}" href="picks.html">精选清单</a>'
    '<a class="kwlink{active_clusters}" href="clusters.html">内容集群</a>'
    '<a class="kwlink{active_news}" href="news.html">新闻榜</a>'
    '<a class="kwlink{active_reddit}" href="reddit.html">Reddit专业榜</a>'
    '<a class="kwlink{active_competitors}" href="competitors.html">同行动态</a>'
    '<a class="kwlink" href="keywords.html">关键词库</a>'
    '<a class="kwlink" href="humor.html">趣味帖</a>'
)


def render_nav(active):
    kwargs = {f"active_{k}": (" active-nav" if k == active else "") for k in
              ("home", "picks", "clusters", "news", "reddit", "competitors")}
    return NAV_TEMPLATE.format(**kwargs)


BASE_CSS = """
:root {
  --bg: #ffffff; --surface: #fafaf9; --border: #eaeae7;
  --text: #1c1c1a; --text-muted: #8a8a85; --text-faint: #b6b6b1;
  --accent: #3c6e5c; --accent-soft: #3c6e5c14; --copper: #a8703f; --red: #b1584c;
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 3rem 1.5rem 5rem; background: var(--bg); color: var(--text);
  font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.header {
  max-width: 1080px; margin: 0 auto 1.25rem; display: flex; justify-content: space-between;
  align-items: flex-end; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--border);
  padding-bottom: 1.5rem;
}
.header h1 { margin: 0; font-size: 26px; font-weight: 600; font-family: Georgia, "Songti SC", serif; }
.header .sub { color: var(--text-muted); font-size: 13px; margin-top: 6px; }
.nav { max-width: 1080px; margin: 0 auto 2rem; display: flex; gap: 8px; flex-wrap: wrap; }
.kwlink {
  font-size: 12.5px; color: var(--accent); text-decoration: none; border: 1px solid var(--border);
  padding: 7px 14px; border-radius: 999px; white-space: nowrap;
}
.kwlink:hover, .kwlink.active-nav { background: var(--accent-soft); }
.stats { max-width: 1080px; margin: 0 auto 2rem; display: flex; gap: 14px; flex-wrap: wrap; }
.stat { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 14px 20px; min-width: 150px; }
.stat .label { font-size: 11.5px; color: var(--text-muted); }
.stat .value { font-size: 24px; font-weight: 600; margin-top: 4px; font-family: Georgia, serif; }
.filters { max-width: 1080px; margin: 0 auto 10px; display: flex; gap: 8px; flex-wrap: wrap; }
.filter-btn, .pfilter-btn {
  font-size: 12.5px; padding: 6px 15px; border-radius: 999px; border: 1px solid var(--border);
  background: var(--bg); color: var(--text-muted); cursor: pointer; font-family: inherit;
}
.filter-btn:hover, .pfilter-btn:hover { border-color: var(--accent); color: var(--text); }
.filter-btn.active { background: var(--accent); color: #fff; border-color: var(--accent); font-weight: 500; }
.pfilter-btn.active { background: var(--copper); color: #fff; border-color: var(--copper); font-weight: 500; }
table { max-width: 1080px; margin: 1.5rem auto 0; width: 100%; border-collapse: collapse; }
th {
  text-align: left; font-size: 11px; color: var(--text-faint); font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.06em; padding: 10px 12px; border-bottom: 1px solid var(--border);
}
td { padding: 16px 12px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13.5px; line-height: 1.55; }
tr:hover td { background: var(--surface); }
td.rank { color: var(--text-faint); font-family: Georgia, serif; font-size: 15px; font-style: italic; width: 36px; padding-top: 17px; }
td.score { font-family: "SF Mono", Menlo, monospace; text-align: right; width: 56px; color: var(--text-muted); }
td.summary { color: var(--text-muted); max-width: 260px; font-size: 12.5px; }
td.kw code { color: var(--accent); font-family: "SF Mono", Menlo, monospace; font-size: 12px; background: var(--accent-soft); padding: 2px 6px; border-radius: 5px; }
td.fmt { color: var(--text-muted); white-space: nowrap; font-size: 12.5px; }
td.title-cell { max-width: 260px; }
a { color: var(--text); text-decoration: none; font-weight: 500; }
a:hover { color: var(--accent); }
.sub { margin-top: 6px; display: flex; gap: 6px; flex-wrap: wrap; }
.tag { font-size: 10px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--border); color: var(--text-muted); font-weight: 500; }
.tag.new { color: var(--copper); border-color: #a8703f40; background: #a8703f0c; }
.tag.up { color: var(--accent); border-color: #3c6e5c40; background: var(--accent-soft); }
.tag.down { color: var(--red); border-color: #b1584c40; background: #b1584c0c; }
.empty { text-align: center; color: var(--text-muted); padding: 3rem; }
.title-draft {
  margin-top: 6px; font-size: 12.5px; color: var(--text); background: var(--accent-soft);
  border-radius: 8px; padding: 6px 10px; line-height: 1.5;
}
td.used-col { width: 50px; text-align: center; }
.used-checkbox { display: flex; flex-direction: column; align-items: center; gap: 2px; font-size: 10px; color: var(--text-muted); cursor: pointer; }
.used-checkbox input { cursor: pointer; }
tr.used-row { opacity: 0.4; }
tr.used-row td.title-cell a { text-decoration: line-through; }
#toggle-used-btn.active { background: var(--text); color: #fff; border-color: var(--text); }
"""


def render_board_page(bank_path, page_title, page_subtitle, active_nav, out_path):
    if os.path.exists(bank_path):
        with open(bank_path, "r", encoding="utf-8") as f:
            bank = json.load(f)
    else:
        bank = {}

    active = [e for e in bank.values() if e.get("status") == "active"]
    active.sort(key=lambda e: e.get("rank") or 9999)

    new_today = sum(1 for e in active if e.get("previous_rank") is None)
    pending_enrich = sum(1 for e in active if not e.get("enriched"))

    rows_html = "".join(render_row(e) for e in active) if active else \
        '<tr><td colspan="7" class="empty">这个榜单还是空的，等下次抓取跑过之后就会有数据。</td></tr>'

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
<title>{esc(page_title)}</title>
<style>{BASE_CSS}</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>{esc(page_title)}</h1>
      <div class="sub">更新时间：{generated_at_display} · {esc(page_subtitle)}</div>
    </div>
  </div>
  <div class="nav">
    {render_nav(active_nav)}
  </div>
  <div class="stats">
    <div class="stat"><div class="label">在榜条目</div><div class="value">{len(active)}</div></div>
    <div class="stat"><div class="label">今日新上榜</div><div class="value">{new_today}</div></div>
    <div class="stat"><div class="label">待补充关键词</div><div class="value">{pending_enrich}</div></div>
  </div>
  <div class="filters">
    {filter_buttons}
  </div>
  <div class="filters">
    {product_buttons}
  </div>
  <div class="filters">
    <button class="filter-btn" id="toggle-used-btn" data-showused="false">隐藏"已用"话题</button>
  </div>
  <table>
    <thead>
      <tr><th>排名</th><th>话题</th><th>内容摘要</th><th>目标长尾词</th><th>建议形式</th><th>热度</th><th>状态</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <script>
    var currentRegion = 'all';
    var currentProduct = 'all';
    var hideUsed = false;
    var STORAGE_KEY = 'heatpump_topics_used_v1';

    function getUsedSet() {{
      try {{
        return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]'));
      }} catch (e) {{ return new Set(); }}
    }}
    function saveUsedSet(set) {{
      localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
    }}

    function applyFilters() {{
      var usedSet = getUsedSet();
      document.querySelectorAll('tbody tr').forEach(function(row) {{
        var regionOk = (currentRegion === 'all' || row.dataset.region === currentRegion);
        var productOk = (currentProduct === 'all' || row.dataset.product === currentProduct);
        var isUsed = usedSet.has(row.dataset.id);
        var usedOk = !(hideUsed && isUsed);
        row.style.display = (regionOk && productOk && usedOk) ? '' : 'none';
      }});
    }}

    function refreshUsedUI() {{
      var usedSet = getUsedSet();
      document.querySelectorAll('.mark-used').forEach(function(cb) {{
        var isUsed = usedSet.has(cb.dataset.id);
        cb.checked = isUsed;
        var row = cb.closest('tr');
        if (row) {{ row.classList.toggle('used-row', isUsed); }}
      }});
    }}

    document.querySelectorAll('.mark-used').forEach(function(cb) {{
      cb.addEventListener('change', function() {{
        var usedSet = getUsedSet();
        if (cb.checked) {{ usedSet.add(cb.dataset.id); }} else {{ usedSet.delete(cb.dataset.id); }}
        saveUsedSet(usedSet);
        refreshUsedUI();
        applyFilters();
      }});
    }});

    var toggleBtn = document.getElementById('toggle-used-btn');
    if (toggleBtn) {{
      toggleBtn.addEventListener('click', function() {{
        hideUsed = !hideUsed;
        toggleBtn.classList.toggle('active', hideUsed);
        toggleBtn.textContent = hideUsed ? '显示"已用"话题' : '隐藏"已用"话题';
        applyFilters();
      }});
    }}

    document.querySelectorAll('.filter-btn[data-filter]').forEach(function(btn) {{
      btn.addEventListener('click', function() {{
        document.querySelectorAll('.filter-btn[data-filter]').forEach(function(b) {{ b.classList.remove('active'); }});
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

    refreshUsedUI();
  </script>
</body>
</html>
"""

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] {page_title} 已生成：{out_path}（在榜 {len(active)} 条）")
