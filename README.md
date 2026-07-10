# 热泵B2B每日选题看板

每天自动抓欧洲/中东/亚洲的热泵行业新闻，配合Google Trends热度，
用LLM生成选题建议，渲染成一个网页，托管在GitHub Pages上免费访问。

## 一、新建仓库并上传文件（第一次，约5分钟）

1. 打开 https://github.com/new
2. Repository name 填 `heatpump-topics`（或你喜欢的名字）
3. 选择 **Public**（GitHub Pages免费版要求公开仓库；如果不想让别人看到，
   之后可以考虑升级成付费Private+Pages，先用Public跑起来）
4. 不要勾选任何初始化选项（不加README/不加.gitignore），直接点 Create repository
5. 新建好之后，页面上会有一个空仓库的提示。把我打包给你的这些文件全部上传：
   - 打开仓库页面 -> `Add file` -> `Upload files`
   - 把整个项目文件夹里的所有文件和文件夹拖进去（包括隐藏的 `.github` 文件夹，
     如果拖拽时看不到`.github`，可以先在网页上手动创建这个路径下的文件，
     或者用GitHub Desktop客户端整体上传，更省事）
   - 提交（Commit changes）

> 提示：如果你完全不想用命令行，最简单的方式是安装 **GitHub Desktop**
> (https://desktop.github.com)，用它把这个文件夹整体拖进去、点 Publish，
> 比网页上传更不容易漏文件（尤其是 `.github/workflows` 这种隐藏路径）。

## 二、配置OpenAI API Key（必须做，否则选题生成会失败）

1. 进入仓库 -> `Settings` -> 左侧菜单 `Secrets and variables` -> `Actions`
2. 点 `New repository secret`
3. Name 填：`OPENAI_API_KEY`
4. Value 填你的OpenAI API key（sk-开头那串）
5. 保存

## 三、开启GitHub Pages（把看板变成一个可访问的网址）

1. 仓库 -> `Settings` -> 左侧菜单 `Pages`
2. Source 选择 `Deploy from a branch`
3. Branch 选择 `main`，文件夹选择 `/docs`，点 Save
4. 等1-2分钟，页面顶部会出现你的网址，形如：
   `https://你的用户名.github.io/heatpump-topics/`
   这个就是你每天打开的固定看板链接，收藏起来就行

## 四、手动跑一次，测试整条流程通不通

1. 仓库上方 `Actions` 标签
2. 左侧选择 `每日热泵选题更新`
3. 右侧点 `Run workflow` -> 再点一次绿色按钮，手动触发一次
4. 等1-2分钟刷新页面，看运行是否变绿色勾。如果是红叉，点进去看日志，
   常见问题：
   - `OPENAI_API_KEY` 没配对 -> 回到第二步检查
   - RSS抓取某个源报警告 -> 正常，说明那个信源链接失效了，去
     `config/sources.yaml` 换一个（见下方"如何维护信源"）
5. 跑成功后，打开第三步拿到的网址，应该能看到当天的看板

之后每天北京时间早上8点会自动跑一次，不用你管。

## 五、如何维护信源（关键词/新闻源可以随时改）

打开 `config/sources.yaml`：

- `europe` / `middle_east` / `asia` 下面是各区域的RSS新闻源，
  可以随时加/删/换。中东和亚洲这两块我给的信源比较少，
  建议你自己找一些行业展会官网、当地能源政策官网的新闻页补充进去。
- `seed_keywords` 是拿去Google Trends验证热度的种子词，
  可以根据你的产品线（比如你主打商用大型机还是家用机）调整方向。

改完直接在网页上编辑保存（GitHub网页自带一个简单编辑器，点文件右上角铅笔图标），
不需要额外操作，第二天自动生效。

## 六、每周人工复核关键词（这是你选的方案：Trends自动 + 人工周复核）

看板上每个选题卡片如果显示"待人工复核"标签，说明这个长尾词只是LLM建议的方向，
还没经过真实搜索量验证。建议你：

1. 每周一固定花10-15分钟，把本周所有"待人工复核"的词
   拿去 Google Ads 后台的关键词规划师查一遍真实搜索量区间
2. 确认有价值的，就可以安排写；量级太低或没有搜索意图的，跳过

这一步目前是纯人工，看板不会帮你自动打勾——如果后面跑顺了想把这步也自动化
（接入Google Ads API拿真实数据），随时可以回来找我升级。

## 目录结构

```
heatpump-topics/
├── config/sources.yaml       新闻源 + 种子关键词配置（你会经常改这个）
├── scripts/
│   ├── fetch_news.py         抓RSS新闻
│   ├── check_trends.py       查Google Trends热度
│   ├── generate_topics.py    调用OpenAI生成选题
│   └── render_dashboard.py   渲染成网页
├── data/                     每天运行产生的中间数据（自动生成，不用管）
├── docs/index.html           最终看板网页（GitHub Pages从这里发布）
└── .github/workflows/daily.yml   每天自动运行的定时任务配置
```
