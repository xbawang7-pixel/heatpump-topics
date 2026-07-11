"""
精选清单：从三个榜单的Top条目里，挑出一批"兼顾多样性"的推荐——
不是单纯按分数取前几名（那样容易全被同一个来源/同一个地区占满），
是尽量让区域、来源都覆盖到，帮你直接决定"这几天写这几篇"，
不用自己从三个榜单里各挑一遍。
"""
import json
import os
from datetime import datetime, timezone

from board_render import (
    esc, REGION_LABELS, PRODUCT_LABELS, FORMAT_LABELS, render_nav, BASE_CSS,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
OUT_PATH = os.path.join(DOCS_DIR, "picks.html")

BANK_FILES = ["news_bank.json", "reddit_bank.json", "competitor_bank.json"]
PICKS_PER_BOARD = {
    "news_bank.json": 3,
    "reddit_bank.json": 3,
    "competitor_bank.json": 2,
}


def load_bank(bank_file):
    path = os.path.join(DATA_DIR, bank_file)
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    active = [e for e in bank.values() if e.get("status") == "active"]
    active.sort(key=lambda e: e.get("rank") or 9999)
    return active


def pick_diverse(entries, n):
    """尽量让region不重复，优先选没出现过的区域，选够n条为止。
    另外优先选"接地气"的内容（is_grounded=true，对应真实买家关心的问题），
    避免精选清单里全是企业公关新闻这种"新闻性强但不实用"的内容。"""
    grounded = [e for e in entries if e.get("is_grounded") is True]
    ungrounded = [e for e in entries if e.get("is_grounded") is not True]
    # 先在"接地气"的池子里做多样性挑选，池子不够大再从剩下的里面补
    ordered = grounded + ungrounded

    picked = []
    seen_regions = set()
    for e in ordered:
        if len(picked) >= n:
            break
        region = e.get("region") or "global"
        if region not in seen_regions:
            picked.append(e)
            seen_regions.add(region)
    if len(picked) < n:
        picked_ids = {e["id"] for e in picked}
        for e in ordered:
            if len(picked) >= n:
                break
            if e["id"] not in picked_ids:
                picked.append(e)
    return picked


CARD_TEMPLATE = """
<a class="pick-card" href="{link}" target="_blank" rel="noopener">
  <div class="pick-source">{source_badge} · {region_label} {grounded_badge}</div>
  <div class="pick-title-draft">{title_draft}</div>
  <div class="pick-original-title">原标题：{title}</div>
  <div class="pick-summary">{summary_cn}</div>
  <div class="pick-footer">
    <code>{target_keyword}</code>
    <span class="pick-format">{content_format}</span>
  </div>
</a>
"""

SOURCE_BADGES = {"news": "新闻榜", "reddit": "Reddit专业榜", "competitor": "同行动态"}


def render_card(entry):
    title_draft = entry.get("title_draft") or entry.get("title", "")
    grounded_badge = '<span class="grounded-tag">🎯 买家关心</span>' if entry.get("is_grounded") else ""
    return CARD_TEMPLATE.format(
        link=esc(entry.get("link", "")),
        source_badge=SOURCE_BADGES.get(entry.get("source_type"), entry.get("source_type", "")),
        region_label=esc(REGION_LABELS.get(entry.get("region"), entry.get("region") or "通用")),
        grounded_badge=grounded_badge,
        title_draft=esc(title_draft),
        title=esc(entry.get("title", "")),
        summary_cn=esc(entry.get("summary_cn") or "（暂无摘要）"),
        target_keyword=esc(entry.get("target_keyword") or "待补充"),
        content_format=esc(FORMAT_LABELS.get(entry.get("content_format"), "待定")),
    )


def main():
    all_picks = []
    for bank_file in BANK_FILES:
        entries = load_bank(bank_file)
        enriched_entries = [e for e in entries if e.get("enriched")]
        n = PICKS_PER_BOARD.get(bank_file, 3)
        all_picks.extend(pick_diverse(enriched_entries, n))

    generated_at_display = datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M UTC")
    cards_html = "".join(render_card(e) for e in all_picks) if all_picks else \
        '<div class="empty">还没有足够的数据生成精选清单，等榜单积累几天再来看。</div>'

    html_out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>精选清单</title>
<style>{BASE_CSS}
  .note {{
    max-width: 1080px; margin: 1rem auto 2rem; font-size: 16px; color: var(--text-muted);
    background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 12px 16px;
  }}
  .picks-grid {{
    max-width: 1080px; margin: 0 auto; display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px;
  }}
  .pick-card {{
    display: block; background: var(--surface); border: 1px solid var(--border);
    border-radius: 14px; padding: 20px; text-decoration: none; transition: border-color 0.15s;
  }}
  .pick-card:hover {{ border-color: var(--accent); }}
  .pick-source {{ font-size: 14px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.04em; }}
  .pick-title-draft {{ font-size: 21px; font-weight: 600; color: var(--text); margin-top: 8px; line-height: 1.5; font-family: Georgia, serif; }}
  .pick-original-title {{ font-size: 14.5px; color: var(--text-faint); margin-top: 8px; }}
  .pick-summary {{ font-size: 16px; color: var(--text-muted); margin-top: 8px; line-height: 1.65; }}
  .pick-footer {{ margin-top: 14px; display: flex; justify-content: space-between; align-items: center; gap: 8px; }}
  .pick-footer code {{ color: var(--accent); font-family: "SF Mono", Menlo, monospace; font-size: 14.5px; background: var(--accent-soft); padding: 4px 9px; border-radius: 5px; }}
  .pick-format {{ font-size: 14.5px; color: var(--text-muted); white-space: nowrap; }}
  .grounded-tag {{ font-size: 14px; color: var(--accent); font-weight: 600; }}
</style>
</head>
<body>
  <div class="header">
    <div>
      <h1>今日精选清单</h1>
      <div class="sub">更新时间：{generated_at_display} · 从三个榜单里挑出兼顾多样性的推荐，直接拿去当选题</div>
    </div>
  </div>
  <div class="nav">
    {render_nav("home")}
  </div>
  <div class="note">
    这里只从已经生成过标题草稿的条目里选，尽量让不同区域、不同来源都覆盖到。
    带💡的标题草稿可以直接拿去改一改当文章标题用。
  </div>
  <div class="picks-grid">
    {cards_html}
  </div>
</body>
</html>
"""

    os.makedirs(DOCS_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write(html_out)

    print(f"[完成] 精选清单已生成：{OUT_PATH}（共 {len(all_picks)} 条）")


if __name__ == "__main__":
    main()
