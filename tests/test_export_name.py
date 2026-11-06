"""Default export filename includes a timestamp."""

import unittest
from datetime import datetime

from phrase_wheel.logic import export_filename


class ExportFilenameTest(unittest.TestCase):
    def test_uses_date_and_hour_minute(self):
        self.assertEqual(export_filename(datetime(2020, 3, 2, 23, 43)), "中键短语-20200302-2343.txt")


if __name__ == "__main__":
    unittest.main()
