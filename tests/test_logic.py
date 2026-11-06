"""Phrase wheel behavior: sector hit-testing and long-press gesture."""

import unittest

from midphrase.logic import Gesture, sector_index


class SectorIndexTest(unittest.TestCase):
    def test_center_is_cancel(self):
        self.assertIsNone(sector_index(0, 0, count=4, dead_zone=36))

    def test_top_slice_is_first_phrase(self):
        # 12 o'clock is the first slice, going clockwise.
        self.assertEqual(sector_index(0, -80, count=4, dead_zone=36), 0)

    def test_right_slice_is_second_of_four(self):
        self.assertEqual(sector_index(80, 0, count=4, dead_zone=36), 1)

    def test_empty_wheel_has_no_slice(self):
        self.assertIsNone(sector_index(80, 0, count=0, dead_zone=36))


class GestureTest(unittest.TestCase):
    def test_short_click_does_not_open_wheel(self):
        gesture = Gesture(long_press_ms=400, move_slop=12)
        gesture.down(10, 10, now_ms=0)
        action = gesture.up(10, 10, now_ms=120, phrase_count=4, dead_zone=36)
        self.assertEqual(action.kind, "short_click")

    def test_hold_still_opens_wheel(self):
        gesture = Gesture(long_press_ms=400, move_slop=12)
        gesture.down(100, 100, now_ms=0)
        self.assertEqual(gesture.tick(100, 100, now_ms=400), "open")

    def test_release_on_slice_commits_that_phrase(self):
        gesture = Gesture(long_press_ms=400, move_slop=12)
        gesture.down(200, 200, now_ms=0)
        gesture.tick(200, 200, now_ms=400)
        action = gesture.up(200, 120, now_ms=700, phrase_count=4, dead_zone=36)
        self.assertEqual(action.kind, "commit")
        self.assertEqual(action.index, 0)

    def test_release_in_center_cancels(self):
        gesture = Gesture(long_press_ms=400, move_slop=12)
        gesture.down(200, 200, now_ms=0)
        gesture.tick(200, 200, now_ms=400)
        action = gesture.up(204, 198, now_ms=600, phrase_count=4, dead_zone=36)
        self.assertEqual(action.kind, "cancel")

    def test_drag_before_threshold_stays_a_click(self):
        gesture = Gesture(long_press_ms=400, move_slop=12)
        gesture.down(0, 0, now_ms=0)
        self.assertEqual(gesture.move(40, 0, now_ms=100), "wait")
        action = gesture.up(40, 0, now_ms=500, phrase_count=4, dead_zone=36)
        self.assertEqual(action.kind, "short_click")


if __name__ == "__main__":
    unittest.main()
