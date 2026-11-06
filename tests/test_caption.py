"""Candidate row text follows the display mode and never uses the send hint."""

import unittest

from midphrase.logic import Phrase, row_caption


class RowCaptionTest(unittest.TestCase):
    def test_brief_shows_only_the_intro(self):
        phrase = Phrase("问候", "你好，请问有什么可以帮您？")
        self.assertEqual(row_caption(phrase, "brief"), ("问候", ""))

    def test_full_shows_only_the_phrase_that_will_be_sent(self):
        phrase = Phrase("问候", "你好，请问有什么可以帮您？")
        self.assertEqual(row_caption(phrase, "full"), ("你好，请问有什么可以帮您？", ""))

    def test_both_shows_intro_and_full_phrase(self):
        phrase = Phrase("问候", "你好，请问有什么可以帮您？")
        self.assertEqual(row_caption(phrase, "both"), ("问候", "你好，请问有什么可以帮您？"))

    def test_row_never_uses_the_release_hint(self):
        phrase = Phrase("收到", "收到")
        for mode in ("brief", "full", "both"):
            title, detail = row_caption(phrase, mode)
            self.assertNotIn("松开", title)
            self.assertNotIn("松开", detail)


if __name__ == "__main__":
    unittest.main()
