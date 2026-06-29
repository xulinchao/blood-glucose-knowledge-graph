"""Tests for source_fetcher."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from source_fetcher import extract_key_points, fetch_bilibili  # noqa: E402


class TestSourceFetcher(unittest.TestCase):
    def test_extract_key_points_scores_numbers(self):
        text = "空腹血糖 3.9-6.1 mmol/L 是参考范围。今天天气不错。餐后2小时应低于7.8。"
        points = extract_key_points(text, max_points=3)
        self.assertTrue(any("血糖" in p for p in points))
        self.assertFalse(any("天气" in p for p in points))

    @patch("source_fetcher._http_json")
    def test_fetch_bilibili_with_subtitle(self, mock_json):
        mock_json.side_effect = [
            {
                "code": 0,
                "data": {
                    "title": "测试视频",
                    "desc": "简介含血糖与胰岛素抵抗讨论",
                    "cid": 1,
                    "aid": 2,
                    "tag": [{"tag_name": "控糖"}],
                    "owner": {"name": "UP"},
                },
            },
            {
                "code": 0,
                "data": {
                    "subtitle": {
                        "subtitles": [
                            {"subtitle_url": "https://example.com/sub.json", "lan_doc": "中文"}
                        ]
                    }
                },
            },
        ]

        def fake_text(url, referer=""):
            return '{"body":[{"content":"胰岛素抵抗早期可能血糖仍正常"}]}'

        with patch("source_fetcher._http_text", side_effect=fake_text):
            result = fetch_bilibili("https://www.bilibili.com/video/BV1TEST00000")
        self.assertTrue(result["ok"])
        self.assertIn("胰岛素", result["transcript"])
        self.assertTrue(result["key_points"])


if __name__ == "__main__":
    unittest.main()
