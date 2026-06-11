# Embodied Radar

自动追踪 arXiv 最近 15 天具身智能论文的 Web 应用，支持本地 Flask
运行和 GitHub Pages 自动发布。

## 功能

- 从 arXiv API 自动抓取最近论文，每小时整点刷新一次
- 用具身关键词与任务子类规则进行二次筛选
- 按视觉-语言-动作、操作、导航、运动、感知、智能体等方向分类
- 展示标题、摘要、作者、日期、arXiv 分类和团队单位
- 自动提取摘要/备注中的项目与代码链接
- 一键打开 arXiv 详情、PDF、项目或代码页面
- OpenAlex 辅助补全作者团队单位；匹配失败时明确提示
- 识别并筛选 CoRL、ICRA、RSS、IROS、CVPR、ICLR、NeurIPS（NIPS）、ICML、ICCV 论文
- arXiv 与各会议独立成区，支持时间、引用量排序及年份、引用量区间筛选
- Best Paper、Outstanding Paper、Honorable Mention 等荣誉通过官方清单人工核验

## 启动

```powershell
python -m pip install -r requirements.txt
python app.py
```

访问 <http://127.0.0.1:5000>，首次启动后会自动同步，也可以点击“立即刷新”。

## 发布到 GitHub Pages

仓库已经包含 `.github/workflows/deploy-pages.yml`：

1. 把项目推送到 GitHub 仓库的 `main` 或 `master` 分支。
2. 打开仓库 `Settings → Pages`。
3. 在 `Build and deployment` 的 `Source` 中选择 `GitHub Actions`。
4. 打开 `Actions`，手动运行一次 `Update papers and deploy Pages`。

部署完成后，页面地址通常是：

```text
https://你的用户名.github.io/仓库名/
```

工作流每小时整点自动抓取一次 arXiv，并重新部署网页。GitHub 的定时任务可能有
少量延迟，也可以随时在 Actions 页面点击 `Run workflow` 手动更新。

本地预览静态站点：

```powershell
python build_static.py
python -m http.server 8000 --directory _site
```

## 配置

环境变量：

- `PAPER_DAYS`：保留天数，默认 `15`
- `REFRESH_INTERVAL_MINUTES`：自动刷新间隔，默认 `360`
- `ARXIV_MAX_RESULTS`：每次 arXiv 查询上限，默认 `300`
- `OPENALEX_EMAIL`：可选，OpenAlex polite pool 邮箱
- `OPENALEX_API_KEY`：OpenAlex API Key，用于同步会议论文和引用量
- `CONFERENCE_MAX_RESULTS`：每个会议最多缓存的论文数，默认 `200`，最高 `1000`
- `CONFERENCE_YEARS`：会议论文回溯年数，默认 `5`
- `AWARDS_PATH`：奖项清单路径，默认 `data/awards.json`
- `PORT`：服务端口，默认 `5000`
- `DISABLE_SCHEDULER=1`：关闭后台自动刷新

## 测试

```powershell
python -m pytest
```

## 会议与奖项数据

会议论文、正式 venue、发表年份和引用量来自 OpenAlex。GitHub Pages 每 6 小时自动刷新，
并把成功获取的 `data/papers.json` 提交回仓库。部署时请在仓库
`Settings → Secrets and variables → Actions` 中添加 `OPENALEX_API_KEY`；工作流会在每次
更新时刷新引用量。

奖项不能由引用量可靠推断，因此使用 `data/awards.json` 人工维护。每条记录可填写：

```json
{
  "title": "论文完整标题",
  "doi": "可选 DOI",
  "conference": "CoRL",
  "year": 2025,
  "award": "Best Paper",
  "source_url": "会议官方奖项页面"
}
```

系统优先按 DOI、其次按规范化标题匹配，只展示经过清单确认的获奖论文。
