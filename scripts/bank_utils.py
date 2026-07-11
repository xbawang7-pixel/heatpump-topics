"""
三个独立榜单（新闻/Reddit/同行动态）共用的"合并候选进持久化榜单并排名"逻辑。
每个榜单是独立的 bank 文件，互不打分比较——这是这次重构的核心：
之前把新闻和Reddit硬凑在一个分数体系里比较，本质上不是一类东西，
拆开之后各自按自己的逻辑排序更合理。
"""
import json
import os


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_bank(candidates, bank_path, score_fn, top_n, decay_rate, today):
    """
    通用榜单更新逻辑：
    - candidates: 本次抓到的候选列表
    - bank_path: 持久化榜单文件路径
    - score_fn: 接收一个candidate，返回它的原始分数
    - top_n: 榜单展示多少条
    - decay_rate: 每天没被重新提及，分数打几折
    - today: 今天的日期字符串
    """
    bank = load_json(bank_path, {})
    seen_today_ids = set()

    for c in candidates:
        cid = c["id"]
        seen_today_ids.add(cid)
        raw = score_fn(c)

        if cid in bank:
            entry = bank[cid]
            entry["reappear_count"] = min(entry.get("reappear_count", 1) + 1, 5)
            entry["score"] = max(entry["score"], raw) + entry["reappear_count"] * 2
            entry["last_seen"] = today
            entry["title"] = c["title"]
            entry["link"] = c["link"]
            if c.get("region"):
                entry["region"] = c["region"]
        else:
            entry = dict(c)
            entry.update({
                "score": raw,
                "reappear_count": 1,
                "first_seen": today,
                "last_seen": today,
                "enriched": False,  # 即使summary_cn已经有了，target_keyword等
                                     # 字段还没有，仍然要走enrich流程补全
                "product_category": None,
                "target_keyword": None,
                "title_draft": None,
                "content_format": None,
                "why_relevant": None,
                "is_grounded": None,
                "cluster": None,
                "summary_cn": c.get("summary_cn"),  # 保留候选自带的摘要（如果有），
                                                      # enrich跑过之后会用更完整的版本覆盖
                "keyword_validated": False,
                "previous_rank": None,
                "rank": None,
                "status": "active",
            })
            bank[cid] = entry

    for cid, entry in bank.items():
        if cid not in seen_today_ids:
            entry["score"] = round(entry["score"] * decay_rate, 2)

    ranked = sorted(bank.values(), key=lambda e: e["score"], reverse=True)
    for idx, entry in enumerate(ranked, start=1):
        entry["previous_rank"] = entry.get("rank")
        if idx <= top_n:
            entry["rank"] = idx
            entry["status"] = "active"
        else:
            entry["rank"] = None
            entry["status"] = "retired"

    save_json(bank_path, bank)

    active_count = sum(1 for e in bank.values() if e["status"] == "active")
    new_count = sum(1 for e in bank.values() if e["first_seen"] == today)
    return {"total": len(bank), "active": active_count, "new_today": new_count}
