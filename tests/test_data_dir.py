"""User data lives under %APPDATA%\\midphrase."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from midphrase.app import data_dir


class DataDirTest(unittest.TestCase):
    def test_uses_midphrase_and_keeps_old_phrases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "PhraseWheel"
            old.mkdir()
            (old / "phrases.json").write_text('{"phrases":[]}', encoding="utf-8")
            with patch.dict(os.environ, {"APPDATA": str(root)}):
                path = data_dir()
            self.assertEqual(path.name, "midphrase")
            self.assertEqual((path / "phrases.json").read_text(encoding="utf-8"), '{"phrases":[]}')


if __name__ == "__main__":
    unittest.main()
