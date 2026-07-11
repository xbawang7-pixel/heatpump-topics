"""
把 data/humor_pool.json 渲染成 docs/humor.html —— 这是被内容价值过滤
筛掉的Reddit纯玩笑/吐槽帖，跟正经的话题榜（Top50）分开展示，
纯粹是给你感受一下行业圈子里的真实氛围，不建议直接拿来当选题写。
"""
import html
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
POOL_PATH = os.path.join(DATA_DIR, "humor_pool.json")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "humor.html")


def esc(s):
    return html.escape(s or "")


ROW_TEMPLATE = """
<tr>
  <td class="title-cell"><a href="{link}" target="_blank" rel="noopener">{title}</a></td>
  <td class="muted">{source}</td>
  <td class="num">{upvotes}</td>
  <td class="num">{comments}</td>
  <td class="muted">{first_seen}</td>
</tr>
"""


def render_row(item):
    return ROW_TEMPLATE.format(
        link=esc(item.get("link", "")),
        title=esc(item.get("title", "")),
        source=esc(item.get("source_name", "")),
        upvotes=item.get("upvotes", 0),
        comments=item.get("comments", 0),
        first_seen=esc(item.get("first_seen", "")),
    )


def main():
    if os.path.exists(POOL_PATH):
        with open(POOL_PATH, "r", encoding="utf-8") as f:
            pool = json.load(f)
    else:
        pool = {}

    items = list(pool.values())
    items.sort(key=lambda i: i.get("upvotes", 0), reverse=True)

    rows_html = "".join(render_row(i) for i in items) if items else \
        '<tr><td colspan="5" class="empty">暂时还没有被过滤掉的内容，等Reddit抓取跑过之后就会有数据。</td></tr>'

    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>论坛趣味 / 吐槽帖</title>
<style>
  :root {{
    --bg: #ffffff; --surface: #fafaf9; --border: #eaeae7;
    --text: #1c1c1a; --text-muted: #8a8a85; --accent: #3c6e5c; --accent-soft: #3c6e5c14;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 3rem 1.5rem 5rem; background: var(--bg); color: var(--text);
    font-family: -apple-system, "PingFang SC", "Hiragino Sans GB", "Segoe UI", sans-serif;
    -webkit-font-smoothing: antialiased;
  }}
  .header {{
    max-width: 1080px; margin: 0 auto 1rem; display: flex; justify-content: space-between;
    align-items: flex-end; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--border);
    padding-bottom: 1.5rem;
  }}
  .header h1 {{ margin: 0; font-size: 26px; font-weight: 600; font-family: Georgia, "Songti SC", serif; }}
  .header .sub {{ color: var(--text-muted); font-size: 13px; margin-top: 6px; }}
  .header a.back {{
    font-size: 12.5px; color: var(--accent); text-decoration: none; border: 1px solid var(--border);
    padding: 7px 14px; border-radius: 999px; white-space: nowrap;
  }}
  .header a.back:hover {{ background: var(--accent-soft); }}
  .note {{
    max-width: 1080px; margin: 1.25rem auto 2rem; font-size: 12.5px; color: var(--text-muted);
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px;
  }}
  table {{ max-width: 1080px; margin: 0 auto; width: 100%; border-collapse: collapse; }}
  th {{
    text-align: left; font-size: 11px; color: var(--text-muted); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.06em; padding: 10px 12px; border-bottom: 1px solid var(--border);
  }}
  td {{ padding: 14px 12px; border-bottom: 1px solid var(--border); vertical-align: top; font-size: 13px; }}
  tr:hover td {{ background: var(--surface); }}
  td.num {{ font-family: "SF Mono", Menlo, monospace; color: var(--text-muted); }}
  td.muted {{ color: var(--text-muted); font-size: 12px; }}
  td.title-cell {{ max-width: 420px; }}
  a {{ color: var(--text); text-decoration: none; font-weight: 500; }}
  a:hover {{ color: var(--accent); }}
  .empty {{ text-align: center; color: var(--text-muted); padding: 3rem; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>论坛趣味 / 吐槽帖</h1>
      <div class="sub">更新时间：{generated_at_display}</div>
    </div>
    <a class="back" href="index.html">← 返回话题榜</a>
  </div>
  <div class="note">
    这些是Reddit上互动量很高、但被判定为"纯玩笑/吐槽/无实质信息量"而没有进入正经话题榜的帖子——
    不建议直接拿来当选题写，纯粹是给你感受一下行业圈子里的真实氛围。
  </div>
  <table>
    <thead>
      <tr><th>标题</th><th>来源板块</th><th>点赞</th><th>评论</th><th>首次发现</th></tr>
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

    print(f"[完成] 趣味帖页面已生成：{OUT_PATH}（累计 {len(items)} 条）")


if __name__ == "__main__":
    main()
