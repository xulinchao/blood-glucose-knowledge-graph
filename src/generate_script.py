#!/usr/bin/env python3
"""
口播文案生成器 — 从选题资料 + GI/知识库 生成可核实口播稿

示例:
    python src/generate_script.py --topic-id disc-001
    python src/generate_script.py --from-harvest --url "https://www.bilibili.com/video/..."
    python src/generate_script.py --title "胰岛素抵抗怎么判断" --angle "..." --save
    python src/generate_script.py --topic-id disc-001 --save --mark-script writing
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

from script_knowledge import (  # noqa: E402
    CAT_MAP,
    build_ai_prompt,
    build_script_document,
    enrich_data_ref,
    find_discovered_topic,
    find_harvest_item,
    harvest_item_meta,
    harvest_meta_from_topic,
    load_latest_harvest,
    merge_source_key_points,
    save_script_record,
    update_discovered_topic_status,
)
from source_fetcher import fetch_sources  # noqa: E402


def resolve_topic(args: argparse.Namespace) -> tuple[dict, dict, str, str, list[str]]:
    title = (args.title or "").strip()
    angle = (args.angle or "").strip()
    meta: dict = {}
    cat = args.cat or "myth"
    topic_id = args.topic_id

    if args.topic_id:
        topic = find_discovered_topic(args.topic_id)
        if not topic:
            raise SystemExit(f"未找到选题: {args.topic_id}")
        title = title or topic.get("title", "")
        angle = angle or topic.get("angle", "")
        cat = args.cat or CAT_MAP.get(topic.get("category", ""), "myth")
        meta = harvest_meta_from_topic(topic)
        topic_id = topic["id"]
    elif args.from_harvest:
        harvest = load_latest_harvest()
        if not harvest:
            raise SystemExit("未找到 daily-harvest 导出文件")
        item = find_harvest_item(harvest, url=args.url or "", title=args.title or "")
        if not item:
            raise SystemExit("在最新采集中未匹配到条目（需 --url 或 --title）")
        title = title or item.get("title", "")
        angle = angle or item.get("snippet", "")
        cat = args.cat or CAT_MAP.get(item.get("category", ""), "myth")
        meta = harvest_item_meta(item)
        if item.get("url") and not meta.get("source_urls"):
            meta["source_urls"] = [item["url"]]
        topic_id = args.topic_id
    else:
        if not title:
            raise SystemExit("请提供 --topic-id、--from-harvest，或 --title")
        meta = {
            "use_as": args.use_as or "verify_before_script",
            "evidence_tier": args.evidence_tier or "D",
            "creator_note": args.creator_note or "手动选题，写稿前请补充来源",
            "source_urls": [u.strip() for u in (args.source_url or "").split(",") if u.strip()],
        }
        topic_id = args.topic_id

    extra = [ln.strip() for ln in (args.data or "").split("\n") if ln.strip()]
    enriched = enrich_data_ref(title, angle=angle, snippet=angle, extra_lines=extra)
    data_ref = enriched["data_ref"]
    source_bundle = None
    if args.fetch_sources and meta.get("source_urls"):
        source_bundle = fetch_sources(meta["source_urls"])
        data_ref = merge_source_key_points(data_ref, source_bundle)
    return (
        {"title": title, "angle": angle, "category": cat, "id": topic_id},
        meta,
        cat,
        topic_id or "",
        data_ref,
        source_bundle,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="血糖口播文案生成器")
    parser.add_argument("--topic-id", help="discovered-topics.json 中的 id")
    parser.add_argument("--from-harvest", action="store_true", help="从最新 daily-harvest 条目生成")
    parser.add_argument("--url", help="匹配 harvest 条目 URL")
    parser.add_argument("--title", help="选题标题")
    parser.add_argument("--angle", help="切入角度 / 摘要")
    parser.add_argument("--cat", choices=list(set(CAT_MAP.values())))
    parser.add_argument("--platform", default="dy", choices=["dy", "xhs", "bili"])
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--persona", default="friendly", choices=["friendly", "expert", "personal", "surprise"])
    parser.add_argument("--data", help="额外核心数据，换行分隔")
    parser.add_argument("--use-as", dest="use_as")
    parser.add_argument("--evidence-tier", dest="evidence_tier")
    parser.add_argument("--creator-note", dest="creator_note")
    parser.add_argument("--source-url", dest="source_url", help="逗号分隔来源链接")
    parser.add_argument("--save", action="store_true", help="写入 data/scripts/")
    parser.add_argument("--mark-script", dest="mark_script", choices=["pending", "writing", "done"])
    parser.add_argument("--mark-publish", dest="mark_publish", choices=["pending", "published"])
    parser.add_argument("--output", choices=["text", "json", "prompt"], default="text")
    parser.add_argument("--fetch-sources", dest="fetch_sources", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--list-topics", action="store_true", help="列出 discovered-topics 可写稿条目")
    args = parser.parse_args()

    if args.list_topics:
        from script_knowledge import load_discovered_topics

        data = load_discovered_topics()
        for t in data.get("topics", []):
            hm = t.get("harvest_meta") or {}
            use_as = hm.get("use_as") or (hm.get("authenticity") or {}).get("use_as", "?")
            print(f"{t.get('id')}\t{t.get('script_status')}\t{use_as}\t{t.get('title', '')[:50]}")
        return

    topic_info, meta, cat, topic_id, data_ref, _source_bundle = resolve_topic(args)
    doc = build_script_document(
        title=topic_info["title"],
        platform=args.platform,
        cat=cat,
        duration=args.duration,
        persona=args.persona,
        data_ref=data_ref,
        meta=meta,
        angle=topic_info.get("angle", ""),
    )

    if args.output == "json":
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    elif args.output == "prompt":
        print(build_ai_prompt(doc))
    else:
        print(doc["full_text"])
        print("\n--- 核实清单 ---")
        for item in doc["verify_checklist"]:
            mark = "必" if item.get("required") else "选"
            print(f"[{mark}] {item['text']}")

    if args.save:
        saved = save_script_record(doc, topic_id=topic_id or None)
        print(f"\n已保存: {saved['path']}", file=sys.stderr)
        if topic_id:
            update_discovered_topic_status(
                topic_id,
                script_status=args.mark_script or "writing",
                publish_status=args.mark_publish,
                script_file=saved["path"],
            )


if __name__ == "__main__":
    main()
