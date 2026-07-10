# 热泵B2B话题热度榜（Top 50，每天迭代更新）

不是"每天推荐今天写什么"，而是维护一个**持续滚动的Top 50话题库**：
每天抓新的候选（新闻 + Reddit近一年热帖），跟已有话题库合并打分，
排出当前热度前50名。老话题没人提了会慢慢掉分掉出榜单，
重新被提起的话题会加分回升——类似一个"热度排行榜"，而不是一次性清单。

## 打分逻辑（写给你自己理解，不需要改代码也能看懂）

- Reddit帖子：`分数 = 点赞数 + 2×评论数`（评论权重更高，代表真实讨论）
- 新闻类：每次出现给一个基础分，反复被提及会有小幅加成
- 每天没被重新提及的话题：分数打9.7折（微妙衰减，不会一天就掉出榜）
- 重新出现的老话题：分数回升，代表"热度复燃"

## 一、首次部署（如果是全新仓库）

跟之前一样：新建GitHub仓库、上传这些文件、开启GitHub Pages（分支`main`，目录`/docs`）。
如果你已经有一个跑起来的旧版仓库，直接看下面"从旧版迁移"。

## 二、配置Gemini API Key + Reddit应用凭证

**Gemini**（不需要绑卡）：

1. 打开 https://aistudio.google.com/apikey ，登录Google账号，创建key
2. 仓库 -> `Settings` -> `Secrets and variables` -> `Actions` -> `New repository secret`
3. Name: `GEMINI_API_KEY`，Value填你的key

**Apify**（Reddit数据来源，按结果付费，不需要注册Reddit应用，每月5美元免费额度）：

1. 打开 https://console.apify.com/sign-up ，用邮箱注册（不用绑卡）
2. 登录后，右上角头像 -> `Settings` -> `API & Integrations`，复制你的 `Personal API token`
3. 同样加一个repository secret：`APIFY_API_TOKEN`
4. 成本说明：Reddit这部分改成**每周一**才抓一次（不是每天），一次约1.2美元，
   一个月4次约4.8美元，压在5美元免费额度内。如果调整了`config/sources.yaml`里
   板块数量或`REDDIT_LIMIT`，注意重新估算成本，别超出免费额度太多
5. 如果实际调用报"输入格式错误"，去 https://apify.com/harshmaur/reddit-scraper/input-schema
   核对一下真实的输入字段名，照着改 `scripts/collect_candidates.py` 里
   `collect_reddit()` 函数里的 `payload` 变量就行

## 三、从旧版迁移（如果你之前已经跑通过"每日选题"那一版）

这次改动删除/替换了几个文件：

- 删除：`scripts/fetch_news.py`、`scripts/check_trends.py`、`scripts/generate_topics.py`
- 新增：`scripts/collect_candidates.py`、`scripts/update_topic_bank.py`、`scripts/enrich_topics.py`
- 修改：`scripts/render_dashboard.py`、`config/sources.yaml`、`requirements.txt`、
  `.github/workflows/daily.yml`

直接把这个新的项目文件夹整体覆盖替换你桌面的旧文件夹（旧文件会被删除/覆盖），
然后让Codex帮你 `git add -A && git commit -m "升级为Top50话题库模式" && git push`。

**旧版遗留的`OPENAI_API_KEY` secret如果还在，可以留着不用管，也可以删掉**
（`gh secret delete OPENAI_API_KEY`），新流程只用`GEMINI_API_KEY`。

## 四、手动跑一次测试

```
gh workflow run daily.yml
gh run watch
```

第一次跑，因为话题库是空的，全部话题都会是"NEW"，之后每天会看到排名变化
（↑上升、↓下降、NEW新上榜）。

## 五、维护信源（v3更新：已扩展到欧洲/中东/亚洲/非洲/南美 + 24个Reddit板块）

打开 `config/sources.yaml`：

- `regions` 下是五个区域的新闻RSS源。非洲、南美目前还没有验证过的RSS地址，
  是空的框架，需要你或者Codex去核实具体网址后手动加进去（格式照抄欧洲那几条改就行）。
  优先建议核实这几个：JARN（亚洲）、RACA Journal（非洲）、ACR Latinoamérica（南美）
- `reddit_subreddits`：已经扩到24个板块，覆盖五个区域 + 几个全球通用版块。
  这块不需要额外验证，Reddit的RSS格式对任何板块都通用
- 这个文件改完直接生效，不需要额外操作

**没有接入的信息源**（Google Trends、GDELT、LinkedIn等）：这些不是通过订阅RSS链接
就能用的，需要专门的API或者付费权限，目前这套轻量架构没有接。如果后面想加，
最值得优先做的是把Google Trends重新接回来，用来做"搜索热度增长"这个额外的打分维度——
这个可以作为下一步升级，不建议现在一次性全加，容易一次改太多东西全垮。

## 六、关于关键词验证（你之前选的方案：先自动化跑起来，人工周复核）

看板上每条话题旁边的"目标长尾词"是LLM根据标题建议的方向，还没有经过真实搜索量验证。
建议每周固定花10-15分钟，把当周新上榜、排名靠前的话题的关键词，
拿去 Google Ads 后台的关键词规划师核实一遍真实搜索量区间，
确认有价值的再安排写。这一步目前是纯人工，看板不会自动记录你确认过哪些——
后面用顺手了想自动化这一步，随时可以回来升级。

## 目录结构

```
heatpump-topics/
├── config/sources.yaml          新闻源 + Reddit板块 配置
├── scripts/
│   ├── collect_candidates.py    抓新闻RSS + Reddit年度热帖，输出候选
│   ├── update_topic_bank.py     候选合并进持久化话题库，打分排名，取Top50
│   ├── enrich_topics.py         LLM给新上榜话题补关键词/形式建议
│   └── render_dashboard.py      渲染成榜单网页
├── data/
│   ├── candidates.json          每天临时的候选（不重要，会被覆盖）
│   └── topic_bank.json          持久化话题库，这是核心数据，每天累积更新
├── docs/index.html              最终榜单网页（GitHub Pages从这里发布）
└── .github/workflows/daily.yml  每天自动运行的定时任务
```
