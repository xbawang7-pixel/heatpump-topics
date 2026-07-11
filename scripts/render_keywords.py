"""
把 data/keyword_pool.json 渲染成 docs/keywords.html，
这是一个持久累积的长尾词库，不会因为对应话题掉出Top50就消失。
"""
import html
import json
import os
from datetime import datetime, timezone

from board_render import render_nav, BASE_CSS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
POOL_PATH = os.path.join(DATA_DIR, "keyword_pool.json")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "keywords.html")

REGION_LABELS = {
    "europe": "欧洲", "middle_east": "中东", "asia": "亚洲",
    "africa": "非洲", "south_america": "南美", "global": "通用",
}
FORMAT_LABELS = {
    "blog": "技术博客", "case_study": "案例研究",
    "whitepaper": "白皮书", "comparison": "对比测评",
}
PRODUCT_LABELS = {
    "heat_pump": "热泵", "air_conditioner": "空调", "both": "热泵/空调",
}


def esc(s):
    return html.escape(s or "")


ROW_TEMPLATE = """
<tr>
  <td><code>{keyword}</code>{validated_badge}</td>
  <td>{region}</td>
  <td>{product}</td>
  <td>{content_format}</td>
  <td class="num">{times_seen}</td>
  <td class="muted">{first_seen}</td>
  <td class="muted"><a href="{link}" target="_blank" rel="noopener">{title}</a></td>
</tr>
"""


def render_row(kw):
    validated_badge = ' <span class="tag ok">已核实</span>' if kw.get("keyword_validated") else ""
    return ROW_TEMPLATE.format(
        keyword=esc(kw.get("keyword", "")),
        validated_badge=validated_badge,
        region=esc(REGION_LABELS.get(kw.get("region"), "待定")),
        product=esc(PRODUCT_LABELS.get(kw.get("product_category"), "待定")),
        content_format=esc(FORMAT_LABELS.get(kw.get("content_format"), "待定")),
        times_seen=kw.get("times_seen", 1),
        first_seen=esc(kw.get("first_seen", "")),
        link=esc(kw.get("sample_link", "")),
        title=esc((kw.get("sample_title") or "")[:60]),
    )


def main():
    if os.path.exists(POOL_PATH):
        with open(POOL_PATH, "r", encoding="utf-8") as f:
            pool = json.load(f)
    else:
        pool = {}

    keywords = list(pool.values())
    # 按"重复出现次数"排序，越多次被生成，说明这个方向越持续被验证有价值
    keywords.sort(key=lambda k: (k.get("times_seen", 1), k.get("first_seen", "")), reverse=True)

    validated_count = sum(1 for k in keywords if k.get("keyword_validated"))
    rows_html = "".join(render_row(k) for k in keywords) if keywords else \
        '<tr><td colspan="6" class="empty">关键词库还是空的，等第一次运行完成后就会有数据。</td></tr>'

    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>长尾关键词库</title>
<style>{BASE_CSS}
  td.num {{ font-family: "SF Mono", Menlo, monospace; color: var(--text-muted); }}
  td.muted {{ color: var(--text-muted); font-size: 13.5px; max-width: 260px; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>累计长尾关键词库</h1>
      <div class="sub">更新时间：{generated_at_display} · 每次话题被LLM标注过就会记录在这里，永久保留，不随话题掉出榜单而丢失</div>
    </div>
  </div>
  <div class="nav">
    {render_nav("home")}
  </div>
  <div class="stats">
    <div class="stat"><div class="label">累计关键词</div><div class="value">{len(keywords)}</div></div>
    <div class="stat"><div class="label">已人工核实</div><div class="value">{validated_count}</div></div>
  </div>
  <table>
    <thead>
      <tr><th>长尾关键词</th><th>区域</th><th>品类</th><th>建议形式</th><th>重复出现次数</th><th>首次出现</th><th>来源话题</th></tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 关键词库页面已生成：{OUT_PATH}（累计 {len(keywords)} 条）")


if __name__ == "__main__":
    main()
