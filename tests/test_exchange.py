"""Tab-separated phrase import and export."""

import unittest

from midphrase.logic import Phrase, export_phrases, import_phrases, load_import


class PhraseExchangeTest(unittest.TestCase):
    def test_export_writes_short_name_and_full_phrase(self):
        text = export_phrases([Phrase("问候", "你好")])
        self.assertEqual(
            text.splitlines(),
            [
                "# 以 # 开头的行是说明，导入时会忽略。",
                "# 请用 UTF-8 保存，也不要改成 CSV。",
                "# 一行一条短语。简称和全短语之间按一次 Tab，不要用空格代替，一行里不要有第二个 Tab。",
                "# 只有字符串、没有 Tab：这句话同时作为简称和全短语。",
                "# 以 Tab 开头：没有简称，用全短语补上。以 Tab 结尾：没有全短语，用简称补上。",
                "# 简称和全短语都相同：只保留第一条。",
                "# 简称相同、全短语不同：第一条保持原简介，后面的改为 简介-1、简介-2；编号已被占用就跳过。",
                "问候\t你好",
            ],
        )

    def test_import_single_field_fills_both(self):
        phrases, errors = import_phrases("只有一句\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("只有一句", "只有一句")])

    def test_import_missing_short_name_uses_full_phrase(self):
        phrases, errors = import_phrases("\t只有全文\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("只有全文", "只有全文")])

    def test_import_missing_full_phrase_uses_short_name(self):
        phrases, errors = import_phrases("只有简称\t\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("只有简称", "只有简称")])

    def test_import_skips_blanks_and_comments(self):
        phrases, errors = import_phrases("# 注释\n\n收到\t收到，马上看\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("收到", "收到，马上看")])

    def test_import_rejects_extra_tabs(self):
        phrases, errors = import_phrases("简称\t全短语\t多余\n")
        self.assertEqual(phrases, [])
        self.assertTrue(errors)
        self.assertIn("1", errors[0])

    def test_import_keeps_one_when_short_name_and_phrase_match(self):
        phrases, errors = import_phrases("问候\t你好\n问候\t你好\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("问候", "你好")])

    def test_import_suffixes_same_short_name_when_phrase_differs(self):
        phrases, errors = import_phrases("问候\t你好\n问候\t早上好\n问候\t晚上好\n")
        self.assertEqual(errors, [])
        self.assertEqual(
            phrases,
            [Phrase("问候", "你好"), Phrase("问候-1", "早上好"), Phrase("问候-2", "晚上好")],
        )

    def test_import_skips_suffix_already_used_by_another_phrase(self):
        phrases, errors = import_phrases("问候\t你好\n问候\t早上好\n问候-1\t已占用\n")
        self.assertEqual(errors, [])
        self.assertEqual(
            phrases,
            [Phrase("问候", "你好"), Phrase("问候-2", "早上好"), Phrase("问候-1", "已占用")],
        )

    def test_import_note_reports_dropped_and_renamed(self):
        phrases, errors, note = load_import("问候\t你好\n问候\t你好\n问候\t早上好\n")
        self.assertEqual(errors, [])
        self.assertEqual(phrases, [Phrase("问候", "你好"), Phrase("问候-1", "早上好")])
        self.assertIn("去掉 1 条", note)
        self.assertIn("-1", note)


if __name__ == "__main__":
    unittest.main()
