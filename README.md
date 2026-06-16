# Embodied Radar

Embodied Radar 是一个面向具身智能研究的论文雷达，用于自动汇总 arXiv 最新论文、顶级会议论文、引用量、团队单位、项目链接和获奖信息，并发布为 GitHub Pages 静态站点。

线上地址：

<https://timesame128.github.io/reach-arXiv/>

## 功能

- 自动同步近期待筛选的 arXiv 论文。
- 收录 CoRL、ICRA、RSS、IROS、CVPR、ICLR、NeurIPS、ICML、ICCV 等会议论文。
- 使用 OpenAlex 补全作者单位、引用量、摘要和会议元数据，并在必要时回退到 DBLP。
- 支持按论文来源、研究方向、时间范围、引用量区间和关键词筛选。
- 支持最新优先、引用最高、相关性最高和综合推荐排序。
- 支持列表视图、卡片视图和沉浸浏览模式。
- 展示论文详情、PDF、项目或代码链接。
- 通过 `data/awards.json` 人工维护 Best Paper、Outstanding Paper、Honorable Mention 等获奖论文。
- GitHub Actions 定时刷新数据并自动部署 GitHub Pages。

## 仓库结构

```text
.github/workflows/   GitHub Actions 自动刷新和 Pages 部署
data/                论文缓存与获奖清单
embodied_arxiv/      抓取、分类、会议同步和服务逻辑
static/              前端 CSS、JavaScript 和图标
templates/           Flask 页面模板
tests/               自动测试
app.py               本地 Flask 服务
build_static.py      静态站点构建脚本
requirements.txt     Python 依赖
```

## 本地运行

```powershell
python -m pip install -r requirements.txt
python app.py
```

打开：

<http://127.0.0.1:5000>

默认会启动后台刷新任务。调试前端或只想读取本地缓存时，可以关闭后台刷新：

```powershell
$env:DISABLE_SCHEDULER = "1"
python app.py
```

## 构建静态站点

```powershell
python build_static.py
python -m http.server 8000 --directory _site
```

然后访问：

<http://127.0.0.1:8000>

如果需要在构建时刷新论文数据：

```powershell
python build_static.py --refresh
```

## GitHub Pages 部署

仓库包含 `.github/workflows/deploy-pages.yml`。工作流会：

1. 安装 Python 依赖。
2. 执行 `python build_static.py --refresh`。
3. 如果 `data/papers.json` 有变化，将刷新后的缓存提交回当前分支。
4. 上传 `_site` 并部署到 GitHub Pages。

工作流触发方式：

- 推送到 `main` 或 `master`
- 每 6 小时定时运行一次
- 在 Actions 页面手动运行 `Update papers and deploy Pages`

Pages 设置中需要选择：

```text
Settings -> Pages -> Build and deployment -> Source -> GitHub Actions
```

## 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PAPER_DAYS` | `15` | 保留最近多少天的 arXiv 论文 |
| `REFRESH_INTERVAL_MINUTES` | `360` | 本地服务后台刷新间隔 |
| `ARXIV_MAX_RESULTS` | `300` | 每次 arXiv 查询上限 |
| `OPENALEX_EMAIL` | 空 | OpenAlex polite pool 邮箱 |
| `OPENALEX_API_KEY` | 空 | OpenAlex API Key，建议在 GitHub Actions Secrets 中配置 |
| `CONFERENCE_MAX_RESULTS` | `200` | 每个会议最多缓存的论文数，部署时通常设为 `1000` |
| `CONFERENCE_YEARS` | `5` | 会议论文回溯年数 |
| `AWARDS_PATH` | `data/awards.json` | 获奖论文清单路径 |
| `PORT` | `5000` | 本地服务端口 |
| `DISABLE_SCHEDULER` | `0` | 设为 `1` 时关闭本地后台刷新 |

GitHub Actions 中建议配置：

```text
OPENALEX_API_KEY
OPENALEX_EMAIL
```

## 获奖论文维护

获奖信息不能可靠地从引用量推断，因此使用 `data/awards.json` 人工维护。每条记录可以包含：

```json
{
  "title": "论文完整标题",
  "doi": "可选 DOI",
  "conference": "CoRL",
  "year": 2025,
  "award": "Best Paper",
  "source_url": "会议官方获奖页面"
}
```

系统优先按 DOI 匹配，其次按规范化标题匹配，只展示清单确认过的获奖论文。

## 测试

```powershell
python -m pytest
```

## 说明

arXiv 提供预印本数据；OpenAlex 提供会议元数据、引用量、摘要和单位信息；DBLP 用作会议同步的补充来源。由于外部服务偶尔会限流或返回异常，页面会在部分数据更新失败时保留已有缓存并显示异常提示。
