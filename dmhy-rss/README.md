# DMHY RSS

动漫花园（DMHY）字幕组发布列表的**自建 RSS 生成器**，通过 GitHub Actions 定时抓取并自动更新 feed 文件，订阅地址永久可用。

默认订阅 VCB-Studio（team_id=581）的最新发布。

## 部署到 GitHub

1. 在 GitHub 新建一个仓库（如 `dmhy-rss`），Public 公开仓库。
2. 把本目录所有文件推送到仓库默认分支 `main`：
   ```bash
   git init
   git add .
   git commit -m "init"
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/dmhy-rss.git
   git push -u origin main
   ```
3. 推送后 Actions 会自动触发一次（也可在 Actions 页面手动 Run workflow）。

## 订阅地址

Actions 每 30 分钟运行一次，把最新发布写入 `dmhy_feed.xml` 并提交回仓库。

- **Raw 地址（推荐，开箱即用）**：
  ```
  https://raw.githubusercontent.com/<你的用户名>/dmhy-rss/main/dmhy_feed.xml
  ```
  把该地址填进任意 RSS 阅读器（Inoreader / Feedly / Reeder / Folo 等）即可订阅。

- **GitHub Pages 地址（可选，更稳定）**：
  在仓库 Settings → Pages 中，把 Source 设为 `Deploy from a branch`、分支选 `main`、目录选 `/ (root)`，保存后访问：
  ```
  https://<你的用户名>.github.io/dmhy-rss/dmhy_feed.xml
  ```

## 本地运行

```bash
pip install -r requirements.txt
python dmhy_rss.py                # 增量抓取并生成 dmhy_feed.xml
python dmhy_rss.py --force        # 忽略去重，重新生成全部条目
```

## 自定义订阅对象

编辑 `dmhy_rss.py` 顶部的 `LIST_URL`，可切换其他字幕组 / 关键词 / 分类：

- 换字幕组：`team_id=581` 改为目标组 ID（在动漫花园点字幕组标签即可在地址栏看到）
- 换关键词：`keyword=` 后填关键词
- 换分类：`sort_id=0` 改为对应分类 ID

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `dmhy_rss.py` | 抓取 + 解析 + 生成 RSS 主脚本 |
| `dmhy_feed.xml` | 生成的 feed（Actions 自动更新，勿手改） |
| `dmhy_state.json` | 已见条目去重状态（保留在仓库中实现增量） |
| `.github/workflows/rss.yml` | 定时任务：每 30 分钟抓取并提交 |
