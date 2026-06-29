"""Tests for daily_topic_harvest scoring, filters, and audit."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from daily_topic_harvest import (  # noqa: E402
    adversarial_audit,
    make_item,
    parse_count,
    passes_twitter_filter,
    score_importance,
)


class TestDailyHarvest(unittest.TestCase):
    def test_parse_count_wan(self):
        self.assertEqual(parse_count("1.4万"), 14000)
        self.assertEqual(parse_count("2878"), 2878)

    def test_twitter_noise_filtered(self):
        self.assertFalse(
            passes_twitter_filter(
                "BTC long setup",
                "TraderMige",
                "bitget 返55%",
            )
        )
        self.assertTrue(
            passes_twitter_filter(
                "Skin tags may link to insulin resistance",
                "CoachDanGo",
                "health coach",
            )
        )

    def test_authority_tier_a(self):
        auth = adversarial_audit(
            "成人糖尿病食养指南",
            "",
            "https://www.nhc.gov.cn/cms-search/downFiles/test.pdf",
            "authority",
        )
        self.assertEqual(auth["evidence_tier"], "A")
        self.assertEqual(auth["use_as"], "cite_directly")

    def test_sensational_hooks_only(self):
        bad = adversarial_audit(
            "干细胞根治糖尿病别被骗了",
            "某博主",
            "https://xhs.com/b",
            "xhs",
        )
        self.assertEqual(bad["use_as"], "hook_only")
        self.assertIn("sensational", bad["adversarial_flags"])

    def test_importance_engagement(self):
        low = score_importance("控糖", "控糖", {"likes": 50})
        high = score_importance("控糖饮食", "控糖", {"play": 200000})
        self.assertGreater(high["score"], low["score"])

    def test_make_item_stricter_pick(self):
        item = make_item(
            "bili",
            "2026控糖指南解读",
            "https://bilibili.com/video/BV1",
            author="内分泌科医生",
            keyword="控糖",
            metrics={"play": 300000},
        )
        self.assertIn("evidence_tier", item["authenticity"])
        self.assertIn("use_as", item["authenticity"])


if __name__ == "__main__":
    unittest.main()
