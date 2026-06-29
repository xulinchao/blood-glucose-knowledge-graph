#!/usr/bin/env python3
"""本地预览：静态站点 + /api/fetch-source 拉取字幕/网页。"""

from __future__ import annotations

import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from source_fetcher import fetch_source, fetch_sources  # noqa: E402


class DevHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/fetch-source":
            self._handle_fetch_source(parsed)
            return
        if parsed.path == "/api/fetch-sources":
            self._handle_fetch_sources(parsed)
            return
        super().do_GET()

    def _send_json(self, payload: dict, status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _handle_fetch_source(self, parsed):
        qs = parse_qs(parsed.query)
        url = (qs.get("url") or [""])[0]
        if not url:
            self._send_json({"ok": False, "error": "missing url"}, 400)
            return
        self._send_json(fetch_source(url))

    def _handle_fetch_sources(self, parsed):
        qs = parse_qs(parsed.query)
        urls = qs.get("url") or []
        if not urls:
            self._send_json({"ok": False, "error": "missing url"}, 400)
            return
        self._send_json(fetch_sources(urls))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = ThreadingHTTPServer(("127.0.0.1", port), DevHandler)
    print(f"Serving {ROOT} at http://127.0.0.1:{port}/")
    print("API: /api/fetch-source?url=...  /api/fetch-sources?url=...&url=...")
    server.serve_forever()


if __name__ == "__main__":
    main()
