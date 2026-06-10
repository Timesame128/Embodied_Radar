# Embodied Radar

自动追踪 arXiv 最近 15 天具身智能论文的 Web 应用，支持本地 Flask
运行和 GitHub Pages 自动发布。

链接：https://timesame128.github.io/reach-arXiv/

## 功能

- 从 arXiv API 自动抓取最近论文，每 6 小时刷新一次
- 用具身关键词与任务子类规则进行二次筛选
- 按视觉-语言-动作、操作、导航、运动、感知、智能体等方向分类
- 展示标题、摘要、作者、日期、arXiv 分类和团队单位
- 自动提取摘要/备注中的项目与代码链接
- 一键打开 arXiv 详情、PDF、项目或代码页面
- OpenAlex 辅助补全作者团队单位；匹配失败时明确提示

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

工作流每 6 小时自动抓取一次 arXiv，并重新部署网页。GitHub 的定时任务可能有
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
- `PORT`：服务端口，默认 `5000`
- `DISABLE_SCHEDULER=1`：关闭后台自动刷新

## 测试

```powershell
python -m pytest
```
