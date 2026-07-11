import os

from board_render import render_board_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")

if __name__ == "__main__":
    render_board_page(
        bank_path=os.path.join(DATA_DIR, "competitor_bank.json"),
        page_title="同行动态",
        page_subtitle="国际品牌 + 国产同行官网新闻/博客，找选题灵感和内容布局参考",
        active_nav="competitors",
        out_path=os.path.join(DOCS_DIR, "competitors.html"),
    )
