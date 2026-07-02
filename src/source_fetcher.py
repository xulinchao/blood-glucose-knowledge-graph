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


def _find_cli(name: str, version_args: list[str] | None = None) -> list[str] | None:
    version_args = version_args or ["--version"]
    for cmd in ([name], [f"{name}.exe"]):
        try:
            subprocess.run(
                cmd + version_args,
                capture_output=True,
                timeout=15,
                check=True,
            )
            return cmd
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def _is_page_noise_point(point: str) -> bool:
    p = (point or "").strip()
    if not p or p.startswith("来源视频标题："):
        return True
    if re.search(r"BV[0-9A-Za-z]{10}|spm_id_from|router-related|recommend_more", p):
        return True
    if re.search(r"^(首页|登录|收藏|历史|投稿|关注)$", p):
        return True
    return False


def assess_content_status(result: dict[str, Any]) -> str:
    """ready=可写稿 / partial=有片段须核对 / title_only=仅标题 / error=拉取失败"""
    if not result.get("ok"):
        return "error"
    transcript = (result.get("transcript") or "").strip()
    desc = (result.get("description") or "").strip()
    if desc in ("-", "—"):
        desc = ""
    raw = (result.get("raw_text") or "").strip()
    kps = result.get("key_points") or []
    real_kps = [
        p for p in kps
        if p and not _is_page_noise_point(str(p)) and len(str(p).strip()) >= 10
    ]
    src = result.get("sources_used") or []
    has_transcript = len(transcript) >= 120
    has_real_desc = len(desc) >= 40
    jina_only = "页面正文(Jina)" in src and not has_transcript and not has_real_desc

    if has_transcript or (has_real_desc and len(real_kps) >= 2):
        return "ready"
    if has_transcript or len(real_kps) >= 3 or len(transcript) >= 60:
        return "ready"
    if transcript or len(real_kps) >= 1 or has_real_desc or (not jina_only and len(raw) >= 200):
        return "partial"
    return "title_only"


def fetch_bilibili_bili_cli(bvid: str, url: str) -> dict[str, Any] | None:
    """Agent Reach 推荐：bili-cli 读字幕/评论/AI 摘要（优先于裸 API）。"""
    cmd = _find_cli("bili")
    if not cmd:
        return None
    try:
        proc = subprocess.run(
            cmd + ["video", bvid, "--json", "--subtitle", "--comments", "--ai"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=50,
        )
        if proc.returncode != 0 or not (proc.stdout or "").strip():
            return None
        payload = json.loads(proc.stdout)
        data = payload.get("data") or payload
        video = data.get("video") or {}
        subtitle = data.get("subtitle") or {}
        transcript = (subtitle.get("text") or "").strip()
        if not transcript and subtitle.get("items"):
            transcript = _subtitle_json_to_text({"body": subtitle.get("items")})
        desc = (video.get("description") or "").strip()
        if desc in ("-", "—", ""):
            desc = ""
        ai_summary = (data.get("ai_summary") or "").strip()
        comments = data.get("comments") or []
        comment_lines = [
            (c.get("content") or c.get("message") or "").strip()
            for c in comments[:8]
            if (c.get("content") or c.get("message") or "").strip()
        ]
        chunks: list[str] = []
        sources_used: list[str] = []
        if transcript:
            chunks.append(transcript)
            sources_used.append("bili-cli字幕")
        if ai_summary:
            chunks.append(ai_summary)
            sources_used.append("bili-cli AI摘要")
        if desc:
            chunks.append(desc)
            sources_used.append("视频简介")
        if comment_lines:
            chunks.append("热门评论摘录：\n" + "\n".join(comment_lines[:5]))
            sources_used.append("bili-cli评论")
        raw_text = "\n\n".join(chunks)
        key_points = extract_key_points(raw_text)
        title = video.get("title") or ""
        if not key_points and title:
            key_points = [f"来源视频标题：{title}"]
        status = assess_content_status(
            {"ok": True, "transcript": transcript, "description": desc, "raw_text": raw_text, "key_points": key_points}
        )
        note = ""
        if status == "title_only":
            note = (
                "该视频无 CC 字幕/简介/AI 摘要。可本地运行 "
                "`bili audio {bvid}` + `agent-reach transcribe` 转写，或人工看视频写稿。"
            ).format(bvid=bvid)
        elif status == "partial" and not transcript:
            note = "无逐字字幕，以下为简介/AI摘要/评论摘录；写稿前须点开原视频核对。"
        return {
            "ok": True,
            "url": url,
            "type": "bilibili",
            "status": status,
            "content_status": status,
            "title": title,
            "author": (video.get("owner") or {}).get("name", ""),
            "bvid": bvid,
            "transcript": transcript,
            "description": desc,
            "tags": [],
            "raw_text": raw_text,
            "key_points": key_points[:12],
            "sources_used": sources_used or ["bili-cli"],
            "note": note,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "fetch_backend": "bili-cli",
        }
    except Exception:
        return None


def fetch_bilibili(url: str) -> dict[str, Any]:
    bvid = parse_bvid(url)
    if not bvid:
        return {"ok": False, "error": "无法解析 BVID", "url": url, "type": "bilibili"}

    cli_result = fetch_bilibili_bili_cli(bvid, url)
    if cli_result and cli_result.get("content_status") in ("ready", "partial"):
        return cli_result

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
        note = "该视频未返回 CC/AI 字幕；已尝试从页面抓取简介/相关推荐文案，关键句仍须回看视频核实。"

    # B 站无字幕时不走 Jina（页面多为相关推荐噪音）；须 bili audio + transcribe
    if not transcript and len(desc) < 20:
        pass

    if cli_result and cli_result.get("raw_text") and len((cli_result.get("transcript") or "")) > len(transcript):
        transcript = cli_result.get("transcript") or transcript
        for p in cli_result.get("key_points") or []:
            if p not in key_points:
                key_points.append(p)
        for s in cli_result.get("sources_used") or []:
            if s not in sources_used:
                sources_used.append(s)

    content_status = assess_content_status(
        {
            "ok": True,
            "transcript": transcript,
            "description": desc,
            "raw_text": raw_text,
            "key_points": key_points,
        }
    )
    has_ai = any("AI" in s for s in sources_used)
    if not transcript and not has_ai and len(desc) < 40:
        key_points = [p for p in key_points if str(p).startswith("来源视频标题")]
        content_status = "title_only"
        note = (
            f"该视频无 CC 字幕/简介（{bvid}）。请用 "
            f"`bili audio {bvid}` + `agent-reach transcribe` 转写，或 opencli bilibili subtitle / 人工看视频。"
        )

    return {
        "ok": True,
        "url": url,
        "type": "bilibili",
        "status": "ok" if transcript else ("partial" if (desc or tags or key_points) else "title_only"),
        "content_status": content_status,
        "title": title,
        "author": (data.get("owner") or {}).get("name", ""),
        "bvid": bvid,
        "transcript": transcript,
        "description": desc,
        "tags": tags,
        "raw_text": raw_text,
        "key_points": key_points[:12],
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
        "content_status": assess_content_status(
            {"ok": True, "raw_text": body, "key_points": key_points}
        ),
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
            "content_status": assess_content_status(
                {"ok": True, "transcript": transcript[:8000], "key_points": key_points}
            ),
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


def to_source_preview(result: dict[str, Any]) -> dict[str, Any]:
    """精选日报 / 创作台用的轻量预览（不含全文缓存）。"""
    if not result.get("ok"):
        return {
            "status": "error",
            "url": result.get("url", ""),
            "error": result.get("error", "拉取失败"),
        }
    excerpt_parts: list[str] = []
    if result.get("transcript"):
        excerpt_parts.append(str(result["transcript"])[:1200])
    elif result.get("description"):
        excerpt_parts.append(str(result["description"])[:800])
    elif result.get("raw_text"):
        excerpt_parts.append(str(result["raw_text"])[:1200])
    return {
        "status": result.get("content_status") or result.get("status", "ok"),
        "content_status": result.get("content_status") or assess_content_status(result),
        "type": result.get("type", ""),
        "url": result.get("url", ""),
        "title": result.get("title", ""),
        "author": result.get("author", ""),
        "excerpt": "\n\n".join(excerpt_parts)[:1500],
        "key_points": (result.get("key_points") or [])[:8],
        "sources_used": result.get("sources_used") or [],
        "note": result.get("note", ""),
        "fetched_at": result.get("fetched_at", ""),
        "from_cache": bool(result.get("from_cache")),
    }


def enrich_items_with_source_preview(items: list[dict], *, fetch: bool = True) -> None:
    """为精选条目附加 source_preview（原地修改）。"""
    for item in items:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        if item.get("source_preview") and item["source_preview"].get("excerpt"):
            continue
        try:
            if fetch:
                result = fetch_source(url)
            else:
                result = load_cached_source(url) or {"ok": False, "url": url, "error": "无缓存"}
            item["source_preview"] = to_source_preview(result)
        except Exception as e:
            item["source_preview"] = {"status": "error", "url": url, "error": str(e)}


def load_cached_source(url: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{url_cache_key(url)}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
