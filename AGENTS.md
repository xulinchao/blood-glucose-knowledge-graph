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

## Build & Development

```bash
# Python prompt generation
python src/generate_prompts.py

# Local toolbox preview (requires HTTP server)
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
