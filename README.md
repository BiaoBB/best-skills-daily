# AI Agent 技能每日选品手账（自动更新版）

每天北京时间早上 10:00 自动从 [LinklyAI/best-skills](https://github.com/LinklyAI/best-skills) 拉取最新榜单数据，结合本地中文词典生成单文件静态网页，并自动发布到 GitHub Pages。

## 文件说明

- `build.py`：纯 Python 标准库构建脚本（零第三方依赖），负责拉取最新 CSV、识别同源马甲、匹配中文词典并生成 `index.html`。
- `zh_dict.json`：本地中文大白话词典（0 成本，可随时手动增补新技能的中文说明）。
- `template.html`：单文件离线网页模板（无外部 CDN 依赖，电脑和 iPad 均可顺畅打开）。
- `.github/workflows/daily-update.yml`：GitHub Actions 每日定时构建与 Pages 发布配置。

## 本地手动测试

```bash
python build.py
```

运行后会在当前目录生成最新的 `index.html`，双击即可在浏览器打开。

## 数据协议

Data from Best Skills (https://github.com/LinklyAI/best-skills) by @BlueeonY — CC BY 4.0
