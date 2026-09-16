#!/usr/bin/env python3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "patches"))

from gemini_items import place_items_on_array_branches  # noqa: E402


class GeminiItemsTests(unittest.TestCase):
    def test_moves_items_onto_array_anyof_branch(self):
        schema = {
            "anyOf": [{"type": "string"}, {"type": "array"}],
            "items": {"type": "string"},
            "description": "to",
        }
        place_items_on_array_branches(schema)
        self.assertNotIn("items", schema)
        self.assertEqual(schema["anyOf"][1]["items"], {"type": "string"})
        self.assertEqual(schema["anyOf"][0], {"type": "string"})

    def test_array_without_items_gets_string_items(self):
        schema = {"type": "array"}
        place_items_on_array_branches(schema)
        self.assertEqual(schema["items"], {"type": "string"})

    def test_string_with_items_drops_items(self):
        schema = {"type": "string", "items": {"type": "string"}}
        place_items_on_array_branches(schema)
        self.assertNotIn("items", schema)


if __name__ == "__main__":
    unittest.main()
