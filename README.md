# 血糖知识图谱

面向血糖/控糖领域的 AIGC 内容创作工具箱 — 选题发现 · 脚本生成 · Prompt 设计 · 知识笔记 · 日报监控。

线上地址：https://bg.purpleiris.cn/

## 项目结构

```text
血糖知识图谱/
├── index.html              # 工具箱首页
├── content/                # Quartz 笔记源（Obsidian / Markdown）
├── site/                   # 静态交互工具（Prompt 生成器、口播稿生成器）
├── data/                   # 唯一数据源
│   ├── foods/gi-database.json
│   ├── knowledge/
│   ├── discovered-topics.json
│   └── exports/
├── reports/methodology/    # AIGC 方法论报告
├── research-daily/         # 监控日报（HTML）
├── src/                    # Python 脚本
├── docs/                   # 工程文档
├── quartz/                 # Quartz 框架
└── scripts/                # 部署与本地脚本
```

## 本地开发

### 工具箱（HTML 工具）

需要本地 HTTP 服务（不能直接双击 HTML）：

```bash
# Windows
start-server.bat

# 或 Python
python -m http.server 8080
```

访问 http://localhost:8080/

### Quartz 笔记站

```bash
npm ci
npm run plugins:install
npm run build:notes -- --serve
```

笔记预览：http://localhost:8080/notes/

### Python Prompt 生成器

```bash
python src/generate_prompts.py
```

输出到 `out/prompts/`（已 gitignore，不提交）

## 部署

推送到 `main` 分支后，GitHub Actions 自动：

1. 构建 Quartz 笔记站 → `/notes/`
2. 合并工具箱静态文件
3. 部署到 GitHub Pages

详见 [docs/Quartz部署说明.md](docs/Quartz部署说明.md)

## 数据说明

- **食物数据**：统一使用 `data/foods/gi-database.json`（145 种）
- **知识主题**：`data/knowledge/topics.json`
- **口播选题库**：`data/knowledge/script-topics.json`
- **选题发现**：`data/discovered-topics.json`

## TraeWork

TraeWork 与本仓库共用数据与真实性规则。每日采集跑 `scripts/run-daily-harvest.bat`（含**精选日报**）；Agent 查热点见 `.cursor/skills/blood-glucose-daily-brief/SKILL.md`；深度监控见 [docs/TraeWork.md](docs/TraeWork.md)。

## 更新笔记

1. 在 `content/` 添加或编辑 Markdown
2. `git push origin main`
3. 约 2 分钟后在 https://bg.purpleiris.cn/notes/ 查看
