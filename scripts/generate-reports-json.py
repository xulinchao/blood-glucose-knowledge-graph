#!/usr/bin/env python3
"""扫描 research-daily 生成首页用的 reports.json（本地预览 / CI 均可调用）。"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HTML_DIR = ROOT / "research-daily"
DEFAULT_QUARTZ_DIR = ROOT / "public" / "notes" / "research-daily"
DEFAULT_OUT = ROOT / "reports.json"

MONITOR_TITLE = "血糖控糖热点监控日报"
BRIEF_TITLE = "血糖控糖精选日报"
HARVEST_TITLE = "选题采集日报"

DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(?:精选|采集)?日报$")


def scan_html_reports(directory: Path, url_prefix: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {
        "html_reports": [],
        "brief_reports": [],
        "harvest_reports": [],
    }
    if not directory.is_dir():
        return out
    for path in sorted(directory.glob("*.html"), reverse=True):
        m = DATE_RE.match(path.stem)
        if not m:
            continue
        date = m.group(1)
        row = {"date": date, "url": url_prefix + path.name}
        if path.stem.endswith("-精选日报"):
            row["title"] = BRIEF_TITLE
            out["brief_reports"].append(row)
        elif path.stem.endswith("-采集日报"):
            row["title"] = HARVEST_TITLE
            out["harvest_reports"].append(row)
        elif path.stem.endswith("-日报"):
            row["title"] = MONITOR_TITLE
            out["html_reports"].append(row)
    return out


def scan_quartz(directory: Path, url_prefix: str) -> list[dict]:
    if not directory.is_dir():
        return []
    rows = []
    for path in directory.glob("*-日报.md"):
        date = path.stem.replace("-日报", "")
        rows.append({"date": date, "title": MONITOR_TITLE, "url": url_prefix + path.name})
    rows.sort(key=lambda x: x["date"], reverse=True)
    return rows


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="生成首页 reports.json")
    parser.add_argument("--html-dir", type=Path, default=DEFAULT_HTML_DIR)
    parser.add_argument("--quartz-dir", type=Path, default=DEFAULT_QUARTZ_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    scanned = scan_html_reports(args.html_dir, "research-daily/")
    payload = {
        "html_reports": scanned["html_reports"],
        "brief_reports": scanned["brief_reports"],
        "harvest_reports": scanned["harvest_reports"],
        "quartz_reports": scan_quartz(args.quartz_dir, "notes/research-daily/"),
    }
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    print(
        f"  监控: {len(payload['html_reports'])} · 精选: {len(payload['brief_reports'])} · "
        f"采集: {len(payload['harvest_reports'])} · Quartz: {len(payload['quartz_reports'])}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
