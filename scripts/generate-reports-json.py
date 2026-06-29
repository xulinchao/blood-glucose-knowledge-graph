#!/usr/bin/env python3
"""扫描 research-daily 生成首页用的 reports.json（本地预览 / CI 均可调用）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_DIR = ROOT / "research-daily"
QUARTZ_DIR = ROOT / "public" / "notes" / "research-daily"
OUT = ROOT / "reports.json"

TITLE = "血糖控糖热点监控日报"


def scan_dir(directory: Path, url_prefix: str) -> list[dict]:
    if not directory.is_dir():
        return []
    rows = []
    for path in directory.glob("*-日报.html"):
        date = path.stem.replace("-日报", "")
        rows.append({"date": date, "title": TITLE, "url": url_prefix + path.name})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows


def main() -> int:
    payload = {
        "html_reports": scan_dir(HTML_DIR, "research-daily/"),
        "quartz_reports": scan_dir(QUARTZ_DIR, "notes/research-daily/"),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  HTML: {len(payload['html_reports'])} · Quartz: {len(payload['quartz_reports'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
