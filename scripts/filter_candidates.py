"""
在候选话题进入打分排名之前，先做一轮"内容价值过滤"：
用LLM快速批量判断每条候选是不是"纯玩笑/吐槽/无实质信息量"的内容
（比如Reddit上很受欢迎的梗图、纯发泄贴，互动量很高但对B2B内容营销毫无价值），
过滤掉这些，避免它们仅凭高互动量就挤进Top50话题库。

**这些被过滤掉的内容不会被丢弃**，会存进 data/humor_pool.json，
单独渲染成一个"论坛趣味/吐槽帖"页面，跟正经的话题榜分开展示。

这一步只做粗筛（yes/no判断），成本很低，用免费额度充足的flash-lite模型，
批量处理，不是逐条调用。

新闻类候选默认全部保留（不参与这轮过滤，新闻本身的时效性已经是价值信号）。
"""
import json
import os
from datetime import datetime, timezone

import google.generativeai as genai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "candidates.json")
HUMOR_POOL_PATH = os.path.join(DATA_DIR, "humor_pool.json")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
BATCH_SIZE = 60

SYSTEM_PROMPT = """你在给一个B2B热泵/空调行业内容营销团队筛选Reddit候选话题。
读者是采购商、经销商、工程公司，团队想找的是"有实质信息量、能启发写一篇
技术文章/案例/行业观察"的话题。

请排除掉这些类型（worth_writing = false）：
- 纯粹的玩笑、梗图、吐槽、抱怨情绪发泄，没有具体技术/行业信息
- 纯个人闲聊、跟工作内容无关的话题（比如职业规划感慨、退休吐槽这种没有
  具体技术信息的帖子）
- 单纯征友、招聘启示、纯广告

请保留（worth_writing = true）：
- 包含具体技术问题、故障排查、产品对比、安装案例的帖子
- 反映真实采购/维护痛点，能看出用户在纠结什么决策的帖子
- 行业动态、政策、市场变化相关的讨论

你会收到一个候选列表，每条有id和title（可能还有summary）。
只输出严格的JSON数组，顺序不用跟输入一致，但id要能对上，不要漏项：
[{"id": "...", "worth_writing": true或false}]
不要markdown代码块标记，不要任何多余文字。
"""


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    candidates = load_json(CANDIDATES_PATH, [])
    if not candidates:
        print("[提示] 没有候选，跳过过滤")
        return

    # 新闻类默认全部保留，只过滤Reddit类
    news_items = [c for c in candidates if c["source_type"] != "reddit"]
    reddit_items = [c for c in candidates if c["source_type"] == "reddit"]

    if not reddit_items:
        print("[提示] 没有Reddit候选需要过滤")
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[警告] 没有配置 GEMINI_API_KEY，跳过内容价值过滤（保留全部候选）")
        return

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=SYSTEM_PROMPT,
        generation_config={"response_mime_type": "application/json"},
    )

    kept_reddit = []
    dropped_items = []

    for i in range(0, len(reddit_items), BATCH_SIZE):
        batch = reddit_items[i:i + BATCH_SIZE]
        payload = [
            {"id": c["id"], "title": c["title"], "summary": c.get("summary", "")[:200]}
            for c in batch
        ]
        try:
            response = model.generate_content(json.dumps(payload, ensure_ascii=False))
            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.lower().startswith("json"):
                    raw = raw[4:]
            results = json.loads(raw)
            worth_by_id = {r["id"]: r.get("worth_writing", True) for r in results if "id" in r}
        except Exception as e:
            print(f"[警告] 第{i // BATCH_SIZE + 1}批过滤失败，这批全部保留: {e}")
            worth_by_id = {}

        for c in batch:
            # 判断失败/没返回结果的，默认保留，避免因为LLM偶发问题误删数据
            if worth_by_id.get(c["id"], True):
                kept_reddit.append(c)
            else:
                dropped_items.append(c)

    final_candidates = news_items + kept_reddit
    save_json(CANDIDATES_PATH, final_candidates)

    # 被过滤掉的存进独立的趣味帖库，累积保留，不清空
    if dropped_items:
        humor_pool = load_json(HUMOR_POOL_PATH, {})
        today = datetime.now(timezone.utc).date().isoformat()
        for c in dropped_items:
            cid = c["id"]
            eng = c.get("engagement") or {}
            if cid in humor_pool:
                humor_pool[cid]["last_seen"] = today
            else:
                humor_pool[cid] = {
                    "id": cid,
                    "title": c["title"],
                    "link": c["link"],
                    "source_name": c.get("source_name", ""),
                    "upvotes": eng.get("score", 0) or 0,
                    "comments": eng.get("comments", 0) or 0,
                    "first_seen": today,
                    "last_seen": today,
                }
        save_json(HUMOR_POOL_PATH, humor_pool)

    print(f"[完成] 内容价值过滤：Reddit候选 {len(reddit_items)} 条中过滤掉 {len(dropped_items)} 条"
          f"（存入趣味帖库），保留 {len(kept_reddit)} 条，加上新闻 {len(news_items)} 条，"
          f"共 {len(final_candidates)} 条写回 {CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
