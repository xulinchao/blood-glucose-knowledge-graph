# Quartz 笔记发布

本仓库采用 **混合部署**：根路径是 HTML 工具箱，Markdown 笔记由 Quartz 生成在 `/notes/` 路径。

## 目录

| 路径 | 用途 |
|------|------|
| `content/` | Obsidian / Markdown 笔记（Quartz 内容源） |
| `index.html` | 工具箱首页 |
| `site/`、`data/`、`reports/` | 交互式 HTML 工具与数据 |
| `quartz.config.yaml` | Quartz 站点配置 |

## 本地预览

```bash
npm ci
npm run plugins:install
npm run build:notes -- --serve
```

笔记预览：http://localhost:8080/notes/

工具箱预览：`python -m http.server 8080` → http://localhost:8080/

## 发布流程

1. 把 Obsidian 笔记放进 `content/`
2. `git push origin main`
3. GitHub Actions 自动构建并部署

## 线上地址

| 页面 | 地址 |
|------|------|
| 工具箱首页 | https://bg.purpleiris.cn/ |
| 知识笔记 | https://bg.purpleiris.cn/notes/ |

## GitHub Pages 设置

仓库 Settings → Pages → Source 选 **GitHub Actions**。

## Obsidian 对接

把 `.md` 笔记放入 `content/`，支持 `[[双链]]`、标签、搜索、图谱。

Markdown 用户内容 **只维护 `content/`**，不要在 `docs/` 重复存放。
