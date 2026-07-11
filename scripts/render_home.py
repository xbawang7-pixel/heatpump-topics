"""
首页：不再是一个合并榜单，是三个独立榜单的导航中枢，
外加各自的摘要统计，一眼看出哪个榜单有多少新内容。
"""
import json
import os
from datetime import datetime, timezone

from board_render import render_nav, BASE_CSS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "index.html")

BOARDS = [
    ("新闻榜", "news_bank.json", "news.html", "欧洲/中东/亚洲/非洲/南美行业新闻"),
    ("Reddit专业榜", "reddit_bank.json", "reddit.html", "过滤后的专业对口讨论"),
    ("同行动态", "competitor_bank.json", "competitors.html", "国际品牌 + 国产同行动态"),
]


def load_stats(bank_file):
    path = os.path.join(DATA_DIR, bank_file)
    if not os.path.exists(path):
        return {"active": 0, "new_today": 0}
    with open(path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    active = [e for e in bank.values() if e.get("status") == "active"]
    new_today = sum(1 for e in active if e.get("previous_rank") is None)
    return {"active": len(active), "new_today": new_today}


def main():
    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")

    cards_html = ""
    for title, bank_file, link, desc in BOARDS:
        stats = load_stats(bank_file)
        cards_html += f"""
        <a class="board-card" href="{link}">
          <div class="board-card-title">{title}</div>
          <div class="board-card-desc">{desc}</div>
          <div class="board-card-stats">
            <span>在榜 {stats['active']}</span>
            <span class="new">今日新增 {stats['new_today']}</span>
          </div>
        </a>
        """

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>热泵·空调内容灵感中心</title>
<style>{BASE_CSS}
  .boards {{
    max-width: 1080px; margin: 2rem auto 0; display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px;
  }}
  .board-card {{
    display: block; background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 22px; text-decoration: none; transition: border-color 0.15s;
  }}
  .board-card:hover {{ border-color: var(--accent); }}
  .board-card-title {{ font-size: 17px; font-weight: 600; color: var(--text); font-family: Georgia, "Songti SC", serif; }}
  .board-card-desc {{ font-size: 12.5px; color: var(--text-muted); margin-top: 6px; }}
  .board-card-stats {{ margin-top: 16px; display: flex; gap: 12px; font-size: 12px; color: var(--text-muted); }}
  .board-card-stats .new {{ color: var(--accent); }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>热泵 · 空调内容灵感中心</h1>
      <div class="sub">更新时间：{generated_at_display} · 三个独立榜单，各自按自己的逻辑排序，不混在一起打分</div>
    </div>
  </div>
  <div class="nav">
    {render_nav("home")}
  </div>
  <div class="boards">
    {cards_html}
  </div>
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 首页已生成：{OUT_PATH}")


if __name__ == "__main__":
    main()
