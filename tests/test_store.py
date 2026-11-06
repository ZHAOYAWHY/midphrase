"""Phrase library load, edit, and save."""

import json
import tempfile
import unittest
from pathlib import Path

from phrase_wheel.logic import PhraseStore


class PhraseStoreTest(unittest.TestCase):
    def test_missing_file_starts_with_editable_defaults(self):
        store = PhraseStore(Path(tempfile.mkdtemp()) / "phrases.json")
        phrases = store.load()
        self.assertGreaterEqual(len(phrases), 1)
        self.assertTrue(phrases[0].text)

    def test_round_trip_keeps_label_and_text(self):
        path = Path(tempfile.mkdtemp()) / "phrases.json"
        store = PhraseStore(path)
        store.save([
            {"label": "收到", "text": "收到，马上看"},
            {"label": "", "text": "只有正文"},
        ])
        loaded = store.load()
        self.assertEqual(loaded[0].label, "收到")
        self.assertEqual(loaded[0].text, "收到，马上看")
        self.assertEqual(loaded[1].label, "只有正文")
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["phrases"][1]["text"], "只有正文")

    def test_blank_text_is_dropped(self):
        path = Path(tempfile.mkdtemp()) / "phrases.json"
        store = PhraseStore(path)
        store.save([{"label": "空", "text": "   "}, {"label": "在", "text": "在的"}])
        self.assertEqual([item.text for item in store.load()], ["在的"])


if __name__ == "__main__":
    unittest.main()
