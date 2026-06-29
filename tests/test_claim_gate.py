"""Tests for claim_gate Risk Gate."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from claim_gate import evaluate, extract_claims, adversarial_audit  # noqa: E402
from daily_topic_harvest import make_item  # noqa: E402


class TestClaimGate(unittest.TestCase):
    def test_causal_claim_d_tier_hook_only(self):
        result = evaluate(
            "喝苹果醋能降血糖",
            "博主",
            "https://xhs.com/a",
            "xhs",
        )
        self.assertFalse(result["gate"]["passed"])
        self.assertEqual(result["gate"]["use_as"], "hook_only")
        self.assertIn("causal_claim_low_evidence_D_tier", result["gate"]["veto_reasons"])

    def test_authority_passes_gate(self):
        result = evaluate(
            "成人糖尿病食养指南",
            "",
            "https://www.nhc.gov.cn/cms-search/test.pdf",
            "authority",
        )
        self.assertTrue(result["gate"]["passed"])
        self.assertIn(result["gate"]["use_as"], ("cite_directly", "verify_before_script"))

    def test_high_heat_ugc_not_writable(self):
        item = make_item(
            "bili",
            "逆转胰岛素抵抗五个自然方法",
            "https://bilibili.com/video/BVtest",
            author="UP主",
            keyword="控糖",
            metrics={"play": 500000},
        )
        self.assertGreater(item["heat_score"], 70)
        self.assertFalse(item["gate"]["passed"])
        self.assertFalse(item["topic_pick"])

    def test_writability_not_dominated_by_heat(self):
        low_heat = make_item(
            "exa",
            "中国糖尿病防治指南（2024版）",
            "https://drugs.dxy.cn/pc/clinicalGuidelines/test",
            metrics={"views": 100},
        )
        high_heat_hook = make_item(
            "bili",
            "体验动态血糖仪普通人有必要吗",
            "https://bilibili.com/video/BVhook",
            metrics={"play": 800000},
        )
        self.assertGreater(high_heat_hook["heat_score"], low_heat["heat_score"])
        self.assertGreater(low_heat["writability_score"], high_heat_hook["writability_score"])


if __name__ == "__main__":
    unittest.main()
