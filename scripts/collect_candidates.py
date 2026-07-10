"""
从两类来源收集"候选话题"：
1. 新闻RSS(欧洲/中东/亚洲区域信源) —— 时效性信号
2. Reddit 相关板块的"过去一年最热帖"(按点赞+评论排序) —— 真实讨论热度信号

输出到 data/candidates.json，供 update_topic_bank.py 合并进持久化话题库。

注意：Reddit的匿名/官方接口都被证明不适合这个场景（匿名接口拦截云IP，
官方OAuth注册流程容易被网络环境卡住），改用 Apify 平台上的第三方Reddit抓取器
（harshmaur/reddit-scraper），按结果付费，不需要注册Reddit应用。
需要环境变量 APIFY_API_TOKEN，去 https://console.apify.com 免费注册获取
（不用绑卡，每月5美元免费额度）。

成本控制：这个抓取器按$2/1000条结果收费。24个板块 × 25条 ≈ 1.2美元/次，
如果每天跑会超出免费额度，所以Reddit这部分改成"每周跑一次"（由外部环境变量
RUN_REDDIT 控制，workflow里只在每周一设置为true），一个月约4次，
控制在5美元免费额度内。
"""
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone

import feedparser
import requests
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.yaml")
DATA_DIR = os.path.join(ROOT, "data")
OUT_PATH = os.path.join(DATA_DIR, "candidates.json")

NEWS_LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "168"))  # 默认7天
REDDIT_LIMIT = 25  # 每个板块抓多少条

APIFY_ACTOR = "harshmaur~reddit-scraper"  # Apify Store上的actor标识（~代替/）
APIFY_RUN_URL = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"


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

    if os.environ.get("RUN_REDDIT", "").lower() != "true":
        print("[信息] 今天不是每周Reddit抓取日，跳过（省Apify额度）")
        return candidates

    subs = config.get("reddit_subreddits", []) or []
    if not subs:
        return candidates

    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        print("[警告] 没有配置 APIFY_API_TOKEN，跳过Reddit抓取")
        return candidates

    subreddit_names = [s.get("slug") for s in subs if s.get("slug")]
    region_by_slug = {s.get("slug"): s.get("region") for s in subs}
    name_by_slug = {s.get("slug"): s.get("name", f"r/{s.get('slug')}") for s in subs}

    # 注意：这个字段名是根据Apify这类Reddit actor的常见输入规范写的
    # (subreddits / sort / timeFilter / maxItems)。如果实际调用报"输入格式错误"，
    # 去 https://apify.com/harshmaur/reddit-scraper/input-schema 核对一下
    # 真实字段名，照着改这里的payload就行，不是代码逻辑问题。
    payload = {
        "subreddits": subreddit_names,
        "sort": "top",
        "timeFilter": "year",
        "maxItems": REDDIT_LIMIT * len(subreddit_names),
        "maxPostsPerSource": REDDIT_LIMIT,
        "skipComments": True,
    }

    try:
        resp = requests.post(
            APIFY_RUN_URL,
            params={"token": api_token},
            json=payload,
            timeout=280,  # Apify同步接口最多等5分钟，留一点余量
        )
        if resp.status_code != 200:
            print(f"[警告] Apify Reddit抓取失败: HTTP {resp.status_code} - {resp.text[:300]}")
            return candidates
        items = resp.json()
    except Exception as e:
        print(f"[警告] Apify Reddit抓取异常: {e}")
        return candidates

    for item in items:
        if item.get("dataType") and item.get("dataType") != "post":
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        link = item.get("url") or ""
        slug = (item.get("parsedCommunityName") or item.get("communityName", "").lstrip("r/") or "").strip()
        candidates.append({
            "id": make_id(link, title),
            "title": title,
            "link": link,
            "summary": (item.get("body") or "")[:400],
            "source_type": "reddit",
            "source_name": name_by_slug.get(slug, f"r/{slug}" if slug else "Reddit"),
            "region": region_by_slug.get(slug),
            "engagement": {
                "score": item.get("upVotes", 0) or 0,
                "comments": item.get("numberOfComments", 0) or 0,
            },
            "published": item.get("createdAt"),
        })

    print(f"[完成] Apify Reddit抓取: 共 {len(candidates)} 条")
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
