#!/usr/bin/env python3
"""拉取来源字幕/网页正文并写入缓存，供写稿器使用。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_fetcher import fetch_source, fetch_sources  # noqa: E402
from script_knowledge import find_discovered_topic, load_discovered_topics  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="拉取视频字幕 / 网页正文")
    parser.add_argument("--url", action="append", help="来源 URL，可重复")
    parser.add_argument("--topic-id", help="从 discovered-topics 读取 source_urls")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    urls = list(args.url or [])
    if args.topic_id:
        topic = find_discovered_topic(args.topic_id)
        if not topic:
            print(f"未找到选题 {args.topic_id}", file=sys.stderr)
            return 1
        urls.extend(topic.get("source_urls") or [])

    urls = [u.strip() for u in urls if u and u.strip()]
    if not urls:
        print("请提供 --url 或 --topic-id", file=sys.stderr)
        return 1

    bundle = fetch_sources(urls, use_cache=not args.no_cache)
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        print(f"拉取 {len(bundle['items'])} 个来源，提炼 {len(bundle['key_points'])} 条要点")
        for item in bundle["items"]:
            st = item.get("status") or ("ok" if item.get("ok") else "error")
            print(f"\n• {item.get('url')}")
            print(f"  类型={item.get('type')} 状态={st} 要点={len(item.get('key_points') or [])}")
            if item.get("note"):
                print(f"  提示：{item['note']}")
            if item.get("error"):
                print(f"  错误：{item['error']}")
        print("\n--- 合并要点 ---")
        for i, p in enumerate(bundle["key_points"], 1):
            print(f"{i}. {p}")
        if bundle["errors"]:
            print("\n--- 失败 ---")
            for e in bundle["errors"]:
                print(e)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
