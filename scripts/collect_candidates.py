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
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "sources.yaml")
DATA_DIR = os.path.join(ROOT, "data")

NEWS_LOOKBACK_HOURS = int(os.environ.get("LOOKBACK_HOURS", "168"))  # 默认7天
REDDIT_LIMIT = 35  # 每个板块抓多少条（从25调到35，捞更多内容；
                    # 注意这个数字跟Apify账单成正比，涨了大概40%的调用量，
                    # 如果发现某个月额度紧张，把这个数字调回去就行）

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


def scrape_html_blog(url, min_title_len=15, max_title_len=140, url_must_contain=None):
    """通用HTML博客列表页爬取——没有RSS的网站用这个兜底。
    逻辑很朴素：抓页面里所有链接，标题长度在合理范围内（太短像导航栏，
    太长像正文）的当成候选文章。这个方法比RSS脆弱得多，网站改版可能会
    让抓取失效或者抓到垃圾内容，需要针对具体网站调整 min/max_title_len
    和 url_must_contain 这几个参数。
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; heatpump-topics-bot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"[警告] 网页爬取失败 {url}: HTTP {resp.status_code}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[警告] 网页爬取异常 {url}: {e}")
        return []

    seen_links = set()
    results = []
    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or not (min_title_len <= len(title) <= max_title_len):
            continue
        if url_must_contain and url_must_contain not in href:
            continue
        # 补全相对链接
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        if not href.startswith("http"):
            continue
        if href in seen_links:
            continue
        seen_links.add(href)
        results.append({"title": title, "link": href})
    return results


RSS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


FEED_CACHE_PATH = os.path.join(DATA_DIR, "feed_cache.json")

# 用来判断一条新闻是否跟热泵/空调相关的关键词（英文+主要欧洲语言常见词）。
# 只有标题或摘要里命中至少一个词的新闻才会被保留，避免抓到大量不相关内容
# （很多综合性行业媒体首页混杂各种建筑/能源新闻，不加这层过滤会很脏）。
RELEVANCE_KEYWORDS = [
    "heat pump", "air conditioning", "air conditioner", "hvac", "refrigeration",
    "refrigerant", "heating", "cooling", "chiller", "vrf", "vrv",
    "pompe à chaleur", "climatisation", "génie climatique",  # 法语
    "pompa di calore", "climatizzazione", "condizionamento",  # 意大利语
    "bomba de calor", "climatización", "aire acondicionado",  # 西班牙语
    "warmtepomp", "airconditioning", "koeltechniek",  # 荷兰语
    "pompa ciepła", "klimatyzacja", "chłodnictwo",  # 波兰语
    "värmepump", "varmepumpe", "ilmastointi", "kylteknik",  # 北欧语言
]


def is_relevant(title, summary=""):
    text = f"{title} {summary}".lower()
    return any(kw in text for kw in RELEVANCE_KEYWORDS)


def load_feed_cache():
    if not os.path.exists(FEED_CACHE_PATH):
        return {}
    try:
        with open(FEED_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_feed_cache(cache):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FEED_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _feed_has_entries(url):
    try:
        parsed = feedparser.parse(url, request_headers=RSS_HEADERS)
        return len(parsed.entries) > 0
    except Exception:
        return False


def discover_feed_url(homepage_url, cache):
    """按顺序自动探测一个网站的RSS地址：
    1. 如果之前探测成功过，直接用缓存的地址（省请求，跑得快）
    2. 检测页面HTML里的 <link rel="alternate" type="application/rss+xml"> 标签
    3. 依次尝试常见路径：/feed/、/rss/、/news/feed/、/feed、/rss.xml、/rss
    都失败就返回 None，调用方会记录警告，不会中断整个流程。
    """
    if homepage_url in cache and cache[homepage_url].get("feed_url"):
        cached = cache[homepage_url]["feed_url"]
        if _feed_has_entries(cached):
            return cached
        # 缓存的地址失效了（比如网站改版），清掉重新探测

    from urllib.parse import urljoin

    try:
        resp = requests.get(homepage_url, headers=RSS_HEADERS, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            link_tag = soup.find(
                "link", attrs={"type": lambda t: t and "rss" in t.lower()}
            )
            if link_tag and link_tag.get("href"):
                candidate = urljoin(homepage_url, link_tag["href"])
                if _feed_has_entries(candidate):
                    cache[homepage_url] = {"feed_url": candidate, "method": "html_link_tag"}
                    return candidate
    except Exception:
        pass

    base = homepage_url.rstrip("/") + "/"
    for path in ("feed/", "rss/", "news/feed/", "feed", "rss.xml", "rss"):
        candidate = urljoin(base, path)
        if _feed_has_entries(candidate):
            cache[homepage_url] = {"feed_url": candidate, "method": f"common_path:{path}"}
            return candidate

    cache[homepage_url] = {"feed_url": None, "method": "not_found"}
    return None


def collect_news(config):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    candidates = []
    regions = config.get("regions", {}) or {}
    feed_cache = load_feed_cache()
    cache_dirty = False

    for region, feeds in regions.items():
        feeds = feeds or []
        region_count = 0
        for feed in feeds:
            source_name = feed.get("name", "")
            country = feed.get("country", "")
            language = feed.get("language", "")

            rss_url = feed.get("rss")
            if not rss_url and feed.get("homepage"):
                rss_url = discover_feed_url(feed["homepage"], feed_cache)
                cache_dirty = True
                if not rss_url:
                    print(f"[警告] {source_name} 自动探测RSS失败（试了原生标签+常见路径都没找到），跳过")
                    continue
                else:
                    print(f"[信息] {source_name} 自动探测到RSS: {rss_url}")

            if not rss_url:
                continue

            try:
                parsed = feedparser.parse(rss_url, request_headers=RSS_HEADERS)
            except Exception as e:
                print(f"[警告] 新闻源解析失败 {source_name}: {e}")
                continue

            raw_count = len(parsed.entries)
            kept_count = 0
            for entry in parsed.entries:
                pub_time = parse_entry_time(entry)
                if pub_time and pub_time < cutoff:
                    continue
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = (entry.get("summary", "") or "")[:400]
                if not title:
                    continue
                if not is_relevant(title, summary):
                    continue
                candidates.append({
                    "id": make_id(link, title),
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "source_type": "news",
                    "source_name": source_name,
                    "region": region,
                    "country": country,
                    "language": language,
                    "engagement": None,
                    "published": pub_time.isoformat() if pub_time else None,
                })
                kept_count += 1
            print(f"[信息] {source_name}: RSS原始 {raw_count} 条，相关且在时间窗口内 {kept_count} 条")
            region_count += kept_count
        print(f"[信息] 新闻-{region}: 本次抓到 {region_count} 条")

    if cache_dirty:
        save_feed_cache(feed_cache)

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

    # 这是根据 https://apify.com/harshmaur/reddit-scraper 的 Input -> JSON example
    # 核对过的真实字段名，不是猜的。注意：这个actor目前没有看到"按年度最热排序"
    # 这个开关，所以拿到的是该板块默认排序下的帖子（不保证是过去一年最热），
    # 但点赞数/评论数是真实的，打分逻辑依然有效。
    #
    # 重要：maxPostsCount 是"整次调用的总量上限"，不是"每个板块各自的上限"。
    # 之前把所有板块一次性传进去，结果额度被最先/最热的一两个板块吃光，
    # 其余板块一条都没有——所以这里改成"每个板块单独调用一次"，
    # 各自给固定的 REDDIT_LIMIT 上限，保证覆盖均衡。
    for sub in subs:
        slug = sub.get("slug")
        name = sub.get("name", f"r/{slug}")
        region_hint = sub.get("region")
        if not slug:
            continue

        payload = {
            "searchTerms": [],
            "searchPosts": True,
            "searchComments": False,
            "searchCommunities": False,
            "withinCommunity": "",
            "startUrls": [],
            "subredditUrls": [f"https://www.reddit.com/r/{slug}"],
            "onlyWithFlair": False,
            "crawlCommentsPerPost": False,
            "includeNSFW": False,
            "maxPostsCount": REDDIT_LIMIT,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        try:
            resp = requests.post(
                APIFY_RUN_URL,
                params={"token": api_token},
                json=payload,
                timeout=120,
            )
            if not (200 <= resp.status_code < 300):
                print(f"[警告] Apify抓取 {name} 失败: HTTP {resp.status_code} - {resp.text[:200]}")
                continue
            items = resp.json()
        except Exception as e:
            print(f"[警告] Apify抓取 {name} 异常: {e}")
            continue

        sub_count = 0
        for item in items:
            if item.get("dataType") and item.get("dataType") not in ("post", None):
                continue
            title = (item.get("title") or item.get("postTitle") or "").strip()
            if not title:
                continue
            link = item.get("url") or item.get("postUrl") or item.get("permalink") or ""
            score = item.get("upVotes", item.get("score", item.get("ups", 0))) or 0
            comments = item.get("numberOfComments", item.get("commentCount", item.get("numComments", 0))) or 0
            candidates.append({
                "id": make_id(link, title),
                "title": title,
                "link": link,
                "summary": (item.get("body") or item.get("selftext") or "")[:400],
                "source_type": "reddit",
                "source_name": name,
                "region": region_hint,
                "engagement": {"score": score, "comments": comments},
                "published": item.get("createdAt") or item.get("created_utc"),
            })
            sub_count += 1

        print(f"[信息] Reddit-{name}: 抓到 {sub_count} 条")

    print(f"[完成] Apify Reddit抓取: 共 {len(candidates)} 条")
    return candidates


def collect_competitors(config):
    """同行/竞品官网新闻博客——支持两种接入方式：
    - rss: 标准RSS订阅，稳定可靠，优先用这个
    - html: 没有RSS的网站，直接爬网页列表页兜底，
      需要 url_must_contain 参数缩小范围，减少抓到导航栏垃圾链接的概率，
      这类信源比RSS脆弱，网站改版可能需要重新调整参数
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=NEWS_LOOKBACK_HOURS)
    candidates = []
    competitors = config.get("competitors", []) or []
    for comp in competitors:
        source_name = comp.get("name", "")
        category = comp.get("category", "competitor")

        if comp.get("rss"):
            rss_url = comp["rss"]
            try:
                parsed = feedparser.parse(rss_url, request_headers=RSS_HEADERS)
            except Exception as e:
                print(f"[警告] 同行信源解析失败 {source_name}: {e}")
                continue
            raw_entry_count = len(parsed.entries)
            if raw_entry_count == 0:
                bozo_msg = getattr(parsed, "bozo_exception", "无entries返回，可能被拦截或RSS地址失效")
                print(f"[警告] {source_name} RSS原始条目数为0，诊断信息: {bozo_msg}")
            count = 0
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
                    "source_type": "competitor",
                    "source_name": source_name,
                    "region": category,
                    "engagement": None,
                    "published": pub_time.isoformat() if pub_time else None,
                })
                count += 1
            print(f"[信息] 同行(RSS)-{source_name}: RSS原始 {raw_entry_count} 条，"
                  f"时间窗口内 {count} 条")

        elif comp.get("html"):
            items = scrape_html_blog(
                comp["html"],
                min_title_len=comp.get("min_title_len", 15),
                max_title_len=comp.get("max_title_len", 140),
                url_must_contain=comp.get("url_must_contain"),
            )
            count = 0
            for item in items:
                candidates.append({
                    "id": make_id(item["link"], item["title"]),
                    "title": item["title"],
                    "link": item["link"],
                    "summary": "",
                    "source_type": "competitor",
                    "source_name": source_name,
                    "region": category,
                    "engagement": None,
                    "published": None,  # 网页爬取拿不到发布时间，靠"重复出现"信号判断持续度
                })
                count += 1
            print(f"[信息] 同行(网页爬取)-{source_name}: 抓到 {count} 条")

    return candidates


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    os.makedirs(DATA_DIR, exist_ok=True)

    news_candidates = collect_news(config)
    with open(os.path.join(DATA_DIR, "news_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(news_candidates, f, ensure_ascii=False, indent=2)

    reddit_candidates = collect_reddit(config)
    with open(os.path.join(DATA_DIR, "reddit_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(reddit_candidates, f, ensure_ascii=False, indent=2)

    competitor_candidates = collect_competitors(config)
    with open(os.path.join(DATA_DIR, "competitor_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(competitor_candidates, f, ensure_ascii=False, indent=2)

    print(f"[完成] 新闻 {len(news_candidates)} 条 + Reddit {len(reddit_candidates)} 条 "
          f"+ 同行动态 {len(competitor_candidates)} 条，分别写入三个候选文件")


if __name__ == "__main__":
    main()
