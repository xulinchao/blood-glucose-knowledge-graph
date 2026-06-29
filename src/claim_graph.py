#!/usr/bin/env python3
"""Topic Memory Graph — claim 历史误读与已发布版本（Phase 3）。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from claim_gate import make_claim_id

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GRAPH_PATH = PROJECT_ROOT / "data" / "knowledge" / "claim-graph.json"


def _default_graph() -> dict[str, Any]:
    return {
        "_meta": {
            "version": "1.0.0",
            "description": "主张记忆图谱：防重复谣言包装与误读升级",
            "last_updated": "",
        },
        "claims": {},
    }


def load_claim_graph() -> dict[str, Any]:
    if not GRAPH_PATH.is_file():
        return _default_graph()
    with open(GRAPH_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_claim_graph(data: dict[str, Any]) -> Path:
    GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    data.setdefault("_meta", {})
    data["_meta"]["last_updated"] = datetime.now().isoformat(timespec="seconds")
    with open(GRAPH_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return GRAPH_PATH


def get_claim_graph_penalty(claim_ids: list[str]) -> int:
    """历史 common_misreads 越多，writability 扣分越高。"""
    graph = load_claim_graph()
    claims_db = graph.get("claims") or {}
    penalty = 0
    for cid in claim_ids:
        entry = claims_db.get(cid) or {}
        misreads = entry.get("common_misreads") or []
        penalty += min(15, len(misreads) * 5)
    return penalty


def upsert_claim_from_evaluation(
    claims: list[dict[str, Any]],
    *,
    url: str = "",
    title: str = "",
) -> None:
    graph = load_claim_graph()
    claims_db = graph.setdefault("claims", {})
    for c in claims:
        cid = c.get("claim_id") or make_claim_id(c.get("claim", ""))
        entry = claims_db.setdefault(
            cid,
            {
                "claim_text": c.get("claim", ""),
                "claim_type": c.get("claim_type", ""),
                "supporting_evidence": [],
                "counter_evidence": [],
                "common_misreads": [],
                "safe_templates": [],
                "published_versions": [],
                "related_topics": [],
            },
        )
        if title and title not in entry.get("titles_seen", []):
            entry.setdefault("titles_seen", []).append(title[:120])
        if url and url not in entry.get("source_urls", []):
            entry.setdefault("source_urls", []).append(url)
    save_claim_graph(graph)


def record_published_script(
    claim_ids: list[str],
    script_id: str,
    title: str,
    *,
    safe_template: str = "",
) -> None:
    graph = load_claim_graph()
    claims_db = graph.setdefault("claims", {})
    for cid in claim_ids:
        entry = claims_db.setdefault(
            cid,
            {
                "claim_text": "",
                "supporting_evidence": [],
                "counter_evidence": [],
                "common_misreads": [],
                "safe_templates": [],
                "published_versions": [],
                "related_topics": [],
            },
        )
        versions = entry.setdefault("published_versions", [])
        versions.append(
            {
                "script_id": script_id,
                "title": title[:120],
                "published_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        if safe_template and safe_template not in entry.get("safe_templates", []):
            entry.setdefault("safe_templates", []).append(safe_template[:200])
    save_claim_graph(graph)


def record_misread(claim_id: str, misread: str) -> None:
    graph = load_claim_graph()
    claims_db = graph.setdefault("claims", {})
    entry = claims_db.setdefault(
        claim_id,
        {
            "claim_text": "",
            "supporting_evidence": [],
            "counter_evidence": [],
            "common_misreads": [],
            "safe_templates": [],
            "published_versions": [],
            "related_topics": [],
        },
    )
    misreads = entry.setdefault("common_misreads", [])
    if misread and misread not in misreads:
        misreads.append(misread[:200])
    save_claim_graph(graph)
