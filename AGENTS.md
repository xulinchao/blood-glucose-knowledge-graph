# Repository Guidelines

## Project Structure

```text
血糖知识图谱/
├── index.html              # Toolbox landing page
├── content/                # Quartz notes source (Obsidian / Markdown)
├── site/                   # Static interactive HTML tools
├── data/                   # Single source of truth for datasets
│   ├── foods/gi-database.json
│   ├── knowledge/
│   ├── discovered-topics.json
│   └── exports/
├── reports/methodology/    # AIGC methodology report
├── research-daily/         # Daily monitoring reports (HTML)
├── src/                    # Python generators
├── docs/                   # Engineering docs (not user notes)
├── quartz/                 # Quartz v5 framework
├── scripts/                # Deploy and refactor scripts
└── tests/                  # Python tests
```

## Components

- `data/foods/gi-database.json` — 145 foods with GI/GL/nutrition data
- `data/knowledge/topics.json` — 12 blood-glucose knowledge topics
- `site/prompt-generator.html` — Prompt generator (loads JSON via fetch)
- `site/script-generator.html` — Script generator for short-video platforms
- `content/` — Markdown notes published via Quartz at `/notes/`
- `src/generate_prompts.py` — CLI prompt generator
- `src/generate_script.py` — CLI 口播文案生成（选题 + GI/知识库增强 + 归档 + 安全 Lint）
- `src/claim_gate.py` — 主张拆解与 Risk Gate（可写性否决）
- `src/script_safety.py` — 口播生成后 Lint（与 Gate 禁止词同源）
- `data/knowledge/claim-graph.json` — 主张记忆图谱（误读升级 / 已发版本）
- `site/script-bridge.js` — 浏览器端选题资料桥接（与 `script_knowledge.py` 规则一致）

## Build & Development

```bash
# Python prompt generation
python src/generate_prompts.py

# 口播文案（选题库 / 采集条目）
python src/generate_script.py --topic-id disc-001 --save
python src/generate_script.py --from-harvest --url "原贴URL" --save

# Local toolbox preview (requires dev server for source fetch API)
python scripts/dev_server.py 8080

# Plain static preview (no /api/fetch-source)
python -m http.server 8080

# Quartz notes preview
npm ci && npm run plugins:install && npm run build:notes -- --serve
```

Python: `C:\Users\xulinchao\.workbuddy\binaries\python\versions\3.13.12\python.exe`

## Deployment

Push to `main` triggers GitHub Actions (`.github/workflows/deploy.yml`):

1. Build Quartz → `public/notes/`
2. Merge toolbox assets via `scripts/merge-static.sh`
3. Deploy to GitHub Pages at `bg.purpleiris.cn`

GitHub Pages source must be **GitHub Actions** (not branch deploy).

## Testing

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Commit Guidelines

Use concise imperative messages, e.g. `Add gi-database loader to prompt generator`.

Pull requests should include purpose, key changes, and test evidence.

## Agent Instructions

Do not treat the user's current understanding as the quality ceiling. Meet the requested scope, then call out gaps against professional repository, medical-data, and software-engineering standards when relevant.

Markdown user content lives in `content/` only — do not duplicate into `docs/`.

## 选题与内容真实性（非医生创作者）

本仓库面向**血糖/控糖科普**，维护者**非执业医生**。Agent 处理选题、日报、写稿、采集时**必须**遵守以下规则（与 `src/claim_gate.py` + `src/daily_topic_harvest.py` 一致）。

### Risk Gate（可写性否决权）

**热度与可写性已分权**（`heat_score` vs `writability_score`）：

- `src/claim_gate.py` 在采集时对每条主张做规则拆解与 Gate 裁决
- **`gate.passed`** 拥有可写性否决权；高 `heat_score` **不得**单独决定能否写稿
- 精选日报 Schema **2.0** 字段：`writing_safety`、`gate`、`propagation`、`cognitive_conflict`
- 口播生成后须经 `src/script_safety.py` Lint（与 Gate 禁止词同源）

Agent 读精选 JSON 时优先看：`gate.passed`、`forbidden_expressions`、`required_hedges`、`agent_hints.top_script_angles.why_selected`。

### 第一性原理（什么算「可用」）

1. **可验证**：每条主张应能追溯到原贴 URL、指南或可查数据；无法追溯则不得写成事实句。
2. **证据层级**（A→E，高→低）：
   - **A**：政府/期刊/正式指南（如 `nhc.gov.cn`、WHO、NEJM）
   - **B**：医疗专业平台（丁香、好大夫等）
   - **C**：可识别医疗相关身份的作者（仍须核对资质）
   - **D**：普通 UGC（B站/小红书/知乎等）— 默认**仅选题钩子**
   - **E**：夸张/绝对化/离题噪音 — **不可当内容依据**
3. **伤害性**：涉及用药、剂量、替代就医、治愈承诺时，必须降级为「讨论话题」并提示就医。
4. **动机**：识别带货、恐惧营销、绝对化表述；高互动 ≠ 高真实性。

### 对抗性审核（Red Team）

处理任何选题或原贴前，**假设作者在最大化传播而非最大化真相**，主动检查：

| 标记 | 触发示例 | Agent 动作 |
|------|----------|------------|
| `sensational` | 根治、神药、被骗、一夜、百分百 | 仅作辟谣/钩子，不复述为事实 |
| `absolute_claim` | 所有人都、保证逆转、永不复发 | 拒绝写进口播正文 |
| `commercial_hook` | 卖、链接、优惠券 + 低证据 | 标注动机，不帮带货 |
| `off_topic_noise` | X 上 crypto/trader 等 | 丢弃，不进入选题 |

### `use_as` 用法（写稿前必看）

| 值 | 含义 | 口播要求 |
|----|------|----------|
| `cite_directly` | 可引用来源 | 加「非医疗建议」+ 原链接 |
| `verify_before_script` | 写稿前回源核实 | 关键数字必须二次查证 |
| `hook_only` | 只反映「大家在聊什么」 | **不得**把标题观点当医学结论 |

### 自动入库门槛

`discovered-topics.json` 仅收录同时满足：`gate.passed`、证据非 E、`use_as` 可写稿、`writability_score`≥62、真实性≥50。  
`hook_only` 条目可出现在采集日报，**默认不自动入库**。

### 数据采集

- 一键采集：`scripts/run-daily-harvest.bat` 或 `python src/daily_topic_harvest.py`
- 输出：`research-daily/*-采集日报.html`、`data/exports/daily-harvest-*.json`
- 平台：权威来源、B站、小红书、知乎、YouTube、X（健康过滤）、Reddit、Exa
- 年轻人向默认关键词见 `src/daily_topic_harvest.py` 中 `YOUTH_KEYWORDS`

### 口播底线（每条必达）

> 这是网上讨论 / 某来源说法，个体情况请咨询医生，不构成医疗建议。

Agent 生成口播稿、选题角度、日报摘要时，对 D/E 级与 `hook_only` 内容**不得**使用「研究表明你一定…」「只要…就能治愈」等确定性医学断言。

### Script Safety Compiler

- 生成口播：`python src/generate_script.py` 自动 Lint；未通过默认拒绝 `--save`（可用 `--force`）
- 规则来源：`claim_gate.FORBIDDEN_PATTERNS` 与 `script_safety.py` 同源
- 浏览器端：`site/script-bridge.js` 的 `lintScriptText` 对齐 Python 规则

## TraeWork 与本仓库

TraeWork 与本仓库 Cursor/Agent **共用同一套数据与规则**（`AGENTS.md` + `.cursor/skills/blood-glucose-topic-authenticity/SKILL.md` + `.cursor/skills/blood-glucose-daily-brief/SKILL.md`）。

### 三类日报（勿混淆）

| 类型 | 生成方式 | 输出 | 用途 |
|------|----------|------|------|
| **采集日报** | 定时跑 `scripts/run-daily-harvest.bat` | `research-daily/YYYY-MM-DD-采集日报.html` | 多平台原贴全量 + 证据层级 |
| **精选日报** | 采集后自动 `curate_daily_brief.py` | `research-daily/YYYY-MM-DD-精选日报.html` + `data/exports/daily-brief-*.json` | **Agent 默认读**；时间线 ~12 条 |
| **监控日报** | TraeWork 任务（深度解读，可选） | HTML：`research-daily/YYYY-MM-DD-日报.html` · MD：`content/research-daily/YYYY-MM-DD-日报.md` | 政策核实、口播建议；**页面只展示 HTML，MD 进笔记** |

TraeWork 写监控日报时：

1. **先读** 当日 `data/exports/daily-brief-YYYY-MM-DD.json`（精选），再按需读 `daily-harvest-*.json`
2. **必须** 对引用主张做对抗性审核（见上节）；二手信息标「待核实」
3. **不得** 把 `hook_only` / E 级条目写成已核实事实
4. 监控日报：**HTML** 仅 `research-daily/*-日报.html`；**MD** 仅 `content/research-daily/*-日报.md`（Quartz）。不要在 `research-daily/` 留监控日报的 `.md`
5. 产出 HTML 首行保留 `<!-- Generated by Trae Work -->` 约定

### TraeWork 推荐定时任务

```text
任务1（每日）：scripts/run-daily-harvest.bat  → 含精选日报
任务2（可选，TraeWork Agent）：读精选 JSON → 写监控日报 → 更新 content/research-daily 若需发笔记
```

TraeWork 系统提示词建议附加：

```text
工作目录：血糖知识图谱仓库根目录。遵守 AGENTS.md「选题与内容真实性」。
查今日热点先读 data/exports/latest-brief.json（见 blood-glucose-daily-brief Skill）。
维护者非医生：口播与日报仅科普讨论，不构成医疗建议。
```

详见 [docs/TraeWork.md](docs/TraeWork.md)。
