#!/usr/bin/env python3
"""
语义风险裁决层（Claim Firewall / Risk Gate）

从标题/摘要规则抽取主张，裁决可写性（与热度分权）。
供 daily_topic_harvest、curate_daily_brief、script_safety 共用。
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

SENSATIONAL = [
    "根治", "治愈保证", "神药", "被骗", "一夜", "百分百", "千万别",
    "跌落神坛", "惊呆", "暴涨", "万病之源", "一招", "秘方", "包治",
]
ABSOLUTE_CLAIMS = ["所有人都", "一定治", "保证逆转", "永不复发", "替换药物"]
CREDIBLE_AUTHOR = [
    "医生", "医师", "营养师", "医院", "主任", "教授", "指南", "学会", "疾控", "大夫",
]

# 口播 Lint 与 Gate 共享
FORBIDDEN_PATTERNS: list[tuple[str, str]] = [
    (r"一定能(降|控制)?糖", "绝对化疗效"),
    (r"可以降血糖", "因果疗效断言"),
    (r"保证(逆转|治愈|根治)", "治愈承诺"),
    (r"所有人都", "绝对化人群"),
    (r"替医嘱|代替医生", "替代就医"),
    (r"停药|不用吃药", "用药建议"),
    (r"研究表明你一定", "UGC 确定性断言"),
    (r"只要.{0,8}就能(降|治)", "因果跳跃"),
]

CAUSAL_JUMP_PATTERNS: list[tuple[str, str]] = [
    (r"因为.{2,30}所以.{0,12}(降|控)糖", "因果跳跃"),
    (r"吃了.{2,20}(血糖|降糖)", "因果跳跃"),
]

DEFAULT_HEDGES = ["目前证据有限", "个体差异较大", "请以复查和医嘱为准"]

HEALTH_SIGNAL = re.compile(
    r"血糖|糖尿|控糖|胰岛素|糖化|HbA1c|GI\b|GL\b|glycemic|glucose|diabetes|"
    r"insulin|prediabetes|metabolic|CGM|低血糖|餐后|碳水",
    re.I,
)
TWITTER_NOISE = re.compile(
    r"trader|trading|bitcoin|crypto|bitget|gate\.io|binance|forex|"
    r"返\d+%|BP\d+|nft\b|airdrop",
    re.I,
)

CLAIM_RULES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"(降血糖|降糖|控糖|逆转|治愈|根治)", re.I),
        "claim_type": "causal_claim",
        "harm_risk": "medium",
        "forbidden": ["可以降血糖", "一定能降糖", "保证逆转", "根治"],
    },
    {
        "pattern": re.compile(r"(代替药物|停药|不用吃药|替换药物)", re.I),
        "claim_type": "medication_claim",
        "harm_risk": "high",
        "forbidden": ["停药", "不用吃药", "代替药物"],
        "allowed_frame": "verify_with_clinician",
    },
    {
        "pattern": re.compile(r"(二甲双胍|胰岛素|司美格鲁肽|格列|降糖药)", re.I),
        "claim_type": "drug_discussion",
        "harm_risk": "high",
        "forbidden": ["自行调整剂量", "停药"],
        "allowed_frame": "verify_with_clinician",
    },
    {
        "pattern": re.compile(r"(苹果醋|苦瓜|偏方|秘方)", re.I),
        "claim_type": "food_cure_claim",
        "harm_risk": "medium",
        "forbidden": ["可以降血糖", "降糖神器"],
    },
]

EXPERIENCE_WORDS = re.compile(r"亲身|实测|我吃了|亲测|体验|感觉|据说", re.I)
SCIENCE_WORDS = re.compile(r"研究|试验|指南|数据|mmol|HbA1c|糖化|GI\b|共识", re.I)

ALLOWED_FRAME_LABELS = {
    "cite_with_disclaimer": "可引用，须非医疗建议+链接",
    "verify_before_script": "写稿前回源核实",
    "discussion_only": "仅讨论型话题",
    "verify_with_clinician": "须强调遵医嘱/就医",
    "hook_only": "仅钩子",
}


def passes_health_relevance(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t)
    return bool(HEALTH_SIGNAL.search(blob))


def passes_twitter_filter(text: str, author: str = "", bio: str = "") -> bool:
    blob = f"{text} {author} {bio}"
    if TWITTER_NOISE.search(blob):
        return False
    return passes_health_relevance(text, bio)


def make_claim_id(claim_text: str) -> str:
    normalized = re.sub(r"\s+", "", (claim_text or "").strip().lower())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def adversarial_audit(
    title: str,
    author: str,
    url: str,
    platform: str,
    snippet: str = "",
) -> dict[str, Any]:
    """可验证性 + 证据层级 + 对抗性标记（不含热度）。"""
    t, a, u, s = title or "", author or "", url or "", snippet or ""
    blob = f"{t} {s} {a}"
    flags: list[str] = []
    reasons: list[str] = []
    score = 50

    tier = "D"
    if any(d in u for d in [".gov.cn", "who.int", "nih.gov", "nejm", "lancet", "指南", "consensus"]):
        tier, score = "A", score + 35
        reasons.append("一级来源：指南/政府/期刊域名")
    elif "dxy.cn" in u or "haodf.com" in u or "medlive" in u:
        tier, score = "B", score + 28
        reasons.append("二级来源：医疗专业平台")
    elif any(k in a for k in CREDIBLE_AUTHOR):
        tier, score = "C", score + 18
        reasons.append("作者具医疗相关身份标识（仍需核对资质）")
    elif platform in ("xhs", "bili", "zhihu", "twitter", "reddit", "youtube"):
        tier = "D"
        reasons.append("UGC 平台：默认仅可作选题钩子，不可当医学结论")

    for bad in SENSATIONAL:
        if bad in blob:
            flags.append("sensational")
            score -= 20
            reasons.append(f"对抗性标记：夸张词「{bad}」")
            tier = "E"
    for bad in ABSOLUTE_CLAIMS:
        if bad in blob:
            flags.append("absolute_claim")
            score -= 15
            tier = "E"
            reasons.append(f"对抗性标记：绝对化表述「{bad}」")

    if re.search(r"卖|链接|下单|代购|优惠券", blob) and tier in ("D", "E"):
        flags.append("commercial_hook")
        score -= 8
        reasons.append("对抗性标记：疑似带货动机")

    if re.search(r"\d+(\.\d+)?%|GI|HbA1c|糖化|mmol|研究|试验|指南", blob, re.I):
        score += 6
        reasons.append("含可核对的数据或术语（需回源核实）")

    if platform == "twitter" and not passes_twitter_filter(t, a, s):
        flags.append("off_topic_noise")
        tier, score = "E", min(score, 25)

    score = max(0, min(100, score))

    if tier == "A":
        use_as = "cite_directly"
        creator_note = "可引用来源观点，口播须加「非医疗建议」并附原链接"
    elif tier == "B":
        use_as = "verify_before_script"
        creator_note = "写稿前对照原帖/指南核实；口播避免给个体诊断"
    elif tier == "E" or "sensational" in flags or "absolute_claim" in flags:
        use_as = "hook_only"
        creator_note = "仅作「大家在讨论什么」的选题钩子，勿复述为事实"
    elif tier == "C":
        use_as = "verify_before_script"
        creator_note = "可讲话题，关键数字须二次查证；建议找指南或医生审稿"
    else:
        use_as = "hook_only"
        creator_note = "适合年轻受众切入点，内容须改写为「生活方式科普+就医提醒」"

    if score >= 75:
        label = "较高"
    elif score >= 55:
        label = "中等"
    elif score >= 35:
        label = "偏低"
    else:
        label = "需谨慎"

    return {
        "score": score,
        "label": label,
        "reasons": reasons[:5],
        "evidence_tier": tier,
        "adversarial_flags": flags,
        "use_as": use_as,
        "creator_note": creator_note,
    }


def _evidence_strength_for_tier(tier: str) -> str:
    return {"A": "high", "B": "medium", "C": "low", "D": "low", "E": "none"}.get(tier, "low")


def extract_claims(title: str, snippet: str = "", evidence_tier: str = "D") -> list[dict[str, Any]]:
    blob = f"{title or ''} {snippet or ''}"
    claims: list[dict[str, Any]] = []
    seen: set[str] = set()

    for rule in CLAIM_RULES:
        m = rule["pattern"].search(blob)
        if not m:
            continue
        claim_text = m.group(0).strip()
        if claim_text in seen:
            continue
        seen.add(claim_text)

        ev = _evidence_strength_for_tier(evidence_tier)
        harm = rule.get("harm_risk", "medium")
        misinterpret = "high" if evidence_tier in ("D", "E") and rule["claim_type"] == "causal_claim" else "medium"
        if harm == "high":
            misinterpret = "high"

        allowed = rule.get("allowed_frame")
        if not allowed:
            if rule["claim_type"] == "causal_claim" and evidence_tier in ("D", "E"):
                allowed = "discussion_only"
            elif evidence_tier in ("A", "B"):
                allowed = "verify_before_script"
            else:
                allowed = "discussion_only"

        forbidden = list(rule.get("forbidden") or [])
        claims.append(
            {
                "claim_id": make_claim_id(claim_text),
                "claim": claim_text,
                "claim_type": rule["claim_type"],
                "evidence_strength": ev,
                "harm_risk": harm,
                "misinterpretation_risk": misinterpret,
                "allowed_frame": allowed,
                "forbidden_expressions": forbidden,
                "required_hedges": list(DEFAULT_HEDGES),
            }
        )

    if not claims and blob.strip():
        claims.append(
            {
                "claim_id": make_claim_id(title or blob[:40]),
                "claim": (title or blob[:60]).strip(),
                "claim_type": "topic_discussion",
                "evidence_strength": _evidence_strength_for_tier(evidence_tier),
                "harm_risk": "low",
                "misinterpretation_risk": "medium" if evidence_tier in ("D", "E") else "low",
                "allowed_frame": "discussion_only" if evidence_tier in ("D", "E") else "verify_before_script",
                "forbidden_expressions": [],
                "required_hedges": list(DEFAULT_HEDGES),
            }
        )
    return claims


def detect_controversy_hint(title: str, snippet: str = "") -> str:
    blob = f"{title or ''} {snippet or ''}"
    has_exp = bool(EXPERIENCE_WORDS.search(blob))
    has_sci = bool(SCIENCE_WORDS.search(blob))
    if has_exp and has_sci:
        return "经验叙述与科学术语同现，易误读为已验证结论"
    if has_exp:
        return "以个人体验为主，不宜推广为普适结论"
    if re.search(r"误区|谣言|别信|真的吗|辟谣", blob):
        return "存在明显争议或辟谣向，适合讨论而非定论"
    return ""


def build_editorial_hints(
    title: str,
    auth: dict[str, Any],
    gate: dict[str, Any],
    claims: list[dict[str, Any]],
) -> dict[str, Any]:
    tier = auth.get("evidence_tier", "D")
    tier_reason = {
        "A": "一级权威来源，非热度驱动",
        "B": "专业平台来源，须回源核实",
        "C": "作者有医疗相关标识，仍须核对资质",
    }.get(tier, "UGC 讨论热点，默认不可当医学结论")

    misleading = ""
    if claims:
        high_risk = [c for c in claims if c.get("misinterpretation_risk") == "high"]
        if high_risk:
            misleading = f"标题/摘要含「{high_risk[0]['claim']}」，易被理解为个体疗效承诺"
        elif gate.get("allowed_frame") == "discussion_only":
            misleading = "标题观点可能被当成已验证医学结论"

    safe_rewrite = ""
    frame = gate.get("allowed_frame", "")
    if frame == "discussion_only":
        safe_rewrite = f"用「网上很多人在讨论 {title[:30]}…」而非「{title[:20]} 是对的」"
    elif frame == "verify_with_clinician":
        safe_rewrite = "强调「用药/调整方案须遵医嘱」，不给出个体剂量建议"
    elif tier in ("A", "B"):
        safe_rewrite = f"用「指南/来源提到…」并附链接，避免「你应该…」"
    else:
        safe_rewrite = "对照可查数据说明，结尾提醒个体差异与就医"

    return {
        "why_selected": tier_reason,
        "misleading_risk": misleading or gate.get("creator_note", ""),
        "safe_rewrite": safe_rewrite,
    }


def evaluate(
    title: str,
    author: str,
    url: str,
    platform: str,
    snippet: str = "",
    *,
    claim_graph_penalty: int = 0,
) -> dict[str, Any]:
    """
    完整 Gate 评估：authenticity + claims + gate 裁决。
    claim_graph_penalty: 来自 claim-graph 历史误读的 writability 扣分。
    """
    auth = adversarial_audit(title, author, url, platform, snippet)
    tier = auth["evidence_tier"]
    claims = extract_claims(title, snippet, tier)

    forbidden: list[str] = []
    hedges: list[str] = []
    veto: list[str] = []
    max_harm = "low"
    allowed_frame = "verify_before_script"

    for c in claims:
        forbidden.extend(c.get("forbidden_expressions") or [])
        for h in c.get("required_hedges") or []:
            if h not in hedges:
                hedges.append(h)
        hr = c.get("harm_risk", "low")
        if hr == "high":
            max_harm = "high"
        elif hr == "medium" and max_harm != "high":
            max_harm = "medium"
        af = c.get("allowed_frame", "")
        if af == "verify_with_clinician":
            allowed_frame = af
        elif af == "discussion_only" and allowed_frame != "verify_with_clinician":
            allowed_frame = af

    use_as = auth["use_as"]
    if max_harm == "high" and tier in ("D", "E"):
        use_as = "hook_only"
        veto.append("high_harm_claim_D_tier")
    if any(c.get("claim_type") == "causal_claim" and c.get("evidence_strength") == "low" for c in claims):
        if tier in ("D", "E"):
            use_as = "hook_only"
            veto.append("causal_claim_low_evidence_D_tier")
        elif use_as == "hook_only":
            veto.append("causal_claim_low_evidence")

    if allowed_frame == "discussion_only" and use_as not in ("cite_directly", "verify_before_script"):
        use_as = "hook_only"

    writability = auth["score"]
    if max_harm == "high":
        writability -= 25
    elif max_harm == "medium":
        writability -= 10
    if allowed_frame == "discussion_only":
        writability -= 8
    writability -= claim_graph_penalty
    writability = max(0, min(100, writability))

    blocked = (
        tier == "E"
        or "off_topic_noise" in auth.get("adversarial_flags", [])
    )
    passed = (
        not blocked
        and use_as in ("cite_directly", "verify_before_script", "safe_to_discuss")
        and writability >= 50
    )

    if not passed and not blocked:
        if writability < 50:
            veto.append("writability_below_threshold")

    claim_summary = claims[0]["claim"] if claims else (title or "").strip()[:80]
    controversy = detect_controversy_hint(title, snippet)

    gate = {
        "passed": passed,
        "writability_score": writability,
        "veto_reasons": veto,
        "use_as": use_as,
        "allowed_frame": allowed_frame,
        "forbidden_expressions": list(dict.fromkeys(forbidden)),
        "required_hedges": hedges or list(DEFAULT_HEDGES),
        "creator_note": auth.get("creator_note", ""),
    }

    editorial = build_editorial_hints(title, auth, gate, claims)

    return {
        "authenticity": auth,
        "claims": claims,
        "gate": gate,
        "claim_summary": claim_summary,
        "controversy_hint": controversy,
        "editorial": editorial,
    }


def score_authenticity(title: str, author: str, url: str, platform: str, snippet: str = "") -> dict[str, Any]:
    return adversarial_audit(title, author, url, platform, snippet)
