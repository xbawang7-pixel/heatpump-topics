"""
同行动态榜单：竞品官网新闻/博客，跟新闻榜逻辑一样简单——按新鲜度/持续出现排序，
不用互动量打分（企业官网本来就没有点赞数这种东西）。
"""
import os
from datetime import datetime, timezone

from bank_utils import load_json, update_bank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "competitor_candidates.json")
BANK_PATH = os.path.join(DATA_DIR, "competitor_bank.json")

TOP_N = 30
DECAY_RATE = 0.97
BASE_SCORE = 20


def score_fn(candidate):
    return BASE_SCORE


def main():
    candidates = load_json(CANDIDATES_PATH, [])
    today = datetime.now(timezone.utc).date().isoformat()
    stats = update_bank(candidates, BANK_PATH, score_fn, TOP_N, DECAY_RATE, today)
    print(f"[完成] 同行动态榜：共 {stats['total']} 条，在榜 {stats['active']} 条，"
          f"今天新增 {stats['new_today']} 条")


if __name__ == "__main__":
    main()
