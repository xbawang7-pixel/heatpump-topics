import os

from board_render import render_board_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")

if __name__ == "__main__":
    render_board_page(
        bank_path=os.path.join(DATA_DIR, "news_bank.json"),
        page_title="热泵·空调新闻榜",
        page_subtitle="覆盖欧洲/中东/亚洲/非洲/南美的行业新闻信源",
        active_nav="news",
        out_path=os.path.join(DOCS_DIR, "news.html"),
    )
