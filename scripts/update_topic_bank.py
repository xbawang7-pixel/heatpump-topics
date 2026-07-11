"""
把 data/candidates.json 里今天新抓到的候选，合并进持久化的话题库
data/topic_bank.json（这个文件每天会被提交回仓库，不会被清空，
所以能做到"近一年热度滚动排名，每天迭代"）。

打分逻辑：
- Reddit帖子：score = log(点赞数 + 2×评论数) × 缩放系数
  （用对数压缩，避免爆款帖子几千分把新闻类完全碾压，参考量级：
   200互动 ≈ 106分，6000互动 ≈ 177分，跟新闻基础分20分在同一数量级里比较，
   而不是几百倍的差距）
- 新闻类：给一个基础分，每多出现一次（比如同一事件被多个源报道，
  或者延续好几天还在被提及）就加一次基础分，代表"持续被关注"
- 每天没有再出现的旧话题，分数按天衰减（DECAY_RATE），避免老话题赖在榜首不走
- 重新出现的老话题，会在原有(衰减后)的分数基础上再叠加一次新分数，
  相当于"热度回升"

最终按分数排序取Top N，但保留一个"新闻最低配额"：如果纯按分数排会导致
新闻类一条都进不去（Reddit互动量天然更大），就强制置换进一部分新闻，
保证信息来源多样性，不是Reddit一言堂。
"""
import json
import math
import os
from datetime import datetime, timezone

TOP_N = 50
DECAY_RATE = 0.97          # 每天没被重新提及，分数乘这个系数
NEWS_BASE_SCORE = 20        # 新闻类候选每次出现的基础分
REAPPEAR_BONUS_CAP = 5      # 反复出现的加成次数上限，避免无限累加
REDDIT_LOG_SCALE = 20        # Reddit对数打分的缩放系数
MIN_NEWS_SLOTS = 12          # Top50里至少保留给新闻类的名额

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.json")
BANK_PATH = os.path.join(DATA_DIR, "topic_bank.json")


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def raw_score_for(candidate):
    if candidate["source_type"] == "reddit":
        eng = candidate.get("engagement") or {}
        raw_engagement = (eng.get("score", 0) or 0) + 2 * (eng.get("comments", 0) or 0)
        return math.log1p(max(raw_engagement, 0)) * REDDIT_LOG_SCALE
    return NEWS_BASE_SCORE


def main():
    candidates = load_json(CANDIDATES_PATH, [])
    bank = load_json(BANK_PATH, {})  # dict: id -> entry

    today = datetime.now(timezone.utc).date().isoformat()
    seen_today_ids = set()

    for c in candidates:
        cid = c["id"]
        seen_today_ids.add(cid)
        raw = raw_score_for(c)

        if cid in bank:
            entry = bank[cid]
            entry["reappear_count"] = min(entry.get("reappear_count", 1) + 1, REAPPEAR_BONUS_CAP)
            # 分数取"衰减后的旧分数"和"这次新观察到的分数"里较大的一个，
            # 再加一点反复出现的加成
            decayed_old = entry["score"]  # 衰减已经在下面统一对所有条目做过
            entry["score"] = max(decayed_old, raw) + entry["reappear_count"] * 2
            entry["last_seen"] = today
            entry["title"] = c["title"]  # 标题以最新一次抓到的为准
            entry["link"] = c["link"]
            if c.get("region"):
                entry["region"] = c["region"]
        else:
            bank[cid] = {
                "id": cid,
                "title": c["title"],
                "link": c["link"],
                "summary": c.get("summary", ""),
                "source_type": c["source_type"],
                "source_name": c["source_name"],
                "region": c.get("region"),
                "product_category": None,
                "score": raw,
                "reappear_count": 1,
                "first_seen": today,
                "last_seen": today,
                "enriched": False,
                "target_keyword": None,
                "content_format": None,
                "why_relevant": None,
                "summary_cn": None,
                "keyword_trend": None,
                "keyword_validated": False,
                "previous_rank": None,
                "rank": None,
                "status": "active",
            }

    # 对今天没出现的条目做衰减
    for cid, entry in bank.items():
        if cid not in seen_today_ids:
            entry["score"] = round(entry["score"] * DECAY_RATE, 2)

    # 先按分数整体排序
    ranked = sorted(bank.values(), key=lambda e: e["score"], reverse=True)

    # 保底逻辑：如果纯按分数选出的Top N里，新闻类数量不够 MIN_NEWS_SLOTS，
    # 就把分数最高的几条新闻类"换"进来，替换掉Top N里排名最靠后的非新闻条目，
    # 保证信息来源多样性，不会被Reddit互动量完全挤压掉
    baseline_top = ranked[:TOP_N]
    rest = ranked[TOP_N:]

    news_in_top = [e for e in baseline_top if e["source_type"] == "news"]
    news_shortfall = MIN_NEWS_SLOTS - len(news_in_top)

    if news_shortfall > 0:
        # 从榜外找分数最高的新闻类候选，按需补进来
        outside_news = [e for e in rest if e["source_type"] == "news"]
        outside_news.sort(key=lambda e: e["score"], reverse=True)
        promote = outside_news[:news_shortfall]

        if promote:
            promote_ids = {e["id"] for e in promote}
            # 从baseline里踢掉排名最靠后的非新闻条目，腾出等量名额
            non_news_in_top = [e for e in baseline_top if e["source_type"] != "news"]
            non_news_in_top.sort(key=lambda e: e["score"])  # 分数最低的排前面，优先被替换
            demote = non_news_in_top[:len(promote)]
            demote_ids = {e["id"] for e in demote}

            baseline_top = [e for e in baseline_top if e["id"] not in demote_ids] + promote
            # 重新按分数排一次序，保证展示顺序还是按热度从高到低
            baseline_top.sort(key=lambda e: e["score"], reverse=True)

    final_top_ids = {e["id"] for e in baseline_top}

    for entry in bank.values():
        entry["previous_rank"] = entry.get("rank")
        if entry["id"] in final_top_ids:
            entry["status"] = "active"
        else:
            entry["rank"] = None
            entry["status"] = "retired"

    for idx, entry in enumerate(
        sorted(baseline_top, key=lambda e: e["score"], reverse=True), start=1
    ):
        bank[entry["id"]]["rank"] = idx

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(BANK_PATH, "w", encoding="utf-8") as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

    active_count = sum(1 for e in bank.values() if e["status"] == "active")
    new_count = sum(1 for e in bank.values() if e["first_seen"] == today)
    print(f"[完成] 话题库共 {len(bank)} 条，其中Top{TOP_N}在榜 {active_count} 条，"
          f"今天新增候选 {new_count} 条")


if __name__ == "__main__":
    main()
