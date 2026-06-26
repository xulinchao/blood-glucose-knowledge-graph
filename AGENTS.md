# Repository Guidelines

## Project Structure & Module Organization

This repository is currently an early-stage workspace. Keep the root focused on project metadata and documentation. Place production source code under `src/`, tests under `tests/`, reusable data or knowledge-graph inputs under `data/`, and generated artifacts under `out/` or `dist/`. Use `docs/` for design notes, schema explanations, and research references.

Recommended layout:

```text
src/            Application code, prompt generators
data/           Curated blood-glucose knowledge inputs (foods, topics)
docs/           Architecture and domain notes
out/prompts/    Generated AI image prompts (JSON + Markdown)
```

Current project components:
- `data/foods/` — 28 种常见食物的 GI/GL/营养/食用建议数据，带 JSON Schema
- `data/knowledge/` — 12 个血糖知识主题（基础概念/病理/饮食/运动/监测）
- `src/templates/prompts.json` — 8 套 Prompt 模板（卡片/对比/象限图/曲线图等）
- `src/generate_prompts.py` — Prompt 生成器，支持 MJ/DALL·E 双格式

## Build, Test, and Development Commands

```bash
# 生成全部 Prompt（食物 + 知识，MJ + DALL·E 双格式）
python src/generate_prompts.py

# 仅生成食物卡片 Prompt
python src/generate_prompts.py --type food

# 仅生成知识卡片 Prompt
python src/generate_prompts.py --type knowledge

# 指定输出格式
python src/generate_prompts.py --output json   # JSON
python src/generate_prompts.py --output md     # Markdown

# 指定平台
python src/generate_prompts.py --format mj     # Midjourney
python src/generate_prompts.py --format dalle  # DALL·E 3
```

Python environment: use the managed Python at
`C:\Users\xulinchao\.workbuddy\binaries\python\versions\3.13.12\python.exe`

No external dependencies required — only Python stdlib (json, argparse, pathlib).

If scripts require local configuration, provide a checked-in example such as `.env.example` and never commit secrets.

## Coding Style & Naming Conventions

Use clear, domain-oriented names. Prefer English identifiers for code and stable Chinese or bilingual labels only where they represent user-facing medical concepts. Use `snake_case` for Python files and functions, `camelCase` for JavaScript/TypeScript variables, and `PascalCase` for classes and React components. Keep modules small and organized by responsibility, for example `src/ingest/`, `src/schema/`, and `src/export/`.

Format code with the formatter standard for the chosen stack, such as `black` for Python or `prettier` for TypeScript. Add formatter and lint commands once the toolchain exists.

## Testing Guidelines

Add tests with every non-trivial behavior change. Name tests after observable behavior, not implementation details, for example `test_normalizes_fasting_glucose_unit.py`. For knowledge-graph logic, include fixtures covering units, aliases, source attribution, and conflicting medical claims. Avoid relying on live network calls in tests; use local fixtures.

## Commit & Pull Request Guidelines

This directory is not currently a Git repository, so no local commit convention is available. Use concise imperative commit messages, for example `Add glucose unit normalization`. Pull requests should include a short purpose statement, key implementation notes, test evidence, and screenshots or sample outputs when generated files or visual reports change.

## Agent-Specific Instructions

Do not treat the user's current understanding as the quality ceiling. Meet the requested scope, then call out gaps against professional repository, medical-data, and software-engineering standards when relevant.
