import os

from board_render import render_board_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")

if __name__ == "__main__":
    render_board_page(
        bank_path=os.path.join(DATA_DIR, "reddit_bank.json"),
        page_title="Reddit专业话题榜",
        page_subtitle="已过滤掉纯玩笑/吐槽帖，只保留专业对口的讨论（互动量对数缩放打分）",
        active_nav="reddit",
        out_path=os.path.join(DOCS_DIR, "reddit.html"),
    )
