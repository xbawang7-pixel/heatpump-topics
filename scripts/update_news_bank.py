"""
新闻榜单：不需要跟Reddit比分数，按"出现次数+新鲜度"简单排序即可——
同一事件被多个信源报道，或者持续好几天还在被提及，说明确实是热点。
"""
import os
from datetime import datetime, timezone

from bank_utils import load_json, update_bank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "news_candidates.json")
BANK_PATH = os.path.join(DATA_DIR, "news_bank.json")

TOP_N = 50
DECAY_RATE = 0.97
BASE_SCORE = 20


def score_fn(candidate):
    return BASE_SCORE


def main():
    candidates = load_json(CANDIDATES_PATH, [])
    today = datetime.now(timezone.utc).date().isoformat()
    stats = update_bank(candidates, BANK_PATH, score_fn, TOP_N, DECAY_RATE, today)
    print(f"[完成] 新闻榜：共 {stats['total']} 条，在榜 {stats['active']} 条，"
          f"今天新增 {stats['new_today']} 条")


if __name__ == "__main__":
    main()
