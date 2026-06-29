#!/usr/bin/env python3
"""口播写稿：知识库匹配、资料增强、核实清单与文案组装（非医生创作者规则）。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = DATA_DIR / "scripts"
TOPICS_FILE = DATA_DIR / "discovered-topics.json"
EXPORTS_DIR = DATA_DIR / "exports"

DISCLAIMER = "以上为网上讨论/科普信息，个体情况请咨询医生，不构成医疗建议。"

CAT_MAP = {
    "辟谣纠偏": "myth",
    "饮食指南": "food",
    "数字科普": "number",
    "实操方法": "action",
    "症状预警": "symptom",
    "工具测评": "tool",
    "案例故事": "story",
    "避坑指南": "mistake",
}

PERSONA_LABELS = {
    "friendly": "亲切科普（像朋友聊天）",
    "expert": "循证解读（资料说话，非医生身份）",
    "personal": "亲身经历（控糖者自述）",
    "surprise": "反常识揭秘（制造意外感）",
}

PLATFORM_LABELS = {"dy": "抖音", "xhs": "小红书", "bili": "B站"}


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_foods() -> list[dict]:
    data = load_json(DATA_DIR / "foods" / "gi-database.json")
    return data.get("foods", [])


def load_knowledge_topics() -> list[dict]:
    data = load_json(DATA_DIR / "knowledge" / "topics.json")
    return data.get("topics", [])


def load_discovered_topics() -> dict:
    if not TOPICS_FILE.exists():
        return {"version": "1.0", "topics": []}
    return load_json(TOPICS_FILE)


def load_latest_harvest() -> dict | None:
    pointer = EXPORTS_DIR / "latest-harvest.json"
    if not pointer.exists():
        candidates = sorted(EXPORTS_DIR.glob("daily-harvest-*.json"), reverse=True)
        if not candidates:
            return None
        return load_json(candidates[0])
    meta = load_json(pointer)
    path = EXPORTS_DIR / meta.get("path", f"daily-harvest-{meta.get('report_date', '')}.json")
    if path.exists():
        return load_json(path)
    return None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def food_name_variants(name_zh: str) -> list[str]:
    variants = [name_zh]
    if "/" in name_zh:
        variants.extend(p.strip() for p in name_zh.split("/") if p.strip())
    return variants


def match_foods(text: str, foods: list[dict] | None = None, limit: int = 5) -> list[dict]:
    foods = foods if foods is not None else load_foods()
    text_norm = normalize_text(text)
    matched: list[tuple[int, dict]] = []
    for food in foods:
        name = food.get("name_zh", "")
        for variant in food_name_variants(name):
            if len(variant) >= 2 and variant in text_norm:
                matched.append((len(variant), food))
                break
    matched.sort(key=lambda x: -x[0])
    seen: set[str] = set()
    out: list[dict] = []
    for _, food in matched:
        fid = food.get("id")
        if fid in seen:
            continue
        seen.add(fid)
        out.append(food)
        if len(out) >= limit:
            break
    return out


def match_knowledge(text: str, topics: list[dict] | None = None, limit: int = 3) -> list[dict]:
    topics = topics if topics is not None else load_knowledge_topics()
    text_norm = normalize_text(text)
    scored: list[tuple[int, dict]] = []
    for topic in topics:
        score = 0
        for kw in topic.get("keywords", []):
            if kw and kw in text_norm:
                score += len(kw)
        title = topic.get("title_zh", "")
        if title and any(part in text_norm for part in title.split("（")[0].split(" ") if len(part) >= 2):
            score += 3
        if score:
            scored.append((score, topic))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:limit]]


def format_food_fact(food: dict) -> str:
    parts = [f"{food['name_zh']} GI{food.get('gi', '?')}"]
    gl = food.get("gl_per_serving")
    if gl not in (None, "", 0):
        parts.append(f"GL{gl}")
    level = food.get("gi_level")
    if level:
        parts.append(f"{level}GI")
    return " · ".join(parts)


def enrich_data_ref(
    title: str,
    angle: str = "",
    snippet: str = "",
    extra_lines: list[str] | None = None,
    *,
    foods: list[dict] | None = None,
    knowledge: list[dict] | None = None,
) -> dict[str, Any]:
    corpus = " ".join(filter(None, [title, angle, snippet]))
    matched_foods = match_foods(corpus, foods=foods)
    matched_topics = match_knowledge(corpus, topics=knowledge)

    lines: list[str] = []
    if extra_lines:
        lines.extend(x.strip() for x in extra_lines if x and x.strip())
    for food in matched_foods:
        line = format_food_fact(food)
        if line not in lines:
            lines.append(line)
    for topic in matched_topics:
        for point in topic.get("key_points", [])[:4]:
            if point not in lines:
                lines.append(point)
    if snippet and snippet.strip() and snippet.strip() not in lines:
        lines.append(f"来源摘要：{snippet.strip()[:120]}")

    return {
        "data_ref": lines,
        "matched_foods": [{"id": f["id"], "name_zh": f["name_zh"], "gi": f.get("gi")} for f in matched_foods],
        "matched_knowledge": [{"id": t["id"], "title_zh": t.get("title_zh", "")} for t in matched_topics],
    }


def resolve_write_mode(use_as: str | None) -> str:
    if use_as == "hook_only":
        return "hook_only"
    if use_as == "cite_directly":
        return "cite_directly"
    return "verify_before_script"


def build_verify_checklist(meta: dict[str, Any]) -> list[dict[str, Any]]:
    use_as = meta.get("use_as") or "verify_before_script"
    tier = meta.get("evidence_tier") or "D"
    checklist = [
        {
            "id": "disclaimer",
            "text": "口播含「非医疗建议」声明",
            "required": True,
            "auto": True,
        },
    ]
    if use_as == "hook_only":
        checklist.insert(
            0,
            {
                "id": "hook_only",
                "text": "正文仅写「大家在讨论…」，不得写成医学结论",
                "required": True,
                "auto": False,
            },
        )
    if tier in ("C", "D", "E") or use_as == "verify_before_script":
        checklist.append(
            {
                "id": "verify_numbers",
                "text": "关键数字/疗效已对照原帖或 A/B 级指南",
                "required": True,
                "auto": False,
            }
        )
    if meta.get("source_urls"):
        checklist.append(
            {
                "id": "source_trace",
                "text": "主张可追溯到 source_urls 中的原贴/指南",
                "required": True,
                "auto": False,
            }
        )
    flags = meta.get("adversarial_flags") or []
    if flags:
        checklist.append(
            {
                "id": "adversarial",
                "text": f"已处理对抗性标记：{', '.join(flags)}",
                "required": True,
                "auto": False,
            }
        )
    if meta.get("creator_note"):
        checklist.append(
            {
                "id": "creator_note",
                "text": meta["creator_note"],
                "required": False,
                "auto": False,
            }
        )
    return checklist


def _pick_hook(title: str, persona: str, write_mode: str) -> str:
    clean = re.sub(r"[？!！。]", "", title)
    if write_mode == "hook_only":
        templates = [
            f"最近网上很多人在聊「{clean}」——今天不判对错，只帮你把讨论脉络讲清楚。",
            f"你可能也刷到过：{clean}？先说明：这是平台讨论热点，不是给你下诊断。",
        ]
    elif persona == "expert":
        templates = [
            f"关于「{clean}」，我查了公开资料和指南，今天用普通人能听懂的方式讲清楚。",
            f"「{clean}」这个话题讨论很多，咱们对照可查的数据来说。",
        ]
    elif persona == "personal":
        templates = [
            f"控糖路上我也纠结过：{clean}？今天把我查到的和踩过的坑摊开说。",
        ]
    elif persona == "surprise":
        templates = [
            f"关于{clean}，常见说法和可查数据之间，可能差一截。",
        ]
    else:
        templates = [
            f"关于「{clean}」，网上说法挺多——今天帮你捋一捋哪些能参考、哪些别当真。",
            f"有朋友说：{clean}？咱们慢慢聊，记得个体情况要问医生。",
        ]
    return templates[0]


def _max_points_for_duration(duration: int) -> int:
    if duration <= 20:
        return 2
    if duration <= 45:
        return 3
    if duration <= 90:
        return 4
    return 5


def _topic_intro(title: str, cat: str, write_mode: str) -> str:
    clean = re.sub(r"[？!！。]", "", title)
    if write_mode == "hook_only" or not clean:
        return ""
    if re.search(r"怎么判断|如何判断|自测|有没有|是不是", title):
        return (
            f"关于「{clean}」，先说明：网上的讨论和自测清单，"
            "只能帮你打开话题，不能替代体检和医生判断。"
        )
    if re.search(r"能不能|可以吗|可不可以", title):
        return f"「{clean}」别只看一条短视频就下结论。下面把资料里相对好核查的几点，串成一条线。"
    if cat == "myth":
        return f"围绕「{clean}」，咱们对照可查信息，把常见误会和相对靠谱的说法分开。"
    if cat == "number":
        return f"「{clean}」涉及的数字不少，我按「先概念、再数字、再怎么用」来说。"
    return f"围绕「{clean}」，我把资料里最关键、也相对好核对的几点，展开说人话版。"


def _expand_point(point: str, index: int) -> str:
    leads = ["先说第一点，", "第二点，", "第三点，", "还有一点，", "最后补充，"]
    lead = leads[index] if index < len(leads) else "另外，"
    p = (point or "").strip()
    if not p:
        return ""

    if p.startswith("【来源】"):
        body = p.replace("【来源】", "", 1).strip()
        sent = body if re.search(r"[。！？]$", body) else f"{body}。"
        return f"{lead}根据可查来源摘引：{sent}口播时请对照原链接核实，勿当定论。"

    if re.search(r"GI\s*\d|GL\s*\d|mmol|HbA1c|糖化|≤|≥", p):
        return f"{lead}数字这块：{p.rstrip('。．')}。这是讨论用的参考，你的目标值以复查和医嘱为准。"

    if re.search(r'=|「|比喻|像.*一样|钥匙|锁', p):
        body = p if re.search(r"[。！？]$", p) else f"{p}。"
        return f"{lead}{body}这个比喻好懂，但别凭感觉就给自己贴标签。"

    if "（" in p and "）" in p:
        body = p if re.search(r"[。！？]$", p) else f"{p}。"
        return f"{lead}{body}"

    if len(p) <= 18:
        return f"{lead}很多人会提到：{p}。把它当成提问线索，不是结论。"

    return f"{lead}{p if re.search(r'[。！？]$', p) else p + '。'}"


def _body_bridge(topic: str, cat: str, write_mode: str) -> str:
    if write_mode == "hook_only":
        return "如果你也有类似困惑，别自己吓自己，该复查就复查。"
    if re.search(r"判断|自测|有没有|是否|怎么查", topic or ""):
        return (
            "要是觉得对上了好几条，别自己诊断——"
            "空腹/餐后血糖、腰围、家族史，交给医生一起评估更靠谱。"
        )
    if cat == "food":
        return "记住：不是「绝对不能吃」，而是份量、搭配和烹饪方式一起考虑。"
    if cat == "number":
        return "这些数字帮你建立语感，异常与否以化验单和医生解读为准。"
    if cat == "symptom":
        return "症状只是提醒，不是确诊；有担心就尽快做正规检查。"
    return "以上内容来自公开讨论和可查资料，怎么落到你身上，还要结合体检结果。"


def expand_spoken_body(
    *,
    title: str,
    cat: str,
    data_lines: list[str],
    write_mode: str,
    duration: int,
) -> str:
    points = [x.strip() for x in data_lines if x and x.strip()]
    if write_mode == "hook_only":
        ps = points[: _max_points_for_duration(duration)] or [
            "有人在分享个人体验",
            "也有人在质疑夸张说法",
            "更稳妥的是结合体检和医嘱",
        ]
        chunks = [_expand_point(p, i) for i, p in enumerate(ps)]
        return (
            "先把话说在前面：以下是网上讨论里反复出现的几点，不等于医学结论。\n\n"
            + "\n\n".join(chunks)
            + f"\n\n{_body_bridge(title, cat, write_mode)}"
        )

    limit = _max_points_for_duration(duration)
    pts = points[:limit]
    if not pts:
        pts = [
            "先搞清自己的体检指标，而不是只看短视频标题",
            "生活方式调整通常比极端做法更可坚持",
            "有用药或指标异常，及时咨询医生",
        ]

    intro = _topic_intro(title, cat, write_mode)
    expanded = [_expand_point(p, i) for i, p in enumerate(pts)]
    bridge = _body_bridge(title, cat, write_mode)
    return "\n\n".join([x for x in [intro, *expanded, bridge] if x])


def _build_body(
    cat: str,
    data_lines: list[str],
    write_mode: str,
    duration: int,
    title: str = "",
) -> str:
    return expand_spoken_body(
        title=title,
        cat=cat,
        data_lines=data_lines,
        write_mode=write_mode,
        duration=duration,
    )


def _build_cta(platform: str) -> str:
    ctas = {
        "dy": "觉得有收获就点个赞收藏；评论区说说你还想聊哪个控糖话题。",
        "xhs": "先⭐收藏，对照着看。有问题评论区聊，记得个体情况咨询医生。",
        "bili": "有帮助的话三连支持；弹幕或评论告诉我下一期想聊什么。",
    }
    return ctas.get(platform, ctas["dy"])


def merge_source_key_points(data_ref: list[str], source_bundle: dict[str, Any] | None) -> list[str]:
    lines = list(data_ref or [])
    if not source_bundle:
        return lines
    for point in source_bundle.get("key_points") or []:
        line = point if point.startswith("【来源】") else f"【来源】{point}"
        if line not in lines:
            lines.append(line)
    return lines


def build_script_document(
    *,
    title: str,
    platform: str = "dy",
    cat: str = "myth",
    duration: int = 30,
    persona: str = "friendly",
    data_ref: list[str] | None = None,
    meta: dict[str, Any] | None = None,
    angle: str = "",
) -> dict[str, Any]:
    meta = meta or {}
    write_mode = resolve_write_mode(meta.get("use_as"))
    data_ref = data_ref or []
    if not data_ref and (title or angle):
        data_ref = enrich_data_ref(title, angle=angle).get("data_ref", [])

    hook = _pick_hook(title, persona, write_mode)
    body = _build_body(cat, data_ref, write_mode, duration, title=title)
    cta = _build_cta(platform)
    full_text = f"{hook}\n\n{body}\n\n{cta}\n\n{DISCLAIMER}"

    doc = {
        "title": title,
        "platform": platform,
        "platform_label": PLATFORM_LABELS.get(platform, platform),
        "cat": cat,
        "duration_sec": duration,
        "persona": persona,
        "persona_label": PERSONA_LABELS.get(persona, persona),
        "write_mode": write_mode,
        "meta": meta,
        "data_ref": data_ref,
        "verify_checklist": build_verify_checklist(meta),
        "parts": {
            "hook": hook,
            "body": body,
            "cta": cta,
            "disclaimer": DISCLAIMER,
        },
        "full_text": full_text,
        "sources": meta.get("source_urls") or [],
        "creator_note": meta.get("creator_note", ""),
    }
    from script_safety import lint_script_document  # noqa: WPS433

    lint_script_document(doc)
    return doc


def build_ai_prompt(doc: dict[str, Any]) -> str:
    meta = doc.get("meta") or {}
    data_block = "\n".join(f"- {line}" for line in doc.get("data_ref") or []) or "（请补充可查数据）"
    sources = "\n".join(f"- {u}" for u in doc.get("sources") or []) or "（无固定来源，写稿前须补充）"
    checklist = "\n".join(f"- {c['text']}" for c in doc.get("verify_checklist") or [])

    mode_note = {
        "hook_only": "本条为 hook_only：只能写「大家在讨论」，禁止写成医学定论。",
        "cite_directly": "可引用来源，但必须标注链接且加非医疗建议。",
        "verify_before_script": "写稿前须核实关键数字；无 A/B 来源的数字标「待核实」。",
    }.get(doc.get("write_mode", "verify_before_script"), "")

    forbidden = meta.get("forbidden_expressions") or (meta.get("gate") or {}).get("forbidden_expressions") or []
    hedges = meta.get("required_hedges") or (meta.get("gate") or {}).get("required_hedges") or []
    forbidden_block = "\n".join(f"- 禁止出现：{e}" for e in forbidden) if forbidden else "- （无 Gate 级禁止词）"
    hedge_block = "\n".join(f"- 建议降权：{h}" for h in hedges) if hedges else "- 目前证据有限 / 个体差异较大"

    return f"""【口播文案生成 Prompt · 血糖科普 · 非医生创作者】

## 选题
{doc['title']}

## 平台 / 时长 / 人设
- 平台：{doc.get('platform_label', doc.get('platform'))}
- 时长：{doc.get('duration_sec')} 秒
- 人设：{doc.get('persona_label', doc.get('persona'))}
- 写稿模式：{doc.get('write_mode')} — {mode_note}

## 证据与用法
- 证据层级：{meta.get('evidence_tier', '—')}
- use_as：{meta.get('use_as', '—')}
- 创作者提示：{meta.get('creator_note') or doc.get('creator_note') or '—'}

## 核心数据 / 知识点
{data_block}

## 来源链接（口播或简介须可追溯）
{sources}

## 写稿前核实清单
{checklist}

## Gate 语言约束（与 script_safety 同源）
{forbidden_block}
{hedge_block}

## 结构
1. 钩子 3-5 秒
2. 正文（口语化，单句宜短）
3. CTA
4. 结尾必须含：{DISCLAIMER}

## 禁止
- 根治 / 保证逆转 / 替医嘱用药
- 把 UGC 标题写成「研究表明你一定…」
"""


def find_discovered_topic(topic_id: str) -> dict | None:
    data = load_discovered_topics()
    for topic in data.get("topics", []):
        if topic.get("id") == topic_id:
            return topic
    return None


def harvest_meta_from_topic(topic: dict) -> dict[str, Any]:
    hm = topic.get("harvest_meta") or {}
    auth = hm.get("authenticity") or {}
    return {
        "use_as": hm.get("use_as") or auth.get("use_as"),
        "evidence_tier": hm.get("evidence_tier") or auth.get("evidence_tier"),
        "creator_note": hm.get("creator_note") or auth.get("creator_note"),
        "adversarial_flags": auth.get("adversarial_flags") or [],
        "source_urls": topic.get("source_urls") or [],
        "topic_score": hm.get("topic_score"),
    }


def find_harvest_item(harvest: dict, *, url: str = "", title: str = "") -> dict | None:
    items = harvest.get("items") or []
    if url:
        for it in items:
            if it.get("url") == url:
                return it
    if title:
        key = normalize_text(title)
        for it in items:
            if normalize_text(it.get("title", "")) == key:
                return it
    return None


def harvest_item_meta(item: dict) -> dict[str, Any]:
    auth = item.get("authenticity") or {}
    gate = item.get("gate") or {}
    return {
        "use_as": gate.get("use_as") or auth.get("use_as"),
        "evidence_tier": auth.get("evidence_tier"),
        "creator_note": gate.get("creator_note") or auth.get("creator_note"),
        "adversarial_flags": auth.get("adversarial_flags") or [],
        "source_urls": [item["url"]] if item.get("url") else [],
        "topic_score": item.get("writability_score") or item.get("topic_score"),
        "writability_score": item.get("writability_score") or item.get("topic_score"),
        "heat_score": item.get("heat_score"),
        "platform": item.get("platform"),
        "gate": gate,
        "allowed_frame": gate.get("allowed_frame"),
        "forbidden_expressions": gate.get("forbidden_expressions") or [],
        "required_hedges": gate.get("required_hedges") or [],
        "claims": item.get("claims") or [],
    }


def next_script_id() -> str:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    index = load_scripts_index()
    today = datetime.now().strftime("%Y%m%d")
    existing = [s["id"] for s in index.get("scripts", []) if s.get("id", "").startswith(f"script-{today}")]
    seq = len(existing) + 1
    return f"script-{today}-{seq:03d}"


def load_scripts_index() -> dict:
    path = SCRIPTS_DIR / "index.json"
    if not path.exists():
        return {"version": "1.0", "updated": "", "scripts": []}
    return load_json(path)


def save_scripts_index(index: dict) -> Path:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    index["updated"] = datetime.now().isoformat(timespec="seconds")
    path = SCRIPTS_DIR / "index.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    return path


def save_script_record(
    doc: dict[str, Any],
    *,
    topic_id: str | None = None,
    script_status: str = "draft",
    publish_status: str = "pending",
) -> dict[str, Any]:
    script_id = next_script_id()
    record = {
        "id": script_id,
        "topic_id": topic_id,
        "title": doc["title"],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "platform": doc.get("platform"),
        "write_mode": doc.get("write_mode"),
        "evidence_tier": (doc.get("meta") or {}).get("evidence_tier"),
        "script_status": script_status,
        "publish_status": publish_status,
        "verify_checklist": doc.get("verify_checklist"),
        "safety_report": doc.get("safety_report"),
        "source_urls": doc.get("sources") or [],
        "data_ref": doc.get("data_ref") or [],
        "parts": doc.get("parts"),
        "full_text": doc.get("full_text"),
        "ai_prompt": build_ai_prompt(doc),
    }
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = SCRIPTS_DIR / f"{script_id}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    index = load_scripts_index()
    index.setdefault("scripts", []).insert(
        0,
        {
            "id": script_id,
            "topic_id": topic_id,
            "title": doc["title"],
            "created_at": record["created_at"],
            "platform": doc.get("platform"),
            "write_mode": doc.get("write_mode"),
            "script_status": script_status,
            "publish_status": publish_status,
            "file": f"scripts/{script_id}.json",
        },
    )
    save_scripts_index(index)
    return {
        "id": script_id,
        "path": f"data/scripts/{script_id}.json",
        "record": record,
    }


def update_discovered_topic_status(
    topic_id: str,
    *,
    script_status: str | None = None,
    publish_status: str | None = None,
    script_file: str | None = None,
) -> bool:
    if not TOPICS_FILE.exists():
        return False
    data = load_json(TOPICS_FILE)
    updated = False
    for topic in data.get("topics", []):
        if topic.get("id") != topic_id:
            continue
        if script_status:
            topic["script_status"] = script_status
        if publish_status:
            topic["publish_status"] = publish_status
        if script_file:
            topic["script_file"] = script_file
        updated = True
        break
    if updated:
        data["updated"] = datetime.now().strftime("%Y-%m-%d")
        with open(TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return updated
