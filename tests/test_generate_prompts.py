"""Tests for generate_prompts.py"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from generate_prompts import load_foods, load_topics  # noqa: E402


class TestDataLoaders(unittest.TestCase):
    def test_load_foods_from_gi_database(self):
        foods = load_foods()
        self.assertGreaterEqual(len(foods), 100)
        first = foods[0]
        self.assertIn("name_zh", first)
        self.assertIn("gi", first)
        self.assertIn("nutrition_per_100g", first)

    def test_load_topics(self):
        topics = load_topics()
        self.assertGreaterEqual(len(topics), 10)
        self.assertIn("title_zh", topics[0])


if __name__ == "__main__":
    unittest.main()
