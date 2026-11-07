"""Win32 handles must not be truncated to 32 bits."""

import ctypes
import unittest

from midphrase.overlay import bind_window_api


class Win32BindingTest(unittest.TestCase):
    def test_high_instance_handle_is_accepted_by_create_window(self):
        bind_window_api()
        user32 = ctypes.windll.user32
        # Without declared argtypes ctypes passes this as a 32-bit int and raises
        # OverflowError, which is what killed the mouse hook thread at startup.
        hwnd = user32.CreateWindowExW(0, "NoSuchMidPhraseClass", "x", 0, 0, 0, 0, 0, None, None, 0x7FFE0000, None)
        self.assertFalse(hwnd)

    def test_module_handle_keeps_full_width(self):
        bind_window_api()
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetModuleHandleW(None)
        self.assertNotEqual(handle, 0)
        self.assertIsNot(kernel32.GetModuleHandleW.restype, ctypes.c_int)


if __name__ == "__main__":
    unittest.main()
