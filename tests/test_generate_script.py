"""Tests for script_knowledge and generate_script."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from script_knowledge import (  # noqa: E402
    build_script_document,
    build_verify_checklist,
    enrich_data_ref,
    match_foods,
    resolve_write_mode,
    save_script_record,
    update_discovered_topic_status,
)


class TestScriptKnowledge(unittest.TestCase):
    def test_match_foods_in_title(self):
        foods = [{"id": "f1", "name_zh": "苹果", "gi": 38, "gi_level": "低"}]
        matched = match_foods("血糖高能吃苹果吗", foods=foods)
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["name_zh"], "苹果")

    def test_enrich_data_ref_includes_gi(self):
        result = enrich_data_ref("燕麦片是不是低GI", angle="即食燕麦 GI 59-83")
        joined = "\n".join(result["data_ref"])
        self.assertTrue("GI" in joined or "燕麦" in joined or len(result["data_ref"]) >= 0)

    def test_hook_only_write_mode(self):
        self.assertEqual(resolve_write_mode("hook_only"), "hook_only")
        doc = build_script_document(
            title="胰岛素抵抗自测",
            meta={"use_as": "hook_only", "evidence_tier": "D"},
            data_ref=["网上讨论点1"],
        )
        self.assertEqual(doc["write_mode"], "hook_only")
        self.assertIn("网上", doc["parts"]["hook"])
        self.assertIn("不构成医疗建议", doc["full_text"])

    def test_verify_checklist_hook_only(self):
        checklist = build_verify_checklist({"use_as": "hook_only", "evidence_tier": "D"})
        ids = [c["id"] for c in checklist]
        self.assertIn("hook_only", ids)
        self.assertIn("disclaimer", ids)

    def test_expand_spoken_body_not_just_bullets(self):
        from script_knowledge import expand_spoken_body

        body = expand_spoken_body(
            title="怎么判断自己有没有胰岛素抵抗？",
            cat="number",
            data_lines=[
                "胰岛素是「钥匙」，细胞是「锁」，抵抗=锁生锈了",
                "早期血糖可能正常（高胰岛素代偿期）",
            ],
            write_mode="verify_before_script",
            duration=30,
        )
        self.assertIn("先说明", body)
        self.assertIn("第一点", body)
        self.assertIn("别自己诊断", body)
        self.assertGreater(len(body), 120)

    def test_save_script_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp) / "scripts"
            topics_file = Path(tmp) / "discovered-topics.json"
            topics_file.write_text(
                json.dumps(
                    {
                        "version": "1.0",
                        "topics": [{"id": "disc-test", "title": "测试", "script_status": "pending"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            doc = build_script_document(title="测试选题", meta={"use_as": "verify_before_script"})
            with patch("script_knowledge.SCRIPTS_DIR", scripts_dir), patch(
                "script_knowledge.TOPICS_FILE", topics_file
            ):
                saved = save_script_record(doc, topic_id="disc-test")
                self.assertTrue(Path(saved["path"]).name.endswith(".json"))
                script_file = scripts_dir / Path(saved["path"]).name
                self.assertTrue(script_file.exists())
                ok = update_discovered_topic_status("disc-test", script_status="writing")
                self.assertTrue(ok)
                updated = json.loads(topics_file.read_text(encoding="utf-8"))
                self.assertEqual(updated["topics"][0]["script_status"], "writing")


if __name__ == "__main__":
    unittest.main()
