#!/usr/bin/env python3
"""口播安全编译器 — 生成后 Lint，规则与 claim_gate 同源。"""

from __future__ import annotations

import re
from typing import Any

from claim_gate import CAUSAL_JUMP_PATTERNS, DEFAULT_HEDGES, FORBIDDEN_PATTERNS


def lint_script_text(
    text: str,
    *,
    meta: dict[str, Any] | None = None,
    write_mode: str = "verify_before_script",
) -> dict[str, Any]:
    meta = meta or {}
    violations: list[dict[str, str]] = []
    suggestions: list[str] = []

    for pattern, label in FORBIDDEN_PATTERNS:
        if re.search(pattern, text, re.I):
            violations.append({"type": "forbidden_pattern", "label": label, "pattern": pattern})

    for pattern, label in CAUSAL_JUMP_PATTERNS:
        if re.search(pattern, text, re.I):
            violations.append({"type": "causal_jump", "label": label, "pattern": pattern})

    tier = meta.get("evidence_tier") or "D"
    allowed_frame = meta.get("allowed_frame") or ""
    required_hedges = meta.get("required_hedges") or meta.get("gate", {}).get("required_hedges") or []
    if not required_hedges:
        required_hedges = list(DEFAULT_HEDGES)

    needs_hedge = (
        write_mode == "hook_only"
        or tier in ("D", "E")
        or allowed_frame == "discussion_only"
    )
    if needs_hedge and required_hedges:
        if not any(h in text for h in required_hedges):
            violations.append(
                {
                    "type": "missing_hedge",
                    "label": "缺少非确定性降权表述",
                    "pattern": "|".join(required_hedges[:2]),
                }
            )
            suggestions.append(f"建议加入：「{required_hedges[0]}」或「{required_hedges[1]}」")

    forbidden_exprs = meta.get("forbidden_expressions") or meta.get("gate", {}).get("forbidden_expressions") or []
    for expr in forbidden_exprs:
        if expr and expr in text:
            violations.append(
                {"type": "gate_forbidden", "label": f"含 Gate 禁止表达「{expr}」", "pattern": expr}
            )
            suggestions.append(f"避免「{expr}」，改用关联/讨论型表述")

    disclaimer_markers = ["不构成医疗建议", "咨询医生", "非医疗建议", "遵医嘱"]
    if not any(m in text for m in disclaimer_markers):
        violations.append(
            {"type": "missing_disclaimer", "label": "缺少医疗免责声明", "pattern": "disclaimer"}
        )
        suggestions.append("结尾须含：个体情况请咨询医生，不构成医疗建议")

    passed = len(violations) == 0
    return {
        "passed": passed,
        "violations": violations,
        "suggestions": suggestions,
    }


def lint_script_document(doc: dict[str, Any]) -> dict[str, Any]:
    meta = doc.get("meta") or {}
    if doc.get("gate"):
        meta = {**meta, "gate": doc["gate"]}
    report = lint_script_text(
        doc.get("full_text") or "",
        meta=meta,
        write_mode=doc.get("write_mode") or "verify_before_script",
    )
    doc["safety_report"] = report
    return report
