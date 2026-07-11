"""
Reddit专业榜单：这批候选已经经过 filter_candidates.py 的"专业对口"筛选，
剩下的都是有实质信息量的帖子。打分用真实互动量（点赞+2×评论），
但做对数压缩，避免个别爆款帖子分数畸高、把其他内容完全比下去。
"""
import math
import os
from datetime import datetime, timezone

from bank_utils import load_json, update_bank

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "reddit_candidates.json")
BANK_PATH = os.path.join(DATA_DIR, "reddit_bank.json")

TOP_N = 50
DECAY_RATE = 0.97
LOG_SCALE = 20


def score_fn(candidate):
    eng = candidate.get("engagement") or {}
    raw_engagement = (eng.get("score", 0) or 0) + 2 * (eng.get("comments", 0) or 0)
    return math.log1p(max(raw_engagement, 0)) * LOG_SCALE


def main():
    candidates = load_json(CANDIDATES_PATH, [])
    today = datetime.now(timezone.utc).date().isoformat()
    stats = update_bank(candidates, BANK_PATH, score_fn, TOP_N, DECAY_RATE, today)
    print(f"[完成] Reddit专业榜：共 {stats['total']} 条，在榜 {stats['active']} 条，"
          f"今天新增 {stats['new_today']} 条")


if __name__ == "__main__":
    main()
