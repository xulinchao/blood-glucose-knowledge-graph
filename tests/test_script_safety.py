"""Tests for script_safety lint."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from script_safety import lint_script_text  # noqa: E402


class TestScriptSafety(unittest.TestCase):
    def test_forbidden_absolute_claim(self):
        report = lint_script_text("这个方法一定可以降血糖。", write_mode="verify_before_script")
        self.assertFalse(report["passed"])
        self.assertTrue(any(v["type"] == "forbidden_pattern" for v in report["violations"]))

    def test_safe_text_with_hedge_and_disclaimer(self):
        text = (
            "网上很多人在讨论苹果醋。目前证据有限，个体差异较大。"
            "个体情况请咨询医生，不构成医疗建议。"
        )
        report = lint_script_text(
            text,
            meta={"evidence_tier": "D", "allowed_frame": "discussion_only"},
            write_mode="hook_only",
        )
        self.assertTrue(report["passed"])


if __name__ == "__main__":
    unittest.main()
