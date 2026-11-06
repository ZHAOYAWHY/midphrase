"""Editor save must keep edits even after the text field takes the selection."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tkinter as tk

from midphrase.app import App


class EditorSaveTest(unittest.TestCase):
    def test_save_keeps_edits_when_entry_owns_the_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("midphrase.app.data_dir", return_value=Path(folder)):
                app = App()
            root = tk.Tk()
            root.withdraw()
            app.root = root
            try:
                app._open_editor()
                editor = app.editor
                editor.update()
                listbox = editor.nametowidget(editor.winfo_children()[0])
                entry = None
                body = None
                save = None
                for child in editor.winfo_children():
                    for grand in child.winfo_children():
                        if grand.winfo_class() == "Entry":
                            entry = grand
                        elif grand.winfo_class() == "Text":
                            body = grand
                        elif grand.winfo_class() == "Button" and str(grand.cget("text")) == "保存":
                            save = grand
                self.assertIsNotNone(entry)
                self.assertIsNotNone(save)
                entry.delete(0, tk.END)
                entry.insert(0, "改过的简介")
                body.delete("1.0", tk.END)
                body.insert("1.0", "改过的全短语")
                entry.focus_set()
                entry.select_range(0, tk.END)
                editor.update()
                save.invoke()
                editor.update()
                self.assertEqual(app.phrases[0].label, "改过的简介")
                self.assertEqual(app.phrases[0].text, "改过的全短语")
                self.assertEqual(listbox.get(0), "改过的简介")
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
