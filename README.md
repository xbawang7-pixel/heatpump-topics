# 热泵/空调 B2B 内容灵感中心（v4：三个独立榜单）

## 这次架构变了，说清楚为什么

v3之前是"新闻+Reddit混在一起打分排一个榜"，实际用起来发现这是个错误设计——
新闻和Reddit根本不是一类东西，硬凑在一个分数体系里比较，要么新闻被Reddit的
互动量完全碾压，要么打补丁强行保底又显得别扭。

v4改成**三个完全独立的榜单**，各自按自己的逻辑排序，互不比较：

1. **新闻榜**（`news.html`）：欧洲/中东/亚洲/非洲/南美的行业媒体新闻
2. **Reddit专业榜**（`reddit.html`）：Reddit热帖，但先经过"专业对口"过滤
   （不只是排除玩笑，标准更严格——泛泛而谈的内容也会被过滤掉）
3. **同行动态**（`competitors.html`）：国际品牌 + 国产同行官网新闻/博客，
   找选题灵感和内容布局参考

首页（`index.html`）是这三个榜单的导航入口，不再是合并榜单本身。

另外两个辅助页面：
- `keywords.html`：三个榜单累积下来的长尾关键词库
- `humor.html`：被"专业对口"过滤掉的Reddit玩笑/吐槽帖，单独展示，纯粹娱乐用

## 关于"同行动态"这块，几件事要知道

- **LinkedIn没有接进来**：反爬虫机制比Reddit严格得多，没有公开API，自动化
  抓取容易失效、还可能牵连你自己的账号被限制。建议偶尔手动去看一眼就好。
- **目前只confirmed了2家有真实RSS**：Carrier、Daikin。国产同行
  （SPRSUN、PHNIX等）大多是自建CMS博客，没有标准RSS接口，接不进来
  （除非以后升级成网页抓取，那是更大的工程）。
- `config/sources.yaml` 里 `competitors` 这个板块可以随时加，方法是：
  去对方官网新闻/博客页面找有没有"RSS Feed"按钮，或者试
  `域名/feed`、`域名/rss` 这类常见路径。

## 一、部署（全新仓库）

跟之前一样：新建GitHub仓库、上传文件、开启GitHub Pages（分支`main`，目录`/docs`）。

## 二、配置密钥

**Gemini**（不需要绑卡）：
1. https://aistudio.google.com/apikey 创建key
2. 仓库 Settings -> Secrets and variables -> Actions -> New repository secret
3. Name: `GEMINI_API_KEY`

**Apify**（Reddit数据来源，第一次订阅Starter档需要$29，用完记得在下个计费周期
前降级回Free）：
1. https://console.apify.com 注册
2. Settings -> API & Integrations 复制token
3. Name: `APIFY_API_TOKEN`

## 三、从v3迁移

这次删除/新增的文件比较多：

**删除**：`scripts/update_topic_bank.py`、`scripts/render_dashboard.py`

**新增**：
- `scripts/bank_utils.py`（三个榜单共用的打分/排名逻辑）
- `scripts/update_news_bank.py` / `update_reddit_bank.py` / `update_competitor_bank.py`
- `scripts/board_render.py`（三个榜单页面共用的渲染逻辑）
- `scripts/render_news.py` / `render_reddit.py` / `render_competitors.py` / `render_home.py`

**修改**：`scripts/collect_candidates.py`（新增同行动态抓取，输出改成三份独立
候选文件）、`scripts/filter_candidates.py`（只处理Reddit候选）、
`scripts/enrich_topics.py`（循环处理三个榜单）、`config/sources.yaml`
（新增competitors板块）、`.github/workflows/daily.yml`（步骤全部重排）

把新版文件整体覆盖旧文件夹（注意有文件被删除，建议整个目录重新同步，
不是简单覆盖），然后：
```
git add -A
git commit -m "重构为三个独立榜单"
git push
```

## 四、Reddit抓取仍然是每周一才跑

省Apify额度，跟之前一样。想测试的话临时把 `daily.yml` 里
"判断是否周一"那个条件改成 `if true`，测完记得改回去。

## 五、目录结构

```
heatpump-topics/
├── config/sources.yaml           新闻源 + Reddit板块 + 同行竞品 配置
├── scripts/
│   ├── collect_candidates.py     抓新闻/Reddit/同行动态，输出三份候选文件
│   ├── filter_candidates.py      过滤Reddit候选，只留专业对口内容
│   ├── bank_utils.py             三个榜单共用的打分排名逻辑
│   ├── update_news_bank.py       更新新闻榜
│   ├── update_reddit_bank.py     更新Reddit专业榜
│   ├── update_competitor_bank.py 更新同行动态榜
│   ├── enrich_topics.py          LLM补充关键词/摘要（循环处理三个榜单）
│   ├── board_render.py           三个榜单页面共用的渲染逻辑
│   ├── render_home.py            首页（导航中枢）
│   ├── render_news.py / render_reddit.py / render_competitors.py
│   ├── render_keywords.py        长尾关键词库页面
│   └── render_humor.py           被过滤掉的Reddit趣味帖页面
├── data/                         持久化数据（三个bank文件 + 关键词库 + 趣味帖库）
├── docs/                         最终网页（GitHub Pages从这里发布）
└── .github/workflows/daily.yml   每天自动运行的定时任务
```
