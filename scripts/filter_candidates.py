"""
只针对 data/reddit_candidates.json 做一轮"内容价值过滤"（新闻/同行动态
这两个榜单不需要过滤，本身就是编辑筛过的正式媒体内容）：
用LLM快速批量判断每条Reddit候选是不是"专业对口"的内容，标准比"排除玩笑"
更严格——互动量再高，泛泛而谈、纯情绪发泄的帖子也会被过滤掉。

**被过滤掉的内容不会被丢弃**，会存进 data/humor_pool.json，
单独渲染成一个"论坛趣味/吐槽帖"页面，跟正经的Reddit榜分开展示。

这一步只做粗筛（yes/no判断），成本很低，用免费额度充足的flash-lite模型，
批量处理，不是逐条调用。
"""
import json
import os
from datetime import datetime, timezone

import google.generativeai as genai

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
CANDIDATES_PATH = os.path.join(DATA_DIR, "reddit_candidates.json")
HUMOR_POOL_PATH = os.path.join(DATA_DIR, "humor_pool.json")

MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
BATCH_SIZE = 60

SYSTEM_PROMPT = """你在给一个B2B热泵/空调行业内容营销团队筛选Reddit候选话题。
读者是采购商、经销商、工程公司，团队要的是"专业对口"的内容——不是随便什么
互动量高的帖子都要，标准要比"排除纯玩笑"更严格一些。

请判定 worth_writing = true 只有满足这些条件之一：
- 包含具体技术问题、故障排查、产品对比、安装案例，能看出真实的专业判断和经验
- 反映真实采购/维护决策中的纠结点（比如"到底该选A还是B""这个方案值不值"）
- 行业动态、政策、市场变化、认证标准相关的讨论

请判定 worth_writing = false（哪怕互动量很高也要排除）：
- 纯粹的玩笑、梗图、吐槽、抱怨情绪发泄
- 个人职业感慨、退休/跳槽故事、纯情绪共鸣贴，没有具体技术信息
- 单纯征友、招聘启示、纯广告
- 内容太泛泛（比如"你们最喜欢的工具是什么"这种闲聊式提问，没有实质信息量）

判断时"专业对口"是核心标准，宁可严格一点漏掉几条，也不要把泛泛而谈的内容
当成有价值的选题。

同时，不管worth_writing判断结果是true还是false，都要给每一条写一句
**中文摘要**（summary_cn，大约40-60字），说清楚这个帖子具体在讲什么，
让人不用点开原文就知道内容——哪怕是被排除的玩笑贴，也要写清楚"在开什么玩笑"，
不能写"这是一个玩笑帖"这种没有信息量的话。

你会收到一个候选列表，每条有id和title（可能还有summary）。
只输出严格的JSON数组，顺序不用跟输入一致，但id要能对上，不要漏项：
[{"id": "...", "worth_writing": true或false, "summary_cn": "..."}]
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
        print("[提示] 没有Reddit候选，跳过过滤")
        return

    reddit_items = candidates  # 这个文件现在只包含Reddit候选，不用再区分

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
            result_by_id = {r["id"]: r for r in results if "id" in r}
        except Exception as e:
            print(f"[警告] 第{i // BATCH_SIZE + 1}批过滤失败，这批全部保留: {e}")
            result_by_id = {}

        for c in batch:
            r = result_by_id.get(c["id"], {})
            # 判断失败/没返回结果的，默认保留，避免因为LLM偶发问题误删数据
            c["summary_cn"] = r.get("summary_cn", "")
            if r.get("worth_writing", True):
                kept_reddit.append(c)
            else:
                dropped_items.append(c)

    final_candidates = kept_reddit
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
                    "summary_cn": c.get("summary_cn") or "",
                    "upvotes": eng.get("score", 0) or 0,
                    "comments": eng.get("comments", 0) or 0,
                    "first_seen": today,
                    "last_seen": today,
                }
        save_json(HUMOR_POOL_PATH, humor_pool)

    print(f"[完成] 内容价值过滤：Reddit候选 {len(reddit_items)} 条中过滤掉 {len(dropped_items)} 条"
          f"（存入趣味帖库），保留 {len(kept_reddit)} 条专业对口的候选，"
          f"写回 {CANDIDATES_PATH}")


if __name__ == "__main__":
    main()
