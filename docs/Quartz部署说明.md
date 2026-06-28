# Quartz 笔记发布

本仓库采用 **混合部署**：根路径是 HTML 工具箱，Markdown 笔记由 Quartz 生成在 `/notes/` 路径。

## 目录

| 路径 | 用途 |
|------|------|
| `content/` | Obsidian / Markdown 笔记（Quartz 内容源） |
| `index.html` | 工具箱首页 |
| `out/`、`data/` | 交互式 HTML 工具 |
| `quartz.config.yaml` | Quartz 站点配置 |

## 本地预览

```bash
npm ci
npx quartz plugin install
npx quartz build --serve
```

笔记预览：http://localhost:8080/notes/

## 发布流程

1. 把 Obsidian 笔记放进 `content/`（或 symlink 整个 vault）
2. `git add . && git commit && git push origin main`
3. GitHub Actions 自动：构建 Quartz → 合并工具箱静态文件 → 部署到 Pages

## 线上地址

| 页面 | 地址 |
|------|------|
| 工具箱首页 | https://bg.purpleiris.cn/ |
| 知识笔记 | https://bg.purpleiris.cn/notes/ |

## GitHub Pages 设置

仓库 Settings → Pages → Source 选 **GitHub Actions**（不是 Deploy from branch）。

## Obsidian 对接

两种方式：

1. **复制**：把 vault 里的 `.md` 复制到 `content/`
2. **符号链接**（Windows 需开发者模式）：`content` 指向你的 Obsidian vault 子目录

Quartz 支持 `[[双链]]`、标签、搜索、图谱，详见 https://quartz.jzhao.xyz/
