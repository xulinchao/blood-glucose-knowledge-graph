"""Tests for curate_daily_brief."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from curate_daily_brief import (  # noqa: E402
    curate_from_harvest_payload,
    find_cross_platform_themes,
    _timeline_sort_key,
    _ensure_gate_fields,
    build_rule_deep_analysis,
)


def _item(
    title,
    platform,
    score=70,
    heat=70,
    use_as="verify_before_script",
    tier="C",
    pick=True,
    gate_passed=True,
):
    gate = {
        "passed": gate_passed,
        "writability_score": score,
        "use_as": use_as,
        "allowed_frame": "verify_before_script",
        "forbidden_expressions": [],
        "required_hedges": ["目前证据有限"],
        "veto_reasons": [],
        "creator_note": "须核实",
    }
    return {
        "title": title,
        "url": f"https://example.com/{platform}",
        "platform": platform,
        "platform_label": platform,
        "topic_score": score,
        "writability_score": score,
        "heat_score": heat,
        "topic_pick": pick and gate_passed,
        "category": "数字科普",
        "authenticity": {
            "score": 65,
            "evidence_tier": tier,
            "use_as": use_as,
            "adversarial_flags": [],
            "creator_note": "须核实",
        },
        "importance": {"score": heat, "label": "中"},
        "gate": gate,
        "editorial": {
            "why_selected": "测试",
            "misleading_risk": "",
            "safe_rewrite": "",
        },
    }


class TestCurateDailyBrief(unittest.TestCase):
    def test_curate_schema_v2(self):
        items = [_item(f"标题{i}", "bili", score=80 - i, heat=50 + i) for i in range(20)]
        items.append(
            {
                **_item("干细胞根治糖尿病", "xhs", score=30, heat=90, use_as="hook_only", tier="E", pick=False, gate_passed=False),
                "authenticity": {
                    "score": 30,
                    "evidence_tier": "E",
                    "use_as": "hook_only",
                    "adversarial_flags": ["sensational"],
                    "creator_note": "仅钩子",
                },
            }
        )
        brief = curate_from_harvest_payload(
            {"report_date": "2026-06-29", "summary": {"total_raw": 21}, "items": items}
        )
        self.assertEqual(brief.get("schema_version"), "2.0")
        self.assertLessEqual(len(brief["timeline"]), 12)
        self.assertNotIn("E", [x["evidence_tier"] for x in brief["timeline"]])
        self.assertIn("agent_hints", brief)
        angles = brief["agent_hints"]["top_script_angles"]
        if angles:
            self.assertIn("why_selected", angles[0])

    def test_gate_passed_sorts_before_heat(self):
        passed = _item("指南解读", "exa", score=65, heat=40, tier="B")
        hot_hook = _item("爆款控糖谣言", "bili", score=35, heat=95, use_as="hook_only", pick=False, gate_passed=False)
        key_passed = _timeline_sort_key(passed)
        key_hook = _timeline_sort_key(hot_hook)
        self.assertGreater(key_passed, key_hook)

    def test_cross_platform(self):
        items = [
            _item("胰岛素抵抗怎么办", "bili", score=75),
            _item("胰岛素抵抗怎么办", "xhs", score=72),
        ]
        themes = find_cross_platform_themes(items)
        self.assertEqual(len(themes), 1)
        self.assertEqual(len(themes[0]["platforms"]), 2)

    def test_ensure_gate_backfills_editorial(self):
        item = _item("空腹血糖6.1算不算糖尿病", "bili")
        item["editorial"] = {}
        fixed = _ensure_gate_fields(item)
        self.assertTrue((fixed.get("editorial") or {}).get("why_selected"))

    def test_rule_deep_analysis_no_verified_label(self):
        item = _item("西瓜GI很高吗", "xhs", tier="C")
        da = build_rule_deep_analysis(item)
        self.assertEqual(da.get("_source"), "rule_engine")
        self.assertFalse(da.get("_ai"))
        self.assertIn("verification_steps", da)
        self.assertNotIn("已核实", da.get("credibility", ""))


if __name__ == "__main__":
    unittest.main()
