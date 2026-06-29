#!/usr/bin/env python3

"""

采集 JSON → AIHOT 式精选日报（时间线 + Agent 可读 JSON）。



输入: data/exports/daily-harvest-YYYY-MM-DD.json

输出:

  data/exports/daily-brief-YYYY-MM-DD.json

  data/exports/latest-brief.json

  research-daily/YYYY-MM-DD-精选日报.html

  research-daily/YYYY-MM-DD-精选日报.md

"""



from __future__ import annotations



import argparse

import html

import json

import os

import re

import sys

from datetime import datetime

from typing import Any



sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from platform_scraper import PROJECT_ROOT, dedup_key  # noqa: E402

from claim_gate import evaluate as claim_gate_evaluate, extract_claims, adversarial_audit  # noqa: E402

from claim_graph import get_claim_graph_penalty  # noqa: E402



EXPORTS_DIR = os.path.join(PROJECT_ROOT, "data", "exports")

REPORT_DIR = os.path.join(PROJECT_ROOT, "research-daily")

SCHEMA_DIR = os.path.join(PROJECT_ROOT, "data", "schemas")



FEATURED_LIMIT = 12

WRITABLE_LIMIT = 8

HOOK_LIMIT = 6

CROSS_PLATFORM_LIMIT = 5

SCHEMA_VERSION = "2.0"



USE_AS_LABEL = {

    "cite_directly": "可引用",

    "verify_before_script": "写稿前核实",

    "hook_only": "仅钩子",

    "safe_to_discuss": "可讨论",

}





def _ensure_gate_fields(item: dict) -> dict:
    """旧 harvest 无 gate 时回填裁决（不重跑采集）。"""
    if item.get("gate") and "writability_score" in item:
        return item
    title = item.get("title", "")
    auth = item.get("authenticity") or adversarial_audit(
        title,
        item.get("author", ""),
        item.get("url", ""),
        item.get("platform", ""),
        item.get("snippet", ""),
    )
    claim_ids = [
        c.get("claim_id", "")
        for c in extract_claims(title, item.get("snippet", ""), auth.get("evidence_tier", "D"))
    ]
    penalty = get_claim_graph_penalty([x for x in claim_ids if x])
    result = claim_gate_evaluate(
        title,
        item.get("author", ""),
        item.get("url", ""),
        item.get("platform", ""),
        item.get("snippet", ""),
        claim_graph_penalty=penalty,
    )
    gate = result["gate"]
    auth_merged = {**auth, "use_as": gate["use_as"], "creator_note": gate.get("creator_note") or auth.get("creator_note")}
    writability = gate["writability_score"]
    out = {
        **item,
        "authenticity": auth_merged,
        "gate": gate,
        "claims": result.get("claims") or [],
        "claim_summary": result.get("claim_summary", ""),
        "controversy_hint": result.get("controversy_hint", ""),
        "editorial": result.get("editorial") or {},
        "writability_score": writability,
        "topic_score": writability,
        "topic_pick": gate["passed"] and writability >= 62,
    }
    if not out.get("heat_score"):
        imp = out.get("importance") or {}
        out["heat_score"] = imp.get("score", 0)
    return out


def _blocked(item: dict) -> bool:

    auth = item.get("authenticity") or {}

    flags = auth.get("adversarial_flags") or []

    return auth.get("evidence_tier") == "E" or "off_topic_noise" in flags





def _gate_passed(item: dict) -> bool:

    gate = item.get("gate") or {}

    if gate.get("passed") is not None:

        return bool(gate.get("passed"))

    auth = item.get("authenticity") or {}

    return auth.get("use_as") in ("cite_directly", "verify_before_script", "safe_to_discuss")





def _writability_score(item: dict) -> int:

    if item.get("writability_score") is not None:

        return int(item.get("writability_score") or 0)

    gate = item.get("gate") or {}

    if gate.get("writability_score") is not None:

        return int(gate.get("writability_score") or 0)

    return int(item.get("topic_score") or 0)





def _heat_score(item: dict) -> int:

    if item.get("heat_score") is not None:

        return int(item.get("heat_score") or 0)

    imp = item.get("importance") or {}

    return int(imp.get("score") or 0)





def _parse_count(raw: Any) -> int:

    if raw is None:

        return 0

    s = str(raw).strip().replace(",", "")

    if not s:

        return 0

    m = re.match(r"^([\d.]+)\s*万$", s)

    if m:

        return int(float(m.group(1)) * 10000)

    m = re.match(r"^([\d.]+)\s*千$", s)

    if m:

        return int(float(m.group(1)) * 1000)

    digits = re.sub(r"[^\d]", "", s)

    return int(digits) if digits else 0





def _engagement(item: dict) -> int:

    if item.get("engagement"):

        return int(item.get("engagement") or 0)

    metrics = item.get("metrics") or {}

    return max(

        _parse_count(metrics.get("play")),

        _parse_count(metrics.get("likes")),

        _parse_count(metrics.get("replies")),

        _parse_count(metrics.get("views")),

    )





def _timeline_sort_key(item: dict) -> tuple:

    gate = item.get("gate") or {}

    passed = bool(gate.get("passed")) if gate else _gate_passed(item)

    return (passed, _writability_score(item), _heat_score(item))





def _item_brief(item: dict) -> dict[str, Any]:

    auth = item.get("authenticity") or {}

    imp = item.get("importance") or {}

    gate = item.get("gate") or {}

    editorial = item.get("editorial") or {}

    use_as = gate.get("use_as") or auth.get("use_as", "")



    brief = {

        "title": item.get("title", ""),

        "url": item.get("url", ""),

        "platform": item.get("platform", ""),

        "platform_label": item.get("platform_label", ""),

        "author": item.get("author", ""),

        "topic_score": _writability_score(item),

        "writability_score": _writability_score(item),

        "heat_score": _heat_score(item),

        "topic_pick": bool(item.get("topic_pick")),

        "evidence_tier": auth.get("evidence_tier", "?"),

        "use_as": use_as,

        "use_as_label": USE_AS_LABEL.get(use_as, use_as),

        "authenticity_score": auth.get("score"),

        "importance_score": imp.get("score"),

        "importance_label": imp.get("label", ""),

        "adversarial_flags": auth.get("adversarial_flags") or [],

        "creator_note": gate.get("creator_note") or auth.get("creator_note", ""),

        "category": item.get("category", ""),

        "snippet": (item.get("snippet") or "")[:200],

        "propagation": {

            "heat_score": _heat_score(item),

            "engagement": _engagement(item),

            "platform": item.get("platform", ""),

            "platform_label": item.get("platform_label", ""),

        },

        "cognitive_conflict": {

            "claim_summary": item.get("claim_summary") or "",

            "controversy_hint": item.get("controversy_hint") or "",

        },

        "writing_safety": {

            "gate_passed": bool(gate.get("passed")) if gate else _gate_passed(item),

            "allowed_frame": gate.get("allowed_frame", ""),

            "forbidden_expressions": gate.get("forbidden_expressions") or [],

            "required_hedges": gate.get("required_hedges") or [],

            "veto_reasons": gate.get("veto_reasons") or [],

        },

        "gate": {

            "passed": bool(gate.get("passed")) if gate else _gate_passed(item),

            "writability_score": _writability_score(item),

            "use_as": use_as,

            "allowed_frame": gate.get("allowed_frame", ""),

            "forbidden_expressions": gate.get("forbidden_expressions") or [],

            "required_hedges": gate.get("required_hedges") or [],

            "veto_reasons": gate.get("veto_reasons") or [],

        },

        "claims": item.get("claims") or [],

        "editorial": editorial,

    }

    return brief





def _dedupe_ranked(items: list[dict], limit: int, sort_key=_timeline_sort_key) -> list[dict]:

    seen: set[str] = set()

    out: list[dict] = []

    for it in sorted(items, key=sort_key, reverse=True):

        key = dedup_key(it.get("title", ""))

        if not key or key in seen:

            continue

        seen.add(key)

        out.append(_item_brief(it))

        if len(out) >= limit:

            break

    return out





def find_cross_platform_themes(items: list[dict]) -> list[dict]:

    buckets: dict[str, list[dict]] = {}

    for it in items:

        if _blocked(it):

            continue

        buckets.setdefault(dedup_key(it.get("title", "")), []).append(it)

    themes: list[dict] = []

    for group in buckets.values():

        plats = sorted({g["platform"] for g in group})

        if len(plats) < 2:

            continue

        best = max(group, key=_timeline_sort_key)

        gate = best.get("gate") or {}

        auth = best.get("authenticity") or {}

        themes.append(

            {

                "title": best.get("title", ""),

                "platforms": plats,

                "platform_labels": sorted({g.get("platform_label", g["platform"]) for g in group}),

                "topic_score": _writability_score(best),

                "writability_score": _writability_score(best),

                "heat_score": _heat_score(best),

                "urls": [g["url"] for g in group if g.get("url")][:4],

                "use_as": gate.get("use_as") or auth.get("use_as", ""),

                "platforms_in_cluster": plats,

            }

        )

    themes.sort(key=lambda x: (len(x["platforms"]), x["writability_score"]), reverse=True)

    return themes[:CROSS_PLATFORM_LIMIT]





def build_agent_hints(

    featured: list[dict],

    writable: list[dict],

    hooks: list[dict],

) -> dict[str, Any]:

    verify_list: list[str] = []

    for it in writable + featured:

        if it.get("use_as") == "verify_before_script":

            verify_list.append(f"{it['title'][:40]} — {it.get('creator_note') or '关键数字须回源'}")

    verify_list = verify_list[:8]



    top_angles = []

    for it in writable[:3]:

        ed = it.get("editorial") or {}

        ws = it.get("writing_safety") or it.get("gate") or {}

        top_angles.append(

            {

                "title": it["title"],

                "platforms_suggest": "dy,xhs" if it.get("platform") in ("xhs", "zhihu") else "dy,bili",

                "evidence_tier": it.get("evidence_tier"),

                "use_as": it.get("use_as"),

                "url": it.get("url"),

                "why_selected": ed.get("why_selected", ""),

                "misleading_risk": ed.get("misleading_risk", ""),

                "safe_rewrite": ed.get("safe_rewrite", ""),

                "forbidden_expressions": ws.get("forbidden_expressions") or [],

                "required_hedges": ws.get("required_hedges") or [],

            }

        )



    do_not = [

        f"{it['title'][:50]}（{it.get('use_as_label')}）"

        for it in hooks

        if it.get("adversarial_flags") or it.get("use_as") == "hook_only"

    ][:6]



    return {

        "query_commands": [

            "今日精选热点有哪些？",

            "哪些选题可以写口播？",

            "待核实清单是什么？",

            "哪些是 hook_only 不能当医学结论？",

            "Gate 否决了哪些高热度条目？",

        ],

        "top_script_angles": top_angles,

        "verify_list": verify_list,

        "do_not_cite_as_fact": do_not,

        "disclaimer": "个体情况请咨询医生，不构成医疗建议。维护者非执业医生。",

    }





def curate_from_harvest_payload(payload: dict) -> dict[str, Any]:

    items = [_ensure_gate_fields(it) for it in (payload.get("items") or [])]

    summary_in = payload.get("summary") or {}

    report_date = payload.get("report_date") or datetime.now().strftime("%Y-%m-%d")



    clean = [it for it in items if not _blocked(it)]

    writable_src = [

        it

        for it in clean

        if it.get("topic_pick") and _gate_passed(it)

    ]

    hook_src = [

        it

        for it in clean

        if not _gate_passed(it)

        and (it.get("authenticity") or {}).get("use_as") == "hook_only"

        and _heat_score(it) >= 50

    ]



    featured = _dedupe_ranked(clean, FEATURED_LIMIT)

    writable = _dedupe_ranked(writable_src, WRITABLE_LIMIT)

    hooks = _dedupe_ranked(hook_src, HOOK_LIMIT, sort_key=lambda x: (_heat_score(x), _writability_score(x)))

    cross_platform = find_cross_platform_themes(clean)



    brief = {

        "schema_version": SCHEMA_VERSION,

        "version": "2.0",

        "report_date": report_date,

        "source_harvest": f"daily-harvest-{report_date}.json",

        "curated_at": datetime.now().isoformat(timespec="seconds"),

        "summary": {

            "total_raw": summary_in.get("total_raw", len(items)),

            "after_filter": len(clean),

            "featured_count": len(featured),

            "writable_count": len(writable),

            "hook_only_count": len(hooks),

            "cross_platform_themes": len(cross_platform),

            "new_topics_added": summary_in.get("new_topics_added", 0),

            "platforms_ok": summary_in.get("platforms_ok", []),

            "gate_note": "timeline 按 gate.passed → writability_score 排序；heat_score 仅传播展示",

        },

        "timeline": featured,

        "writable_picks": writable,

        "hook_only": hooks,

        "cross_platform": cross_platform,

        "agent_hints": build_agent_hints(featured, writable, hooks),

    }

    return brief





def render_markdown(brief: dict) -> str:

    d = brief["report_date"]

    s = brief["summary"]

    lines = [

        f"# 血糖控糖精选日报 · {d}",

        "",

        f"> 机器精选 · Schema {brief.get('schema_version', '1.0')} · 源采集 {s['total_raw']} 条 → 展示 {s['featured_count']} 条热点",

        "> Gate 拥有可写性否决权；D/E 与 hook_only 不得写为医学结论",

        "",

        "## Agent 速查",

        "",

    ]

    hints = brief.get("agent_hints") or {}

    for q in hints.get("query_commands") or []:

        lines.append(f"- {q}")

    lines.extend(["", "## 时间线 · 今日热点", ""])

    for i, it in enumerate(brief.get("timeline") or [], 1):

        ws = it.get("writing_safety") or {}

        lines.append(

            f"### {i}. {it['title']}\n"

            f"- 平台：{it['platform_label']} · 可写性 **{it.get('writability_score', it['topic_score'])}** · "

            f"热度 **{it.get('heat_score', 0)}** · "

            f"证据 **{it['evidence_tier']}** · {it['use_as_label']}\n"

            f"- Gate：{'通过' if ws.get('gate_passed') else '未通过'} · {it.get('claim_summary') or ''}\n"

            f"- 链接：{it.get('url') or '—'}\n"

        )

    if brief.get("writable_picks"):

        lines.extend(["", "## 可写稿选题", ""])

        for it in brief["writable_picks"]:

            lines.append(f"- **{it['title']}** ({it['evidence_tier']}/{it['use_as_label']}) — {it.get('url')}")

    if brief.get("cross_platform"):

        lines.extend(["", "## 跨平台同题", ""])

        for th in brief["cross_platform"]:

            lines.append(

                f"- {th['title']} — {', '.join(th['platform_labels'])} · 可写 {th.get('writability_score')}"

            )

    if brief.get("hook_only"):

        lines.extend(["", "## 仅钩子（不可当医学结论）", ""])

        for it in brief["hook_only"]:

            flags = ",".join(it.get("adversarial_flags") or []) or "UGC"

            lines.append(f"- {it['title']} · 热度 {it.get('heat_score')} · {flags}")

    verify = hints.get("verify_list") or []

    if verify:

        lines.extend(["", "## 待核实", ""])

        for v in verify:

            lines.append(f"- [ ] {v}")

    lines.extend(["", "---", hints.get("disclaimer", ""), ""])

    return "\n".join(lines)





def _tier_badge(tier: str) -> str:

    colors = {

        "A": "tier-a",

        "B": "tier-b",

        "C": "tier-c",

        "D": "tier-d",

        "E": "tier-e",

    }

    cls = colors.get(tier, "tier-d")

    return f'<span class="badge {cls}">{html.escape(tier)}</span>'





def render_html(brief: dict) -> str:

    d = brief["report_date"]

    s = brief["summary"]

    timeline_rows = []

    for i, it in enumerate(brief.get("timeline") or [], 1):

        url = it.get("url") or ""

        link = (

            f'<a href="{html.escape(url)}" target="_blank" rel="noopener">原贴</a>'

            if url

            else ""

        )

        flags = it.get("adversarial_flags") or []

        flag_html = (

            " ".join(f'<span class="flag">{html.escape(f)}</span>' for f in flags)

            if flags

            else ""

        )

        ws = it.get("writing_safety") or {}

        gate_ok = ws.get("gate_passed")

        gate_badge = '<span class="gate-ok">Gate✓</span>' if gate_ok else '<span class="gate-no">Gate✗</span>'

        timeline_rows.append(

            f"""<article class="tl-item">

  <div class="tl-rank">{i}</div>

  <div class="tl-body">

    <h3>{html.escape(it['title'])}</h3>

    <div class="tl-meta">

      <span class="plat">{html.escape(it['platform_label'])}</span>

      {_tier_badge(str(it.get('evidence_tier','?')))}

      <span class="score">可写{it.get('writability_score', it.get('topic_score',0))}</span>

      <span class="heat">热{it.get('heat_score',0)}</span>

      {gate_badge}

      <span class="use">{html.escape(it.get('use_as_label',''))}</span>

      {flag_html}

    </div>

    <p class="note">{html.escape(it.get('creator_note') or it.get('snippet') or '')}</p>

    <div class="tl-foot">{link}</div>

  </div>

</article>"""

        )



    writable_li = "".join(

        f"<li><strong>{html.escape(it['title'][:60])}</strong> "

        f"<span class='muted'>{it.get('evidence_tier')}/{html.escape(it.get('use_as_label',''))}</span></li>"

        for it in brief.get("writable_picks") or []

    )

    cross_li = "".join(

        f"<li>{html.escape(th['title'][:55])} — "

        f"<span class='muted'>{', '.join(html.escape(x) for x in th['platform_labels'])}</span></li>"

        for th in brief.get("cross_platform") or []

    )

    hook_li = "".join(

        f"<li>{html.escape(it['title'][:55])} <span class='warn'>hook · 热{it.get('heat_score',0)}</span></li>"

        for it in brief.get("hook_only") or []

    )

    verify_li = "".join(

        f"<li>{html.escape(v)}</li>" for v in (brief.get("agent_hints") or {}).get("verify_list") or []

    )



    return f"""<!DOCTYPE html>

<html lang="zh-CN"><head><meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>血糖控糖精选日报 · {html.escape(d)}</title>

<style>

:root {{ --bg:#0f1117; --bg2:#1a1d27; --ink:#e8eaed; --muted:#8b8fa3; --accent:#00d4aa; --accent2:#ff6b6b; --accent3:#ffd93d; --accent4:#6c8cff; --rule:#2a2d3a; }}

* {{ box-sizing:border-box; margin:0; padding:0; }}

body {{ font-family:-apple-system,'Segoe UI','Noto Sans CJK SC',sans-serif; background:var(--bg); color:var(--ink); line-height:1.65; }}

.wrap {{ max-width:920px; margin:0 auto; padding:28px 18px 48px; }}

.hero {{ text-align:center; padding-bottom:24px; border-bottom:1px solid var(--rule); margin-bottom:24px; }}

.hero .tag {{ display:inline-block; background:linear-gradient(135deg,var(--accent),var(--accent4)); color:var(--bg); font-size:11px; font-weight:700; padding:4px 12px; border-radius:20px; margin-bottom:10px; }}

.hero h1 {{ font-size:24px; margin-bottom:6px; }}

.hero p {{ color:var(--muted); font-size:13px; }}

.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin-bottom:28px; }}

.stat {{ background:var(--bg2); border:1px solid var(--rule); border-radius:10px; padding:10px 14px; min-width:88px; }}

.stat b {{ display:block; font-size:20px; color:var(--accent); }}

.stat span {{ font-size:11px; color:var(--muted); }}

h2 {{ font-size:16px; color:var(--accent); margin:24px 0 14px; }}

.tl-item {{ display:flex; gap:14px; margin-bottom:16px; padding-bottom:16px; border-bottom:1px solid var(--rule); }}

.tl-rank {{ flex:0 0 28px; height:28px; border-radius:50%; background:var(--bg2); border:1px solid var(--rule); display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:700; color:var(--accent); }}

.tl-body h3 {{ font-size:15px; margin-bottom:8px; font-weight:600; }}

.tl-meta {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:6px; font-size:11px; }}

.plat {{ background:rgba(0,212,170,.12); color:var(--accent); padding:2px 8px; border-radius:6px; }}

.score {{ color:var(--accent3); font-weight:600; }}

.heat {{ color:var(--muted); }}

.gate-ok {{ color:var(--accent); font-weight:700; }}

.gate-no {{ color:var(--accent2); font-weight:700; }}

.use {{ color:var(--muted); }}

.badge {{ padding:2px 7px; border-radius:4px; font-weight:700; }}

.tier-a,.tier-b {{ background:rgba(0,212,170,.15); color:var(--accent); }}

.tier-c {{ background:rgba(108,140,255,.15); color:var(--accent4); }}

.tier-d,.tier-e {{ background:rgba(255,217,61,.12); color:var(--accent3); }}

.flag {{ background:rgba(255,107,107,.12); color:var(--accent2); padding:1px 6px; border-radius:4px; }}

.note {{ font-size:12px; color:var(--muted); margin:6px 0; }}

.tl-foot a {{ color:var(--accent4); font-size:12px; text-decoration:none; }}

.panel {{ background:var(--bg2); border:1px solid var(--rule); border-radius:10px; padding:16px; margin-bottom:14px; }}

.panel ul {{ padding-left:18px; font-size:13px; }}

.panel li {{ margin-bottom:6px; }}

.muted {{ color:var(--muted); font-size:12px; }}

.warn {{ color:var(--accent2); font-size:11px; }}

.agent-box {{ font-size:12px; color:var(--muted); }}

.agent-box code {{ color:var(--accent); font-size:11px; }}

.footer {{ text-align:center; color:var(--muted); font-size:11px; margin-top:32px; padding-top:16px; border-top:1px solid var(--rule); }}

</style></head><body><div class="wrap">

<div class="hero">

  <div class="tag">CURATED · Schema {html.escape(str(brief.get('schema_version','2.0')))}</div>

  <h1>血糖 / 控糖精选日报</h1>

  <p>{html.escape(d)} · 从 {s['total_raw']} 条采集中精选 {s['featured_count']} 条 · Gate 分权排序</p>

</div>

<div class="stats">

  <div class="stat"><b>{s['featured_count']}</b><span>时间线</span></div>

  <div class="stat"><b>{s['writable_count']}</b><span>可写稿</span></div>

  <div class="stat"><b>{s['hook_only_count']}</b><span>仅钩子</span></div>

  <div class="stat"><b>{s['cross_platform_themes']}</b><span>跨平台</span></div>

  <div class="stat"><b>{s.get('new_topics_added',0)}</b><span>新入库</span></div>

</div>

<section>

  <h2>时间线</h2>

  {''.join(timeline_rows) or '<p class="muted">今日无可用精选条目</p>'}

</section>

<div class="panel"><h2 style="margin-top:0">可写稿选题</h2><ul>{writable_li or '<li class="muted">无（见仅钩子区）</li>'}</ul></div>

<div class="panel"><h2 style="margin-top:0">跨平台同题</h2><ul>{cross_li or '<li class="muted">暂无多平台共振</li>'}</ul></div>

<div class="panel"><h2 style="margin-top:0">仅钩子</h2><ul>{hook_li or '<li class="muted">无</li>'}</ul></div>

<div class="panel"><h2 style="margin-top:0">Agent 待核实</h2><ul>{verify_li or '<li class="muted">无</li>'}</ul>

<div class="agent-box" style="margin-top:10px">JSON: <code>data/exports/daily-brief-{html.escape(d)}.json</code> · Markdown: <code>research-daily/{html.escape(d)}-精选日报.md</code></div></div>

<div class="footer">个体情况请咨询医生，不构成医疗建议 · 维护者非执业医生</div>

</div></body></html>"""





def write_schema_stub() -> None:

    """写入 JSON Schema 指针文件（供 Agent / CI 引用）。"""

    os.makedirs(SCHEMA_DIR, exist_ok=True)

    schema_path = os.path.join(SCHEMA_DIR, "daily-brief.schema.json")

    if os.path.isfile(schema_path):

        return

    stub = {

        "$schema": "https://json-schema.org/draft/2020-12/schema",

        "title": "DailyBrief",

        "description": "血糖控糖精选日报 Schema 2.0 — 见 curate_daily_brief.SCHEMA_VERSION",

        "type": "object",

        "required": ["schema_version", "report_date", "timeline", "writable_picks", "agent_hints"],

        "properties": {

            "schema_version": {"const": "2.0"},

            "timeline": {"type": "array"},

            "writable_picks": {"type": "array"},

            "hook_only": {"type": "array"},

            "agent_hints": {"type": "object"},

        },

    }

    with open(schema_path, "w", encoding="utf-8") as f:

        json.dump(stub, f, ensure_ascii=False, indent=2)





def save_curated_brief(report_date: str, harvest_payload: dict) -> dict[str, str]:

    write_schema_stub()

    brief = curate_from_harvest_payload(harvest_payload)

    os.makedirs(EXPORTS_DIR, exist_ok=True)

    os.makedirs(REPORT_DIR, exist_ok=True)



    json_path = os.path.join(EXPORTS_DIR, f"daily-brief-{report_date}.json")

    md_path = os.path.join(REPORT_DIR, f"{report_date}-精选日报.md")

    html_path = os.path.join(REPORT_DIR, f"{report_date}-精选日报.html")



    with open(json_path, "w", encoding="utf-8") as f:

        json.dump(brief, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:

        f.write(render_markdown(brief))

    with open(html_path, "w", encoding="utf-8") as f:

        f.write(render_html(brief))



    latest = os.path.join(EXPORTS_DIR, "latest-brief.json")

    with open(latest, "w", encoding="utf-8") as f:

        json.dump(

            {

                "report_date": report_date,

                "schema_version": brief.get("schema_version", SCHEMA_VERSION),

                "path": os.path.basename(json_path),

                "json": f"exports/daily-brief-{report_date}.json",

                "html": f"research-daily/{report_date}-精选日报.html",

                "markdown": f"research-daily/{report_date}-精选日报.md",

            },

            f,

            ensure_ascii=False,

            indent=2,

        )

    return {"json": json_path, "md": md_path, "html": html_path}





def load_harvest(path: str) -> dict:

    with open(path, encoding="utf-8") as f:

        return json.load(f)





def resolve_harvest_path(date: str | None = None) -> str:

    if date:

        p = os.path.join(EXPORTS_DIR, f"daily-harvest-{date}.json")

        if os.path.isfile(p):

            return p

        raise FileNotFoundError(p)

    latest = os.path.join(EXPORTS_DIR, "latest-harvest.json")

    if os.path.isfile(latest):

        with open(latest, encoding="utf-8") as f:

            ptr = json.load(f)

        p = os.path.join(EXPORTS_DIR, ptr.get("path") or "")

        if os.path.isfile(p):

            return p

    today = datetime.now().strftime("%Y-%m-%d")

    p = os.path.join(EXPORTS_DIR, f"daily-harvest-{today}.json")

    if os.path.isfile(p):

        return p

    raise FileNotFoundError("no harvest json found")





def main() -> int:

    parser = argparse.ArgumentParser(description="从采集 JSON 生成精选日报")

    parser.add_argument("--date", help="YYYY-MM-DD，默认读 latest-harvest")

    args = parser.parse_args()

    try:

        harvest_path = resolve_harvest_path(args.date)

    except FileNotFoundError as e:

        print(f"[错误] {e}", file=sys.stderr)

        return 1

    payload = load_harvest(harvest_path)

    report_date = payload.get("report_date") or args.date or datetime.now().strftime("%Y-%m-%d")

    paths = save_curated_brief(report_date, payload)

    print(f"[精选日报] {report_date}")

    for k, v in paths.items():

        print(f"  {k}: {v}")

    return 0





if __name__ == "__main__":

    sys.exit(main())


