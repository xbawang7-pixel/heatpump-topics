"""
从两类来源收集"候选话题"：
1. 新闻RSS(欧洲/中东/亚洲区域信源) —— 时效性信号
2. Reddit 相关板块的"过去一年最热帖"(按点赞+评论排序) —— 真实讨论热度信号

输出到 data/candidates.json，供 update_topic_bank.py 合并进持久化话题库。

注意：Reddit的公开JSON接口不需要账号/key，但必须带一个像样的User-Agent，
否则容易被限流(429)。这里做了基本的重试和限流保护。
"""
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.yaml")
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "candidates.json")

NEWS_LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "168"))  # 默认7天
REDDIT_HEADERS = {"User-Agent": "heatpump-topics-bot/1.0 (by /u/heatpump_research)"}
REDDIT_LIMIT = 25  # 每个板块抓多少条


def make_id(link, title):
    raw = (link or title or "").strip().lower()
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_entry_time(entry):
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None


def collect_news(config):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    candidates = []
    regions = config.get("regions", {}) or {}
    for region, feeds in regions.items():
        feeds = feeds or []
        region_count = 0
        for feed in feeds:
            rss_url = feed.get("rss")
            source_name = feed.get("name", rss_url)
            if not rss_url:
                continue
            try:
                parsed = feedparser.parse(rss_url)
            except Exception as e:
                print(f"[警告] 新闻源解析失败 {source_name}: {e}")
                continue

            for entry in parsed.entries:
                pub_time = parse_entry_time(entry)
                if pub_time and pub_time < cutoff:
                    continue
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                if not title:
                    continue
                candidates.append({
                    "id": make_id(link, title),
                    "title": title,
                    "link": link,
                    "summary": (entry.get("summary", "") or "")[:400],
                    "source_type": "news",
                    "source_name": source_name,
                    "region": region,
                    "engagement": None,
                    "published": pub_time.isoformat() if pub_time else None,
                })
                region_count += 1
        print(f"[信息] 新闻-{region}: 本次抓到 {region_count} 条")
    return candidates


def collect_reddit(config):
    candidates = []
    subs = config.get("reddit_subreddits", []) or []
    for sub in subs:
        slug = sub.get("slug")
        name = sub.get("name", f"r/{slug}")
        region_hint = sub.get("region")  # 可能为 None，代表全球通用板块
        if not slug:
            continue
        url = f"https://www.reddit.com/r/{slug}/top/.json?t=year&limit={REDDIT_LIMIT}"
        try:
            resp = requests.get(url, headers=REDDIT_HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"[警告] Reddit {name} 请求失败: HTTP {resp.status_code}")
                time.sleep(3)
                continue
            payload = resp.json()
        except Exception as e:
            print(f"[警告] Reddit {name} 请求异常: {e}")
            time.sleep(3)
            continue

        posts = payload.get("data", {}).get("children", [])
        for post in posts:
            p = post.get("data", {})
            title = (p.get("title") or "").strip()
            if not title:
                continue
            link = "https://www.reddit.com" + p.get("permalink", "")
            created = p.get("created_utc")
            published = (
                datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
                if created else None
            )
            candidates.append({
                "id": make_id(link, title),
                "title": title,
                "link": link,
                "summary": (p.get("selftext") or "")[:400],
                "source_type": "reddit",
                "source_name": name,
                "region": region_hint,  # 有配置就用配置的，没有就留空交给LLM判断
                "engagement": {
                    "score": p.get("score", 0),
                    "comments": p.get("num_comments", 0),
                },
                "published": published,
            })
        print(f"[信息] Reddit-{name}: 抓到 {len(posts)} 条")
        time.sleep(2)  # 避免请求过快被限流
    return candidates


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    news_candidates = collect_news(config)
    reddit_candidates = collect_reddit(config)
    all_candidates = news_candidates + reddit_candidates

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, ensure_ascii=False, indent=2)

    print(f"[完成] 新闻 {len(news_candidates)} 条 + Reddit {len(reddit_candidates)} 条 "
          f"= 共 {len(all_candidates)} 条候选，写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
