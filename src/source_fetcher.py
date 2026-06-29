#!/usr/bin/env python3
"""从视频链接 / 网页拉取字幕、正文并提炼写稿要点。"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "source-cache"

HEALTH_KEYWORDS = (
    "血糖",
    "GI",
    "GL",
    "胰岛素",
    "mmol",
    "HbA1c",
    "糖化",
    "碳水",
    "控糖",
    "糖尿病",
    "代谢",
    "空腹",
    "餐后",
    "研究",
    "指南",
    "建议",
    "风险",
    "症状",
    "抵抗",
    "逆转",
    "缓解",
)

# 与 platform_scraper 一致的宽松 SSL（公开 API）
import ssl  # noqa: E402

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _http_json(url: str, referer: str = "") -> dict[str, Any]:
    headers = {"User-Agent": _UA, "Accept": "application/json"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=_CTX, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _http_text(url: str, referer: str = "") -> str:
    headers = {"User-Agent": _UA, "Accept": "text/plain,text/html,*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=_CTX, timeout=45) as resp:
        return resp.read().decode("utf-8", errors="replace")


def url_cache_key(url: str) -> str:
    return hashlib.sha256(url.strip().encode()).hexdigest()[:16]


def detect_source_type(url: str) -> str:
    u = (url or "").lower()
    if "bilibili.com" in u or "b23.tv" in u:
        return "bilibili"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    return "web"


def parse_bvid(url: str) -> str | None:
    m = re.search(r"BV[0-9A-Za-z]+", url or "")
    return m.group(0) if m else None


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"[。！？\n\r]+", text or "")
    out: list[str] = []
    for p in parts:
        p = re.sub(r"\s+", " ", p).strip()
        p = re.sub(r"^[\-\*•#\d\.、\s]+", "", p)
        if 8 <= len(p) <= 160:
            out.append(p)
    return out


def score_sentence(sentence: str) -> int:
    score = 0
    for kw in HEALTH_KEYWORDS:
        if kw.lower() in sentence.lower() or kw in sentence:
            score += 2 if len(kw) >= 3 else 1
    if re.search(r"\d", sentence):
        score += 2
    if any(x in sentence for x in ("误区", "注意", "建议", "标准", "正常", "异常")):
        score += 1
    return score


def extract_key_points(text: str, *, max_points: int = 8) -> list[str]:
    seen: set[str] = set()
    scored: list[tuple[int, str]] = []
    for s in split_sentences(text):
        key = re.sub(r"\s+", "", s)
        if key in seen:
            continue
        sc = score_sentence(s)
        if sc <= 0:
            continue
        seen.add(key)
        scored.append((sc, s))
    scored.sort(key=lambda x: (-x[0], -len(x[1])))
    return [s for _, s in scored[:max_points]]


def _subtitle_json_to_text(sub_json: dict) -> str:
    lines: list[str] = []
    for item in sub_json.get("body") or []:
        content = (item.get("content") or "").strip()
        if content:
            lines.append(content)
    # 合并短句为段落
    merged: list[str] = []
    buf = ""
    for line in lines:
        if len(buf) + len(line) < 42:
            buf = (buf + line).strip()
        else:
            if buf:
                merged.append(buf)
            buf = line
    if buf:
        merged.append(buf)
    return "\n".join(merged)


def fetch_bilibili(url: str) -> dict[str, Any]:
    bvid = parse_bvid(url)
    if not bvid:
        return {"ok": False, "error": "无法解析 BVID", "url": url, "type": "bilibili"}

    referer = f"https://www.bilibili.com/video/{bvid}"
    view = _http_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}", referer)
    if view.get("code") != 0:
        return {"ok": False, "error": view.get("message", "view API 失败"), "url": url, "type": "bilibili"}

    data = view["data"]
    title = data.get("title") or ""
    desc = (data.get("desc") or "").strip()
    tags = [t.get("tag_name", "") for t in (data.get("tag") or []) if t.get("tag_name")]
    cid = data.get("cid")
    aid = data.get("aid")

    transcript = ""
    subtitle_lang = ""
    player = _http_json(
        f"https://api.bilibili.com/x/player/v2?cid={cid}&bvid={bvid}&aid={aid}",
        referer,
    )
    subs = (player.get("data") or {}).get("subtitle", {}).get("subtitles") or []
    for sub in subs:
        sub_url = sub.get("subtitle_url") or ""
        if sub_url.startswith("//"):
            sub_url = "https:" + sub_url
        if not sub_url:
            continue
        try:
            sub_json = json.loads(_http_text(sub_url, referer))
            transcript = _subtitle_json_to_text(sub_json)
            subtitle_lang = sub.get("lan_doc") or sub.get("lan") or "subtitle"
            if transcript:
                break
        except Exception:
            continue

    chunks: list[str] = []
    if transcript:
        chunks.append(transcript)
    if desc:
        chunks.append(desc)
    if tags:
        chunks.append("标签：" + "、".join(tags[:8]))

    raw_text = "\n\n".join(chunks)
    key_points = extract_key_points(raw_text)
    if not key_points and title:
        key_points = [f"来源视频标题：{title}"]

    sources_used: list[str] = []
    if transcript:
        sources_used.append(f"字幕({subtitle_lang})")
    if desc:
        sources_used.append("视频简介")
    if tags and not transcript and not desc:
        sources_used.append("标签")

    status = "ok" if transcript else ("partial" if (desc or tags) else "title_only")
    note = ""
    if not transcript:
        note = "该视频未返回 CC/AI 字幕（仅简介/标题可用）；口播关键句须回看视频或对照指南核实。"

    return {
        "ok": True,
        "url": url,
        "type": "bilibili",
        "status": status,
        "title": title,
        "author": (data.get("owner") or {}).get("name", ""),
        "bvid": bvid,
        "transcript": transcript,
        "description": desc,
        "tags": tags,
        "raw_text": raw_text,
        "key_points": key_points,
        "sources_used": sources_used,
        "note": note,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def fetch_web(url: str) -> dict[str, Any]:
    target = url if url.startswith("http") else f"http://{url}"
    jina_url = f"https://r.jina.ai/{target}"
    try:
        md = _http_text(jina_url)
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url, "type": "web"}

    title = ""
    body = md
    m = re.search(r"^Title:\s*(.+)$", md, re.M)
    if m:
        title = m.group(1).strip()
    if "Markdown Content:" in md:
        body = md.split("Markdown Content:", 1)[1].strip()
    body = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)

    key_points = extract_key_points(body)
    if not key_points and title:
        key_points = extract_key_points(title)

    return {
        "ok": True,
        "url": url,
        "type": "web",
        "status": "ok" if key_points else "partial",
        "title": title,
        "raw_text": body[:12000],
        "key_points": key_points,
        "sources_used": ["网页正文(Jina)"],
        "note": "" if key_points else "未能从网页提炼要点，请人工核对原文",
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _find_ytdlp() -> list[str] | None:
    for cmd in (
        ["python", "-m", "yt_dlp"],
        ["yt-dlp"],
        ["yt-dlp.exe"],
    ):
        try:
            subprocess.run(
                cmd + ["--version"],
                capture_output=True,
                timeout=15,
                check=True,
            )
            return cmd
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def fetch_youtube(url: str) -> dict[str, Any]:
    ytdlp = _find_ytdlp()
    if not ytdlp:
        return {
            "ok": False,
            "error": "未安装 yt-dlp（pip install yt-dlp）",
            "url": url,
            "type": "youtube",
        }
    try:
        proc = subprocess.run(
            ytdlp
            + [
                "--dump-single-json",
                "--skip-download",
                "--no-warnings",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=90,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": (proc.stderr or proc.stdout or "yt-dlp 失败")[:300],
                "url": url,
                "type": "youtube",
            }
        meta = json.loads(proc.stdout)
        title = meta.get("title") or ""
        desc = (meta.get("description") or "")[:4000]
        transcript = desc
        sub_map = meta.get("subtitles") or meta.get("automatic_captions") or {}
        langs = ["zh-Hans", "zh-CN", "zh", "en"]
        for lang in langs:
            tracks = sub_map.get(lang)
            if not tracks:
                continue
            ext_url = tracks[0].get("url")
            if ext_url:
                try:
                    sub_text = _http_text(ext_url)
                    if "WEBVTT" in sub_text or "-->" in sub_text:
                        sub_text = re.sub(r"<[^>]+>", "", sub_text)
                        sub_text = re.sub(r"\d{2}:\d{2}:\d{2}\.\d{3} --> .*", "", sub_text)
                    transcript = sub_text
                    break
                except Exception:
                    continue
        raw = "\n\n".join(x for x in [transcript, desc] if x)
        key_points = extract_key_points(raw)
        return {
            "ok": True,
            "url": url,
            "type": "youtube",
            "status": "ok" if key_points else "partial",
            "title": title,
            "transcript": transcript[:8000],
            "description": desc,
            "raw_text": raw[:12000],
            "key_points": key_points,
            "sources_used": ["YouTube(yt-dlp)"],
            "note": "",
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "url": url, "type": "youtube"}


def fetch_source(url: str, *, use_cache: bool = True, cache_ttl_hours: int = 24) -> dict[str, Any]:
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "空 URL"}

    cache_path = CACHE_DIR / f"{url_cache_key(url)}.json"
    if use_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched = cached.get("fetched_at") or ""
            if fetched:
                age_h = (time.time() - time.mktime(time.strptime(fetched, "%Y-%m-%dT%H:%M:%S"))) / 3600
                if age_h < cache_ttl_hours:
                    cached["from_cache"] = True
                    return cached
        except Exception:
            pass

    kind = detect_source_type(url)
    if kind == "bilibili":
        result = fetch_bilibili(url)
    elif kind == "youtube":
        result = fetch_youtube(url)
    else:
        result = fetch_web(url)

    if result.get("ok"):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def fetch_sources(urls: list[str], **kwargs: Any) -> dict[str, Any]:
    items: list[dict] = []
    all_points: list[str] = []
    errors: list[str] = []

    for url in urls:
        if not url:
            continue
        item = fetch_source(url, **kwargs)
        items.append(item)
        if item.get("ok"):
            for p in item.get("key_points") or []:
                if p not in all_points:
                    all_points.append(p)
        else:
            errors.append(f"{url}: {item.get('error', '失败')}")

    merged_text = "\n\n".join(
        filter(
            None,
            [
                *(it.get("transcript") or "" for it in items if it.get("ok")),
                *(it.get("description") or "" for it in items if it.get("ok")),
                *(it.get("raw_text") or "" for it in items if it.get("ok") and it.get("type") == "web"),
            ],
        )
    )
    if len(all_points) < 3 and merged_text:
        for p in extract_key_points(merged_text, max_points=8):
            if p not in all_points:
                all_points.append(p)

    return {
        "items": items,
        "key_points": all_points[:12],
        "data_ref_lines": [f"【来源】{p}" if not p.startswith("【来源】") else p for p in all_points[:12]],
        "errors": errors,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def load_cached_source(url: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{url_cache_key(url)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
