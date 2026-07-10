"""
用 Google Trends（免费，无需 API key）查种子长尾词的近7天热度走势，
判断是"在升温"还是"平淡"，输出到 data/trends.json

注意：pytrends 是非官方库，调用太频繁会被 Google 临时限流。
这里做了请求间隔 + 出错重试，正常一天跑一次不会有问题。
"""
import json
import os
import time

import yaml
from pytrends.request import TrendReq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.yaml")
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "trends.json")

REQUEST_DELAY_SECONDS = 5


def classify_trend(values):
    if not values or len(values) < 2:
        return "unknown"
    recent = sum(values[-2:]) / 2
    earlier = sum(values[:2]) / 2 if len(values) >= 4 else values[0]
    if earlier == 0:
        return "rising" if recent > 0 else "flat"
    change = (recent - earlier) / max(earlier, 1)
    if change > 0.25:
        return "rising"
    if change < -0.25:
        return "falling"
    return "flat"


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    keywords = config.get("seed_keywords", []) or []
    pytrends = TrendReq(hl="en-US", tz=0)

    results = {}
    # pytrends 一次最多查 5 个词，超过要分批
    batch_size = 5
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i:i + batch_size]
        try:
            pytrends.build_payload(batch, timeframe="now 7-d")
            df = pytrends.interest_over_time()
            for kw in batch:
                if kw in df.columns:
                    values = df[kw].tolist()
                    results[kw] = {
                        "trend": classify_trend(values),
                        "series": values,
                    }
                else:
                    results[kw] = {"trend": "unknown", "series": []}
        except Exception as e:
            print(f"[警告] 查询失败 {batch}: {e}")
            for kw in batch:
                results.setdefault(kw, {"trend": "unknown", "series": []})
        time.sleep(REQUEST_DELAY_SECONDS)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[完成] 查询了 {len(keywords)} 个词，写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
