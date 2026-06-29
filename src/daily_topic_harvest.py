#!/usr/bin/env python3
"""
每日选题采集 — 多平台一键抓取、评分、出日报

TraeWork / 计划任务入口:
    python src/daily_topic_harvest.py

输出:
    data/exports/daily-harvest-YYYY-MM-DD.json
    research-daily/YYYY-MM-DD-采集日报.md
    research-daily/YYYY-MM-DD-采集日报.html
    data/discovered-topics.json（高价值条目增量写入）
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote

# 同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from platform_scraper import (  # noqa: E402
    DATA_DIR,
    PROJECT_ROOT,
    SEARCH_KEYWORDS,
    TOPICS_FILE,
    classify_topic,
    dedup_key,
    estimate_duration,
    estimate_heat,
    fetch,
    generate_topic_id,
    get_bilibili_hot,
    load_existing_topics,
    save_topics,
    search_bilibili,
)
from script_knowledge import enrich_data_ref  # noqa: E402

EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
REPORT_DIR = os.path.join(PROJECT_ROOT, "research-daily")

PLATFORM_LABELS = {
    "bili": "B站",
    "xhs": "小红书",
    "zhihu": "知乎",
    "youtube": "YouTube",
    "twitter": "X/Twitter",
    "reddit": "Reddit",
    "authority": "权威来源",
    "exa": "全网网页(Exa)",
    "jina": "全网网页(Jina)",
    "v2ex": "V2EX",
    "web": "网页",
}

# 年轻人入口词（代谢焦虑）+ 传统词（platform_scraper 内置）
YOUTH_KEYWORDS = [
    "胰岛素抵抗",
    "糖前期",
    "糖耐量异常",
    "空腹血糖正常 餐后高",
    "体检 血糖偏高",
    "糖化血红蛋白",
    "饭后犯困 血糖",
    "奶茶 控糖",
    "减肥平台期 胰岛素",
    "代谢综合征",
    "35岁 血糖",
    "动态血糖仪",
    "糖友 年轻人",
]

DEFAULT_HARVEST_KEYWORDS = list(
    dict.fromkeys(YOUTH_KEYWORDS + list(SEARCH_KEYWORDS))
)

SENSATIONAL = [
    "根治", "治愈保证", "神药", "被骗", "一夜", "百分百", "千万别",
    "跌落神坛", "惊呆", "暴涨", "万病之源", "一招", "秘方", "包治",
]
ABSOLUTE_CLAIMS = ["所有人都", "一定治", "保证逆转", "永不复发", "替换药物"]
CREDIBLE_AUTHOR = [
    "医生", "医师", "营养师", "医院", "主任", "教授", "指南", "学会", "疾控", "大夫",
]
CREDIBLE_URL = [
    ".gov.cn", "who.int", "nih.gov", "nejm.org", "thelancet.com",
    "diabetesjournals.org", "cnki.net", "dxy.cn", "haodf.com", "medlive.cn",
]
AUTHORITY_SITES = ["nhc.gov.cn", "dxy.cn", "who.int", "nih.gov"]

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

OPENCLI_CMD = "opencli.cmd" if os.name == "nt" else "opencli"
MCPORTER_CMD = "mcporter.cmd" if os.name == "nt" else "mcporter"


def run_cmd(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def parse_count(raw: Any) -> int:
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


def parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:10], fmt)
        except ValueError:
            continue
    return None


def passes_health_relevance(*texts: str) -> bool:
    blob = " ".join(t for t in texts if t)
    return bool(HEALTH_SIGNAL.search(blob))


def passes_twitter_filter(text: str, author: str = "", bio: str = "") -> bool:
    blob = f"{text} {author} {bio}"
    if TWITTER_NOISE.search(blob):
        return False
    return passes_health_relevance(text, bio)


def adversarial_audit(
    title: str,
    author: str,
    url: str,
    platform: str,
    snippet: str = "",
) -> dict[str, Any]:
    """
    第一性原理：可验证性 + 证据层级 + 误导伤害 + 动机（带货/恐惧/绝对化）
    对抗性审核：假设作者在最大化传播而非最大化真相，反向打标。
    """
    t, a, u, s = title or "", author or "", url or "", snippet or ""
    blob = f"{t} {s} {a}"
    flags: list[str] = []
    reasons: list[str] = []
    score = 50

    # 证据层级（A 最高）
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

    # 创作者用法（非医生）
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


def score_authenticity(title: str, author: str, url: str, platform: str, snippet: str = "") -> dict[str, Any]:
    return adversarial_audit(title, author, url, platform, snippet)


def score_importance(
    title: str,
    keyword: str,
    metrics: dict[str, Any],
    published_at: str | None = None,
) -> dict[str, Any]:
    score = 40
    reasons: list[str] = []

    engagement = max(
        parse_count(metrics.get("play")),
        parse_count(metrics.get("likes")),
        parse_count(metrics.get("replies")),
        parse_count(metrics.get("views")),
    )
    if engagement >= 500_000:
        score += 35
        reasons.append(f"互动量极高({engagement:,})")
    elif engagement >= 100_000:
        score += 28
        reasons.append(f"互动量高({engagement:,})")
    elif engagement >= 10_000:
        score += 18
        reasons.append(f"互动量中等({engagement:,})")
    elif engagement >= 1_000:
        score += 10
        reasons.append(f"有一定互动({engagement:,})")

    if keyword and (keyword in (title or "") or keyword.split()[0] in (title or "")):
        score += 12
        reasons.append(f"命中关键词「{keyword}」")

    dt = parse_date(published_at)
    if dt and dt >= datetime.now() - timedelta(days=7):
        score += 15
        reasons.append("近 7 天发布")
    elif dt and dt >= datetime.now() - timedelta(days=30):
        score += 8
        reasons.append("近 30 天发布")

    score = max(0, min(100, score))
    if score >= 75:
        label = "高"
    elif score >= 50:
        label = "中"
    else:
        label = "低"
    return {"score": score, "label": label, "reasons": reasons[:4]}


def make_item(
    platform: str,
    title: str,
    url: str,
    *,
    author: str = "",
    keyword: str = "",
    metrics: dict | None = None,
    published_at: str | None = None,
    snippet: str = "",
    raw: dict | None = None,
) -> dict[str, Any]:
    metrics = metrics or {}
    auth = adversarial_audit(title, author, url, platform, snippet)
    imp = score_importance(title, keyword, metrics, published_at)
    topic_score = round(auth["score"] * 0.5 + imp["score"] * 0.5)
    blocked = (
        auth["evidence_tier"] == "E"
        or "off_topic_noise" in auth["adversarial_flags"]
        or (auth["use_as"] == "hook_only" and auth["score"] < 60)
    )
    topic_pick = (
        not blocked
        and auth["use_as"] in ("cite_directly", "verify_before_script", "safe_to_discuss")
        and topic_score >= 62
        and auth["score"] >= 50
    )
    return {
        "platform": platform,
        "platform_label": PLATFORM_LABELS.get(platform, platform),
        "title": title.strip(),
        "url": url,
        "author": author,
        "keyword": keyword,
        "snippet": snippet,
        "metrics": metrics,
        "published_at": published_at,
        "category": classify_topic(title),
        "authenticity": auth,
        "importance": imp,
        "topic_score": topic_score,
        "topic_pick": topic_pick,
        "raw": raw,
    }


def apply_cross_platform_boost(items: list[dict]) -> None:
    """多平台同主题 → 重要性加分（年轻人热议信号）"""
    buckets: dict[str, list[dict]] = {}
    for it in items:
        k = dedup_key(it["title"])
        buckets.setdefault(k, []).append(it)
    for group in buckets.values():
        if len(group) < 2:
            continue
        plats = sorted({it["platform"] for it in group})
        for it in group:
            imp = it["importance"]
            imp["score"] = min(100, imp["score"] + 10 + 2 * len(plats))
            imp["reasons"].append(f"多平台同热({'+'.join(plats)})")
            auth = it["authenticity"]
            it["topic_score"] = round(auth["score"] * 0.5 + imp["score"] * 0.5)
            blocked = (
                auth["evidence_tier"] == "E"
                or "off_topic_noise" in auth.get("adversarial_flags", [])
            )
            it["topic_pick"] = (
                not blocked
                and auth["use_as"] in ("cite_directly", "verify_before_script", "safe_to_discuss")
                and it["topic_score"] >= 62
                and auth["score"] >= 50
            )


# ── 采集器 ─────────────────────────────────────────


def collect_bilibili(keywords: list[str], per_kw: int = 5) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for kw in keywords:
        for r in search_bilibili(kw, pagesize=per_kw):
            if r["title"] in seen:
                continue
            seen.add(r["title"])
            items.append(
                make_item(
                    "bili",
                    r["title"],
                    r["link"],
                    author=r.get("author", ""),
                    keyword=kw,
                    metrics={"play": r.get("play"), "danmaku": r.get("danmaku")},
                    raw=r,
                )
            )
        time.sleep(0.3)

    try:
        for hot in get_bilibili_hot()[:5]:
            kw = hot.get("keyword", "")
            if not kw or kw in seen:
                continue
            seen.add(kw)
            items.append(
                make_item(
                    "bili",
                    f"[B站热搜] {kw}",
                    f"https://search.bilibili.com/all?keyword={quote(kw)}",
                    keyword=kw,
                    metrics={"heat_score": hot.get("heat_score")},
                    snippet="B站热搜榜健康相关词",
                )
            )
    except Exception as e:
        errors.append({"platform": "bili", "stage": "hot", "error": str(e)})

    return items, errors


def collect_xiaohongshu(keywords: list[str], per_kw: int = 8) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for kw in keywords[:6]:
        code, out, err = run_cmd(
            [OPENCLI_CMD, "xiaohongshu", "search", kw, "-f", "json"],
            timeout=90,
        )
        if code != 0:
            errors.append({"platform": "xhs", "keyword": kw, "error": (err or out)[:300]})
            continue
        try:
            start = out.find("[")
            payload = json.loads(out[start:]) if start >= 0 else []
        except json.JSONDecodeError as e:
            errors.append({"platform": "xhs", "keyword": kw, "error": f"JSON parse: {e}"})
            continue
        for row in payload[:per_kw]:
            title = row.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            items.append(
                make_item(
                    "xhs",
                    title,
                    row.get("url", ""),
                    author=row.get("author", ""),
                    keyword=kw,
                    metrics={"likes": row.get("likes")},
                    published_at=row.get("published_at"),
                    raw=row,
                )
            )
        time.sleep(2)

    return items, errors


def collect_youtube(keywords: list[str], per_kw: int = 4) -> tuple[list[dict], list[dict]]:
    """YouTube 关键词搜索（yt-dlp），与「全网网页搜索」不同。"""
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    ytdlp = "yt-dlp.exe" if os.name == "nt" else "yt-dlp"

    for kw in keywords[:5]:
        code, out, err = run_cmd(
            [ytdlp, "--flat-playlist", "--dump-json", f"ytsearch{per_kw}:{kw}"],
            timeout=120,
        )
        if code != 0:
            errors.append({"platform": "youtube", "keyword": kw, "error": (err or out)[:300]})
            continue
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            title = row.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            vid = row.get("id", "")
            url = row.get("webpage_url") or f"https://www.youtube.com/watch?v={vid}"
            items.append(
                make_item(
                    "youtube",
                    title,
                    url,
                    author=row.get("channel") or row.get("uploader", ""),
                    keyword=kw,
                    metrics={"views": row.get("view_count")},
                    snippet=(row.get("description") or "")[:160],
                    raw=row,
                )
            )
        time.sleep(1)

    return items, errors


def collect_twitter(keywords: list[str], per_kw: int = 5) -> tuple[list[dict], list[dict]]:
    """X/Twitter：健康相关过滤 + 对抗性噪音剔除"""
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    queries = [
        "insulin resistance",
        "prediabetes",
        "CGM glucose",
        "blood sugar after meal",
        "胰岛素抵抗",
    ]

    for q in queries:
        code, out, err = run_cmd(
            [OPENCLI_CMD, "twitter", "search", q, "-f", "json"],
            timeout=90,
        )
        if code != 0:
            errors.append({"platform": "twitter", "keyword": q, "error": (err or out)[:300]})
            continue
        try:
            start = out.find("[")
            payload = json.loads(out[start:]) if start >= 0 else []
        except json.JSONDecodeError as e:
            errors.append({"platform": "twitter", "keyword": q, "error": f"JSON parse: {e}"})
            continue
        for row in payload[:per_kw]:
            text = (row.get("text") or "").replace("\n", " ")
            bio = row.get("bio") or ""
            author = row.get("author") or ""
            if not passes_twitter_filter(text, author, bio):
                continue
            key = text[:100]
            if not key or key in seen:
                continue
            seen.add(key)
            title = text if len(text) <= 80 else text[:77] + "..."
            items.append(
                make_item(
                    "twitter",
                    title,
                    row.get("url", ""),
                    author=author,
                    keyword=q,
                    metrics={"likes": row.get("likes"), "views": row.get("views")},
                    published_at=(row.get("created_at") or "")[:16],
                    snippet=text[:200],
                    raw=row,
                )
            )
        time.sleep(2)

    return items, errors


def collect_zhihu(keywords: list[str], per_kw: int = 6) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()

    for kw in keywords[:8]:
        code, out, err = run_cmd(
            [OPENCLI_CMD, "zhihu", "search", kw, "-f", "json"],
            timeout=90,
        )
        if code != 0:
            errors.append({"platform": "zhihu", "keyword": kw, "error": (err or out)[:300]})
            continue
        try:
            start = out.find("[")
            payload = json.loads(out[start:]) if start >= 0 else []
        except json.JSONDecodeError as e:
            errors.append({"platform": "zhihu", "keyword": kw, "error": f"JSON parse: {e}"})
            continue
        for row in payload[:per_kw]:
            title = row.get("title", "")
            if not title or title in seen:
                continue
            if not passes_health_relevance(title, row.get("author", "")):
                continue
            seen.add(title)
            items.append(
                make_item(
                    "zhihu",
                    title,
                    row.get("url", ""),
                    author=row.get("author", ""),
                    keyword=kw,
                    metrics={"votes": row.get("votes")},
                    snippet=row.get("type", ""),
                    raw=row,
                )
            )
        time.sleep(2)

    return items, errors


def collect_reddit(keywords: list[str], per_kw: int = 5) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    queries = ["prediabetes", "blood sugar", "CGM diabetes", "insulin resistance"]

    for q in queries:
        code, out, err = run_cmd(
            [OPENCLI_CMD, "reddit", "search", q, "-f", "json"],
            timeout=90,
        )
        if code != 0:
            errors.append({"platform": "reddit", "keyword": q, "error": (err or out)[:300]})
            continue
        try:
            start = out.find("[")
            payload = json.loads(out[start:]) if start >= 0 else []
        except json.JSONDecodeError as e:
            errors.append({"platform": "reddit", "keyword": q, "error": f"JSON parse: {e}"})
            continue
        for row in payload[:per_kw]:
            title = row.get("title") or row.get("text", "")[:80]
            if not title or title in seen:
                continue
            if not passes_health_relevance(title, row.get("text", "")):
                continue
            seen.add(title)
            items.append(
                make_item(
                    "reddit",
                    title,
                    row.get("url", ""),
                    author=row.get("author") or row.get("subreddit", ""),
                    keyword=q,
                    metrics={"votes": row.get("score") or row.get("ups")},
                    snippet=(row.get("text") or "")[:160],
                    raw=row,
                )
            )
        time.sleep(2)

    return items, errors


def collect_authority_sources() -> tuple[list[dict], list[dict]]:
    """定向搜卫健委、丁香等权威域（提升可引用来源比例）"""
    items: list[dict] = []
    errors: list[dict] = []
    seen: set[str] = set()
    queries = [
        "国家卫健委 成人糖尿病食养指南",
        "丁香医生 胰岛素抵抗 科普",
        "中华医学会 糖前期 筛查",
        "WHO diabetes diet guideline",
    ]
    for q in queries:
        jina_items, jina_err = collect_jina_search(q, limit=5)
        if jina_err:
            errors.extend(jina_err)
        for raw in jina_items:
            url = raw.get("url", "")
            if not any(d in url for d in AUTHORITY_SITES + ["dxy.cn", "nhc.gov.cn", "who.int"]):
                continue
            title = raw.get("title", "")
            if not title or title in seen:
                continue
            seen.add(title)
            items.append(
                make_item(
                    "authority",
                    title,
                    url,
                    keyword=q,
                    snippet=raw.get("snippet", ""),
                )
            )
        time.sleep(0.5)
    return items, errors


def collect_v2ex() -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    data = fetch("https://www.v2ex.com/api/topics/hot.json", headers={"User-Agent": "agent-reach/1.0"})
    if "_error" in data:
        errors.append({"platform": "v2ex", "error": data["_error"]})
        return items, errors
    health_kw = ["糖", "健康", "医", "饮食", "运动", "减肥", "数据", "AI"]
    for t in data[:30]:
        title = t.get("title", "")
        if not any(k in title for k in health_kw):
            continue
        items.append(
            make_item(
                "v2ex",
                title,
                t.get("url", ""),
                author=t.get("member", {}).get("username", ""),
                metrics={"replies": t.get("replies", 0)},
                snippet=t.get("content", "")[:120],
                raw=t,
            )
        )
    return items, errors


def collect_exa(keywords: list[str], per_kw: int = 5) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []

    for kw in keywords[:4]:
        query = f"{kw} 糖尿病 控糖"
        code, out, err = run_cmd(
            [
                MCPORTER_CMD,
                "call",
                f'exa.web_search_exa(query: "{query}", numResults: {per_kw})',
            ],
            timeout=90,
        )
        if code != 0:
            jina_items, jina_err = collect_jina_search(kw, per_kw)
            items.extend(jina_items)
            if jina_err:
                errors.append({"platform": "exa", "keyword": kw, "error": (err or out)[:200], "fallback": "jina"})
            continue
        rows = _parse_mcporter_results(out)
        for row in rows:
            items.append(
                make_item(
                    "exa",
                    row.get("title", ""),
                    row.get("url", ""),
                    keyword=kw,
                    snippet=row.get("snippet", ""),
                    published_at=row.get("published_at"),
                    raw=row,
                )
            )
        time.sleep(0.5)

    return items, errors


def collect_jina_search(keyword: str, limit: int = 5) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    errors: list[dict] = []
    url = f"https://s.jina.ai/{quote(keyword + ' 血糖 控糖')}"
    code, out, err = run_cmd(["curl", "-sL", url], timeout=60)
    if code != 0:
        errors.append({"platform": "jina", "keyword": keyword, "error": err or out})
        return items, errors
    for block in re.split(r"\n(?=\d+\.\s)", out.strip()):
        m = re.match(r"(\d+)\.\s*(.+?)\n\s*URL:\s*(\S+)", block, re.S)
        if not m:
            continue
        title = m.group(2).strip().split("\n")[0]
        link = m.group(3).strip()
        snippet = block[m.end() :].strip()[:200] if m.end() < len(block) else ""
        items.append(
            make_item("jina", title, link, keyword=keyword, snippet=snippet)
        )
        if len(items) >= limit:
            break
    return items, errors


def _parse_mcporter_results(text: str) -> list[dict]:
    rows: list[dict] = []
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data = data.get("results") or data.get("data") or [data]
        if isinstance(data, list):
            for r in data:
                rows.append(
                    {
                        "title": r.get("title") or r.get("name", ""),
                        "url": r.get("url") or r.get("link", ""),
                        "snippet": r.get("snippet") or r.get("text", ""),
                        "published_at": r.get("publishedDate") or r.get("published_at"),
                    }
                )
            return rows
    except json.JSONDecodeError:
        pass
    for m in re.finditer(r"Title:\s*(.+?)\n\s*URL:\s*(\S+)", text, re.I):
        rows.append({"title": m.group(1).strip(), "url": m.group(2).strip(), "snippet": ""})
    return rows


# ── 选题写入 ─────────────────────────────────────


def promote_to_topics(items: list[dict], existing: dict) -> list[dict]:
    picks = [i for i in items if i.get("topic_pick")]
    picks.sort(key=lambda x: x["topic_score"], reverse=True)
    picks = picks[:12]

    existing_ids = {t["id"] for t in existing["topics"]}
    existing_keys = {dedup_key(t["title"]) for t in existing["topics"]}
    added: list[dict] = []

    for it in picks:
        dk = dedup_key(it["title"])
        if dk in existing_keys:
            continue
        play = parse_count(it["metrics"].get("play"))
        likes = parse_count(it["metrics"].get("likes"))
        heat = estimate_heat(play or likes)
        topic = {
            "id": generate_topic_id(existing_ids),
            "title": it["title"][:80],
            "angle": (
                f"{it['platform_label']} · 证据层级{it['authenticity'].get('evidence_tier','?')} · "
                f"{it['authenticity'].get('use_as','')} · "
                f"{it['authenticity'].get('creator_note','')}"[:220]
            ),
            "category": it["category"],
            "platform": {
                "bili": "bili,dy", "xhs": "xhs,dy", "zhihu": "xhs,dy", "youtube": "bili,dy",
                "twitter": "dy,bili", "reddit": "bili", "authority": "dy,xhs",
                "exa": "dy,bili", "jina": "dy,bili", "v2ex": "bili",
            }.get(it["platform"], "dy,xhs"),
            "duration": estimate_duration(it["title"], play or likes),
            "heat": heat,
            "heat_source": (
                f"每日采集 {it['platform_label']} · 选题分 {it['topic_score']} · "
                f"互动 {play or likes or '-'}"
            ),
            "source_urls": [it["url"]] if it.get("url") else [],
            "status": "discovered",
            "script_status": "pending",
            "publish_status": "pending",
            "discovered_date": datetime.now().strftime("%Y-%m-%d"),
            "harvest_meta": {
                "authenticity": it["authenticity"],
                "importance": it["importance"],
                "topic_score": it["topic_score"],
                "platform": it["platform"],
                "evidence_tier": it["authenticity"].get("evidence_tier"),
                "use_as": it["authenticity"].get("use_as"),
                "creator_note": it["authenticity"].get("creator_note"),
            },
        }
        enriched = enrich_data_ref(
            it["title"],
            angle=topic["angle"],
            snippet=it.get("snippet") or "",
        )
        topic["data_ref"] = enriched["data_ref"]
        existing["topics"].append(topic)
        existing_ids.add(topic["id"])
        existing_keys.add(dk)
        added.append(topic)

    if added:
        save_topics(existing)
    return added


# ── 报告 ─────────────────────────────────────────


def build_summary(items: list[dict], errors: list[dict], added: list[dict]) -> dict:
    by_platform: dict[str, int] = {}
    picks = 0
    for it in items:
        by_platform[it["platform"]] = by_platform.get(it["platform"], 0) + 1
        if it.get("topic_pick"):
            picks += 1
    return {
        "total_raw": len(items),
        "by_platform": by_platform,
        "topic_candidates": picks,
        "new_topics_added": len(added),
        "errors": errors,
        "platforms_ok": sorted(by_platform.keys()),
        "platforms_failed": sorted({e["platform"] for e in errors}),
    }


def render_markdown(report_date: str, summary: dict, items: list[dict], added: list[dict]) -> str:
    lines = [
        f"# 每日选题采集日报 · {report_date}",
        "",
        f"> 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "> 非医生创作者：条目含证据层级(A-E)与对抗性标记；`hook_only` 仅作选题钩子，不可当医学结论",
        "",
        "## 一、采集统计",
        "",
        f"| 指标 | 数值 |",
        f"|------|------|",
        f"| 原始条目 | {summary['total_raw']} |",
        f"| 选题候选(评分达标) | {summary['topic_candidates']} |",
        f"| 写入 discovered-topics | {summary['new_topics_added']} |",
        "",
        "### 各平台采集量",
        "",
    ]
    for p, n in sorted(summary["by_platform"].items(), key=lambda x: -x[1]):
        lines.append(f"- **{PLATFORM_LABELS.get(p, p)}**：{n} 条")
    if summary["errors"]:
        lines.extend(["", "### 采集异常", ""])
        for e in summary["errors"]:
            lines.append(f"- `{e.get('platform')}`：{e.get('error', '')[:120]}")
    lines.extend(["", "## 二、推荐选题（按选题分排序）", ""])
    ranked = sorted(items, key=lambda x: x["topic_score"], reverse=True)[:25]
    for i, it in enumerate(ranked, 1):
        pick = "✅" if it.get("topic_pick") else "—"
        lines.extend(
            [
                f"### {i}. {it['title']}",
                "",
                f"- **平台**：{it['platform_label']}",
                f"- **原贴**：<{it['url']}>" if it.get("url") else "- **原贴**：—",
                f"- **作者**：{it.get('author') or '—'}",
                f"- **分类**：{it['category']}",
                f"- **真实性**：{it['authenticity']['label']} ({it['authenticity']['score']}/100)",
                f"- **证据层级**：{it['authenticity'].get('evidence_tier', '—')}",
                f"- **用法**：{it['authenticity'].get('use_as', '—')}",
                f"- **创作者提示**：{it['authenticity'].get('creator_note', '—')}",
                f"- **对抗性标记**：{', '.join(it['authenticity'].get('adversarial_flags') or []) or '无'}",
                f"- **重要性**：{it['importance']['label']} ({it['importance']['score']}/100)",
                f"- **选题分**：{it['topic_score']} {pick}",
                f"- **真实性依据**：{'；'.join(it['authenticity']['reasons']) or '—'}",
                f"- **重要性依据**：{'；'.join(it['importance']['reasons']) or '—'}",
                "",
            ]
        )
    if added:
        lines.extend(["## 三、本次新增到选题库", ""])
        for t in added:
            lines.append(f"- `{t['id']}` {t['title']}")
    lines.extend(
        [
            "",
            "---",
            "",
            "**评分说明（第一性原理 + 对抗性审核）**",
            "- 证据层级：A 指南/政府/期刊 → B 医疗平台 → C 持证作者 → D UGC → E 高风险/噪音",
            "- 对抗性：假设作者在最大化传播，标记夸张词/绝对化/带货/离题",
            "- `hook_only`：只讨论「大家在聊什么」，不写稿为医学事实",
            "- 自动入库：证据非 E、use_as 可写稿、选题分≥62、真实性≥50",
            "",
        ]
    )
    return "\n".join(lines)


def render_html(report_date: str, summary: dict, items: list[dict], added: list[dict]) -> str:
    ranked = sorted(items, key=lambda x: x["topic_score"], reverse=True)[:30]
    rows = []
    for it in ranked:
        auth = it["authenticity"]
        imp = it["importance"]
        pick_cls = "pick-yes" if it.get("topic_pick") else "pick-no"
        rows.append(
            f"""<tr>
  <td><span class="plat">{html.escape(it['platform_label'])}</span></td>
  <td><a href="{html.escape(it.get('url',''))}" target="_blank" rel="noopener">{html.escape(it['title'])}</a>
    <div class="sub">{html.escape(it.get('author') or '')}</div></td>
  <td>{auth.get('evidence_tier','?')}<br><small>{auth['label']} {auth['score']}</small></td>
  <td><small>{html.escape(auth.get('use_as',''))}</small></td>
  <td>{imp['label']}<br><small>{imp['score']}</small></td>
  <td><strong>{it['topic_score']}</strong></td>
  <td class="{pick_cls}">{'入库' if it.get('topic_pick') else '仅钩子'}</td>
</tr>"""
        )
    err_html = ""
    if summary["errors"]:
        err_html = "<ul>" + "".join(
            f"<li><code>{html.escape(e.get('platform',''))}</code> {html.escape(str(e.get('error',''))[:100])}</li>"
            for e in summary["errors"]
        ) + "</ul>"
    plat_cards = "".join(
        f'<div class="stat"><b>{n}</b><span>{html.escape(PLATFORM_LABELS.get(p,p))}</span></div>'
        for p, n in sorted(summary["by_platform"].items(), key=lambda x: -x[1])
    )
    added_html = ""
    if added:
        added_html = "<h2>本次写入选题库</h2><ul>" + "".join(
            f"<li><code>{html.escape(t['id'])}</code> {html.escape(t['title'])}</li>" for t in added
        ) + "</ul>"

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>选题采集日报 · {report_date}</title>
<style>
:root {{ --bg:#0f1117; --bg2:#1a1d27; --ink:#e8eaed; --muted:#8b8fa3; --accent:#00d4aa; --rule:#2a2d3a; }}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family:-apple-system,'Segoe UI','Noto Sans CJK SC',sans-serif; background:var(--bg); color:var(--ink); line-height:1.6; }}
.wrap {{ max-width:1100px; margin:0 auto; padding:28px 18px; }}
h1 {{ font-size:24px; margin-bottom:6px; }}
.meta {{ color:var(--muted); font-size:13px; margin-bottom:20px; }}
.stats {{ display:flex; flex-wrap:wrap; gap:12px; margin:16px 0 24px; }}
.stat {{ background:var(--bg2); border:1px solid var(--rule); border-radius:10px; padding:12px 16px; min-width:100px; }}
.stat b {{ display:block; font-size:22px; color:var(--accent); }}
.stat span {{ font-size:12px; color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th,td {{ border-bottom:1px solid var(--rule); padding:10px 8px; text-align:left; vertical-align:top; }}
th {{ color:var(--muted); font-weight:600; }}
.plat {{ background:rgba(0,212,170,.12); color:var(--accent); padding:2px 8px; border-radius:6px; font-size:11px; }}
.sub {{ color:var(--muted); font-size:11px; margin-top:4px; }}
.pick-yes {{ color:var(--accent); font-weight:700; }}
.pick-no {{ color:var(--muted); }}
a {{ color:#6c8cff; text-decoration:none; }}
h2 {{ font-size:16px; margin:24px 0 12px; color:var(--accent); }}
</style></head><body><div class="wrap">
<h1>每日选题采集日报</h1>
<p class="meta">{report_date} · 原始 {summary['total_raw']} 条 · 候选 {summary['topic_candidates']} · 入库 {summary['new_topics_added']}</p>
<div class="stats">{plat_cards}</div>
{"<h2>采集异常</h2>" + err_html if err_html else ""}
<h2>条目明细（按选题分）</h2>
<table><thead><tr><th>平台</th><th>标题 / 原贴</th><th>证据/真实性</th><th>用法</th><th>重要性</th><th>选题分</th><th>建议</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
{added_html}
</div></body></html>"""


def save_report(report_date: str, payload: dict, md: str, html_doc: str) -> dict[str, str]:
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)
    json_path = os.path.join(EXPORTS_DIR, f"daily-harvest-{report_date}.json")
    md_path = os.path.join(REPORT_DIR, f"{report_date}-采集日报.md")
    html_path = os.path.join(REPORT_DIR, f"{report_date}-采集日报.html")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_doc)
    latest_pointer = os.path.join(EXPORTS_DIR, "latest-harvest.json")
    with open(latest_pointer, "w", encoding="utf-8") as f:
        json.dump(
            {
                "report_date": report_date,
                "path": os.path.basename(json_path),
                "json": f"exports/daily-harvest-{report_date}.json",
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    return {"json": json_path, "md": md_path, "html": html_path}


# ── 主流程 ───────────────────────────────────────


def run_harvest(
    keywords: list[str] | None = None,
    *,
    update_topics: bool = True,
    skip_xhs: bool = False,
    skip_twitter: bool = False,
    skip_youtube: bool = False,
    skip_zhihu: bool = False,
    skip_reddit: bool = False,
) -> dict[str, Any]:
    report_date = datetime.now().strftime("%Y-%m-%d")
    started = datetime.now().isoformat(timespec="seconds")
    keywords = keywords or DEFAULT_HARVEST_KEYWORDS

    print("=" * 56)
    print(f"[每日选题采集] {report_date}")
    print(f"[关键词] 年轻人向 {len(YOUTH_KEYWORDS)} + 传统 {len(SEARCH_KEYWORDS)}")
    print("=" * 56)

    all_items: list[dict] = []
    all_errors: list[dict] = []

    steps: list[tuple[str, Any]] = [
        ("权威来源", collect_authority_sources),
        ("B站", lambda: collect_bilibili(keywords)),
        ("YouTube", lambda: collect_youtube(keywords)),
        ("V2EX", collect_v2ex),
        ("全网网页", lambda: collect_exa(keywords)),
    ]
    if not skip_xhs:
        steps.insert(2, ("小红书", lambda: collect_xiaohongshu(keywords)))
    if not skip_zhihu:
        steps.insert(3 if not skip_xhs else 2, ("知乎", lambda: collect_zhihu(keywords)))
    if not skip_twitter:
        steps.insert(4, ("X/Twitter", lambda: collect_twitter(keywords)))
    if not skip_reddit:
        steps.insert(5, ("Reddit", lambda: collect_reddit(keywords)))
    if skip_youtube:
        steps = [s for s in steps if s[0] != "YouTube"]

    for name, fn in steps:
        print(f"\n→ 采集 {name}...")
        try:
            items, errs = fn()
            all_items.extend(items)
            all_errors.extend(errs)
            print(f"  获得 {len(items)} 条" + (f"，异常 {len(errs)}" if errs else ""))
        except Exception as e:
            all_errors.append({"platform": name, "error": str(e)})
            print(f"  失败: {e}")

    apply_cross_platform_boost(all_items)

    existing = load_existing_topics()
    added = promote_to_topics(all_items, existing) if update_topics else []

    summary = build_summary(all_items, all_errors, added)
    payload = {
        "version": "1.0",
        "report_date": report_date,
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "keywords": keywords,
        "summary": summary,
        "items": all_items,
        "added_topics": [{"id": t["id"], "title": t["title"]} for t in added],
    }
    paths = save_report(
        report_date,
        payload,
        render_markdown(report_date, summary, all_items, added),
        render_html(report_date, summary, all_items, added),
    )

    print("\n" + "=" * 56)
    print("[完成] 采集统计")
    print(f"  总条目: {summary['total_raw']}")
    for p, n in summary["by_platform"].items():
        print(f"  - {PLATFORM_LABELS.get(p,p)}: {n}")
    print(f"  选题候选: {summary['topic_candidates']}")
    print(f"  新写入选题库: {summary['new_topics_added']}")
    if summary["errors"]:
        print(f"  异常: {len(summary['errors'])} 项（见日报）")
    print("\n[输出文件]")
    for k, v in paths.items():
        print(f"  {k}: {v}")

    return payload


def main():
    parser = argparse.ArgumentParser(description="每日选题多平台采集")
    parser.add_argument("--keywords", help="逗号分隔关键词，默认用内置列表")
    parser.add_argument("--no-topics-update", action="store_true", help="不写入 discovered-topics.json")
    parser.add_argument("--skip-xhs", action="store_true", help="跳过小红书(OpenCLI)")
    parser.add_argument("--skip-twitter", action="store_true", help="跳过 X/Twitter(OpenCLI)")
    parser.add_argument("--skip-youtube", action="store_true", help="跳过 YouTube(yt-dlp)")
    parser.add_argument("--skip-zhihu", action="store_true", help="跳过知乎(OpenCLI)")
    parser.add_argument("--skip-reddit", action="store_true", help="跳过 Reddit(OpenCLI)")
    args = parser.parse_args()
    kws = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else None
    run_harvest(
        kws,
        update_topics=not args.no_topics_update,
        skip_xhs=args.skip_xhs,
        skip_twitter=args.skip_twitter,
        skip_youtube=args.skip_youtube,
        skip_zhihu=args.skip_zhihu,
        skip_reddit=args.skip_reddit,
    )


if __name__ == "__main__":
    main()
