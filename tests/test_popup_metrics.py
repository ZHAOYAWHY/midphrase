"""Popup geometry matching QuickLauncher's rounded list, not a solid block."""

import unittest

from midphrase.logic import hit_row, popup_metrics


class PopupMetricsTest(unittest.TestCase):
    def test_rows_start_below_the_header(self):
        metrics = popup_metrics(2)
        self.assertGreater(metrics.rows[0][1], metrics.header_bottom)
        self.assertEqual(len(metrics.rows), 2)

    def test_hit_is_the_card_not_the_gap(self):
        metrics = popup_metrics(2)
        left, top = 100, 80
        row_x, row_y, row_w, row_h = metrics.rows[1]
        self.assertEqual(hit_row(left + row_x + 8, top + row_y + 4, left, top, metrics.rows), 1)
        gap_y = metrics.rows[0][1] + metrics.rows[0][3] + 1
        self.assertIsNone(hit_row(left + row_x + 8, top + gap_y, left, top, metrics.rows))

    def test_outside_the_panel_cancels(self):
        metrics = popup_metrics(1)
        self.assertIsNone(hit_row(10, 10, 100, 80, metrics.rows))


if __name__ == "__main__":
    unittest.main()
