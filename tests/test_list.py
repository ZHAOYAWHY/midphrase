"""Rectangular phrase list hit testing."""

import unittest

from midphrase.logic import list_index


class ListIndexTest(unittest.TestCase):
    def test_first_row(self):
        self.assertEqual(list_index(120, 210, left=100, top=200, width=280, row_height=40, count=3), 0)

    def test_second_row(self):
        self.assertEqual(list_index(200, 245, left=100, top=200, width=280, row_height=40, count=3), 1)

    def test_outside_is_cancel(self):
        self.assertIsNone(list_index(90, 210, left=100, top=200, width=280, row_height=40, count=3))
        self.assertIsNone(list_index(120, 190, left=100, top=200, width=280, row_height=40, count=3))

    def test_empty_list_has_no_row(self):
        self.assertIsNone(list_index(120, 210, left=100, top=200, width=280, row_height=40, count=0))


if __name__ == "__main__":
    unittest.main()
