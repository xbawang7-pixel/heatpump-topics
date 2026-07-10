"""
抓取 config/sources.yaml 里配置的 RSS 信源，
只保留最近 N 小时内发布的文章，输出到 data/news.json
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import feedparser
import yaml

LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "36"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.yaml")
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "news.json")


def parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def fetch_region(region_name, feeds):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    items = []
    for feed in feeds:
        rss_url = feed.get("rss")
        source_name = feed.get("name", rss_url)
        if not rss_url:
            continue
        try:
            parsed = feedparser.parse(rss_url)
        except Exception as e:
            print(f"[警告] 解析失败 {source_name} ({rss_url}): {e}", file=sys.stderr)
            continue

        if parsed.bozo and not parsed.entries:
            print(f"[警告] {source_name} 抓不到内容，检查 RSS 地址是否还有效", file=sys.stderr)
            continue

        for entry in parsed.entries:
            pub_time = parse_entry_time(entry)
            # 抓不到时间的也保留，避免漏掉更新不规范的源，交给后面 LLM 自行判断时效性
            if pub_time and pub_time < cutoff:
                continue
            items.append({
                "region": region_name,
                "source": source_name,
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "summary": (entry.get("summary", "") or "")[:500],
                "published": pub_time.isoformat() if pub_time else None,
            })
    return items


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    all_items = []
    for region in ("europe", "middle_east", "asia"):
        feeds = config.get(region, []) or []
        region_items = fetch_region(region, feeds)
        print(f"[信息] {region}: 抓到 {len(region_items)} 条")
        all_items.extend(region_items)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)

    print(f"[完成] 共 {len(all_items)} 条新闻，写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
