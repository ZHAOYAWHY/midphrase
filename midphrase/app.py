"""Middle-button phrase list for Windows.

Long-press the middle button to open a rectangular list. Move onto a phrase
and release to paste it into the window that already has focus. A short click
is swallowed and then replayed, so QuickLauncher can still use a normal middle click.
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox
from ctypes import wintypes
from pathlib import Path

from midphrase.logic import (
    DISPLAY_BOTH,
    DISPLAY_BRIEF,
    DISPLAY_FULL,
    Gesture,
    Phrase,
    PhraseStore,
    hit_row,
    popup_metrics,
    row_caption,
    export_filename,
    export_phrases,
    merge_phrases,
    parse_phrase_file,
)
from midphrase.overlay import GlassPopup, place_popup, render_popup, render_tray_icon

log = logging.getLogger("midphrase")

WH_MOUSE_LL = 14
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEMOVE = 0x0200
WM_RBUTTONUP = 0x0205
WM_LBUTTONUP = 0x0202
WM_QUIT = 0x0012
WM_APP = 0x8000
LLMHF_INJECTED = 0x00000001
HC_ACTION = 0
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
VK_CONTROL = 0x11
VK_V = 0x56
NIM_ADD = 0
NIM_DELETE = 2
NIF_MESSAGE = 0x01
NIF_ICON = 0x02
NIF_TIP = 0x04
ERROR_ALREADY_EXISTS = 183
LIST_WIDTH = 320
ROW_HEIGHT = 44
LONG_PRESS_MS = 400

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
shell32 = ctypes.windll.shell32

LRESULT = ctypes.c_ssize_t
ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", INPUTUNION)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


def _bind_win32() -> None:
    user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = LRESULT
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK
    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.SetClipboardData.argtypes = [wintypes.UINT, ctypes.c_void_p]
    user32.SetClipboardData.restype = ctypes.c_void_p
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = ctypes.c_void_p
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = ctypes.c_void_p
    kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
    kernel32.GlobalFree.restype = ctypes.c_void_p
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATAW)]
    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = LRESULT
    user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
    user32.AppendMenuW.restype = wintypes.BOOL
    user32.CreatePopupMenu.restype = wintypes.HMENU
    user32.DestroyMenu.argtypes = [wintypes.HMENU]
    user32.DestroyMenu.restype = wintypes.BOOL
    user32.TrackPopupMenu.argtypes = [
        wintypes.HMENU,
        wintypes.UINT,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        ctypes.c_void_p,
    ]
    user32.TrackPopupMenu.restype = wintypes.UINT
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.SetForegroundWindow.restype = wintypes.BOOL


def data_dir() -> Path:
    root = Path(os.environ.get("APPDATA") or Path.home())
    current = root / "midphrase"
    legacy = root / "PhraseWheel" / "phrases.json"
    target = current / "phrases.json"
    if legacy.is_file() and not target.is_file():
        current.mkdir(parents=True, exist_ok=True)
        target.write_bytes(legacy.read_bytes())
    return current


def now_ms() -> int:
    return int(time.monotonic() * 1000)


def cursor_pos() -> tuple[int, int]:
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _open_clipboard() -> bool:
    for _ in range(20):
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.02)
    return False


def read_clipboard() -> str | None:
    if not _open_clipboard():
        return None
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def write_clipboard(text: str) -> bool:
    if not _open_clipboard():
        return False
    allocated = None
    try:
        user32.EmptyClipboard()
        raw = (text or "").encode("utf-16le") + b"\x00\x00"
        allocated = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(raw))
        if not allocated:
            return False
        pointer = kernel32.GlobalLock(allocated)
        if not pointer:
            kernel32.GlobalFree(allocated)
            return False
        ctypes.memmove(pointer, raw, len(raw))
        kernel32.GlobalUnlock(allocated)
        if not user32.SetClipboardData(CF_UNICODETEXT, allocated):
            kernel32.GlobalFree(allocated)
            return False
        allocated = None
        return True
    finally:
        user32.CloseClipboard()
        if allocated:
            kernel32.GlobalFree(allocated)


def send_ctrl_v() -> bool:
    events = (INPUT * 4)()
    steps = (
        (VK_CONTROL, 0),
        (VK_V, 0),
        (VK_V, KEYEVENTF_KEYUP),
        (VK_CONTROL, KEYEVENTF_KEYUP),
    )
    for event, (vk, flags) in zip(events, steps, strict=True):
        event.type = INPUT_KEYBOARD
        event.ki.wVk = vk
        event.ki.dwFlags = flags
    sent = user32.SendInput(4, events, ctypes.sizeof(INPUT))
    return sent == 4


def paste_text(text: str) -> bool:
    time.sleep(0.05)
    previous = read_clipboard()
    if not write_clipboard(text):
        log.warning("clipboard write failed")
        return False
    time.sleep(0.04)
    ok = send_ctrl_v()
    time.sleep(0.30)
    if previous is not None:
        write_clipboard(previous)
    log.info("pasted %s chars ok=%s", len(text), ok)
    return ok


def replay_middle_click() -> None:
    user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
    user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)


class App:
    def __init__(self) -> None:
        self.store = PhraseStore(data_dir() / "phrases.json")
        self.phrases = self.store.load()
        self.display_mode = self.store.display_mode
        self.gesture = Gesture(long_press_ms=LONG_PRESS_MS, move_slop=12)
        self.lock = threading.Lock()
        self.button_down = False
        self.inject_click = False
        self.running = True
        self.events: queue.Queue[tuple] = queue.Queue()
        self.hook = wintypes.HHOOK()
        self.hook_proc = HOOKPROC(self._low_level_mouse)
        self.wnd_proc = WNDPROC(self._tray_proc)
        self.tray_hwnd = None
        self.hook_thread_id = 0
        self.root: tk.Tk | None = None
        self.wheel: tk.Toplevel | None = None
        self.glass = GlassPopup()
        self.popup_origin = (0, 0)
        self.editor: tk.Toplevel | None = None
        self.hover: int | None = None
        self.wheel_open = False

    def start(self) -> None:
        _enable_dpi()
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.geometry("1x1+-3000+-3000")
        self.root.title("短语列表")
        threading.Thread(target=self._hook_thread, name="PhraseWheelHook", daemon=True).start()
        threading.Thread(target=self._timer_thread, name="PhraseWheelTimer", daemon=True).start()
        self.root.after(30, self._pump_ui)
        log.info("ui ready, %s phrases", len(self.phrases))
        self.root.mainloop()
        self.shutdown()

    def shutdown(self) -> None:
        self.running = False
        if self.hook:
            user32.UnhookWindowsHookEx(self.hook)
            self.hook = wintypes.HHOOK()
        if self.tray_hwnd:
            icon = NOTIFYICONDATAW()
            icon.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            icon.hWnd = self.tray_hwnd
            icon.uID = 1
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(icon))
        if self.hook_thread_id:
            user32.PostThreadMessageW(self.hook_thread_id, WM_QUIT, 0, 0)

    def _hook_thread(self) -> None:
        self.hook_thread_id = kernel32.GetCurrentThreadId()
        self.tray_hwnd = self._create_tray_window()
        self.hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self.hook_proc, None, 0)
        log.info("hook installed=%s", bool(self.hook))
        if self.tray_hwnd:
            self._add_tray_icon()
        message = wintypes.MSG()
        while self.running and user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        log.info("hook thread exit")

    def _timer_thread(self) -> None:
        while self.running:
            time.sleep(0.02)
            inject = False
            with self.lock:
                if self.button_down and not self.gesture.open:
                    x, y = cursor_pos()
                    if self.gesture.tick(x, y, now_ms()) == "open":
                        origin = self.gesture.origin
                        self.events.put(("open", origin[0], origin[1]))
                if self.inject_click:
                    self.inject_click = False
                    inject = True
            if inject:
                replay_middle_click()

    def _low_level_mouse(self, code, wparam, lparam):
        try:
            return self._handle_mouse(code, wparam, lparam)
        except Exception:
            log.exception("mouse hook failed")
            return user32.CallNextHookEx(self.hook, code, wparam, lparam)

    def _handle_mouse(self, code, wparam, lparam):
        if code != HC_ACTION:
            return user32.CallNextHookEx(self.hook, code, wparam, lparam)
        info = ctypes.cast(lparam, ctypes.POINTER(MSLLHOOKSTRUCT)).contents
        if info.flags & LLMHF_INJECTED:
            return user32.CallNextHookEx(self.hook, code, wparam, lparam)
        message = int(wparam)
        if message not in (WM_MBUTTONDOWN, WM_MBUTTONUP):
            return user32.CallNextHookEx(self.hook, code, wparam, lparam)
        x, y = int(info.pt.x), int(info.pt.y)
        if message == WM_MBUTTONDOWN:
            with self.lock:
                self.gesture.down(x, y, now_ms())
                self.button_down = True
            return 1
        with self.lock:
            if not self.button_down:
                swallowed = False
            else:
                count = len(self.phrases)
                was_open = self.gesture.open
                origin = self.gesture.origin
                self.gesture.up(x, y, now_ms(), count, 1)
                self.button_down = False
                swallowed = True
                if not was_open:
                    self.inject_click = True
                else:
                    metrics = popup_metrics(count)
                    left, top = place_popup(origin[0], origin[1], metrics)
                    index = hit_row(x, y, left, top, metrics.rows)
                    if index is not None and index < count:
                        self.events.put(("paste", self.phrases[index].text))
                    self.events.put(("close",))
        if not swallowed:
            return user32.CallNextHookEx(self.hook, code, wparam, lparam)
        return 1

    def _pump_ui(self) -> None:
        if not self.running or self.root is None:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "open":
                self._show_list(event[1], event[2])
            elif kind == "close":
                self._hide_wheel()
            elif kind == "paste":
                self._hide_wheel()
                threading.Thread(target=paste_text, args=(event[1],), daemon=True).start()
            elif kind == "edit":
                self._open_editor()
            elif kind == "export":
                self._export_phrases()
            elif kind == "import":
                self._import_phrases()
            elif kind == "quit":
                self.root.quit()
                return
        if self.wheel_open:
            self._redraw_hover()
        self.root.after(16, self._pump_ui)

    def _list_rect(self, press_x: int, press_y: int, count: int) -> tuple[int, int, int, int]:
        width = LIST_WIDTH
        height = max(ROW_HEIGHT, max(count, 1) * ROW_HEIGHT)
        vx = int(user32.GetSystemMetrics(76))
        vy = int(user32.GetSystemMetrics(77))
        vw = int(user32.GetSystemMetrics(78))
        vh = int(user32.GetSystemMetrics(79))
        left = max(vx + 8, min(press_x - 24, vx + vw - width - 8))
        top = max(vy + 8, min(press_y + 12, vy + vh - height - 8))
        return left, top, width, height

    def _show_list(self, x: int, y: int) -> None:
        labels = [row_caption(phrase, self.display_mode) for phrase in self.phrases]
        if not labels:
            labels = [("还没有短语", "托盘右键可以编辑")]
        self.hover = None
        pixels, metrics = render_popup(labels, None)
        left, top = place_popup(x, y, metrics)
        self.popup_origin = (left, top)
        self.glass.show(left, top, pixels, metrics.width, metrics.height)
        self.wheel_open = True

    def _hide_wheel(self) -> None:
        self.wheel_open = False
        self.hover = None
        self.glass.hide()
        self.wheel_open = False
        self.hover = None
        if self.wheel is not None:
            self.wheel.withdraw()

    def _ensure_list(self) -> None:
        if self.wheel is not None or self.root is None:
            return
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg="#8ab4ff")
        win.withdraw()
        frame = tk.Frame(win, bg="#2a3140", highlightthickness=1, highlightbackground="#8ab4ff")
        frame.pack(fill="both", expand=True)
        self.wheel = win
        self.canvas = frame

    def _fill_rows(self) -> None:
        frame = self.canvas
        if not isinstance(frame, tk.Frame):
            return
        for child in frame.winfo_children():
            child.destroy()
        self.rows = []
        phrases = self.phrases or [Phrase("还没有短语", "托盘右键可以编辑")]
        for phrase in phrases:
            row = tk.Frame(frame, bg="#2a3140", height=ROW_HEIGHT)
            row.pack(fill="x")
            row.pack_propagate(False)
            title = phrase.wheel_label
            detail = phrase.text if phrase.text != phrase.wheel_label else "松开输入"
            tk.Label(row, text=title, bg="#2a3140", fg="#ffffff", anchor="w", font=("Microsoft YaHei UI", 12, "bold")).pack(fill="x", padx=14, pady=(6, 0))
            tk.Label(row, text=_short(detail, 28), bg="#2a3140", fg="#d5dbe8", anchor="w", font=("Microsoft YaHei UI", 9)).pack(fill="x", padx=14)
            self.rows.append(row)

    def _highlight(self, hover: int | None) -> None:
        for index, row in enumerate(self.rows):
            color = "#3b82f6" if index == hover else "#2a3140"
            row.configure(bg=color)
            for child in row.winfo_children():
                child.configure(bg=color)

    def _redraw_hover(self) -> None:
        if not self.wheel_open:
            return
        x, y = cursor_pos()
        labels = [(phrase.wheel_label, phrase.text) for phrase in self.phrases] or [("还没有短语", "")]
        metrics = popup_metrics(len(labels))
        left, top = self.popup_origin
        hover = hit_row(x, y, left, top, metrics.rows)
        if hover != self.hover:
            self.hover = hover
            pixels, metrics = render_popup(
                [row_caption(phrase, self.display_mode) for phrase in self.phrases] or [("还没有短语", "")],
                hover,
            )
            self.glass.show(left, top, pixels, metrics.width, metrics.height)

    def _make_click_through(self, window: tk.Toplevel) -> None:
        window.update_idletasks()
        hwnd = window.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
        user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOACTIVATE | SWP_SHOWWINDOW | 0x0001 | 0x0002 | 0x0020)

    def _open_editor(self) -> None:
        if self.root is None:
            return
        self._hide_wheel()
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.deiconify()
            self.editor.lift()
            return
        win = tk.Toplevel(self.root)
        win.title("编辑短语")
        win.geometry("560x420")
        win.minsize(560, 420)
        win.configure(bg="#1c1f26")
        win.attributes("-topmost", True)
        win.columnconfigure(0, minsize=196, weight=0)
        win.columnconfigure(1, weight=1)
        win.rowconfigure(0, weight=1)
        listbox = tk.Listbox(win, bg="#111317", fg="white", selectbackground="#3b82f6", font=("Microsoft YaHei UI", 11), activestyle="none", exportselection=False)
        listbox.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=(16, 8))
        form = tk.Frame(win, bg="#1c1f26")
        form.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=(12, 8))
        form.columnconfigure(0, weight=1)
        form.rowconfigure(3, weight=1)
        tk.Label(form, text="简介", bg="#1c1f26", fg="#d5dbe8", anchor="w", font=("Microsoft YaHei UI", 9)).grid(row=0, column=0, sticky="ew")
        label = tk.Entry(form, bg="#111317", fg="white", insertbackground="white", font=("Microsoft YaHei UI", 11))
        label.grid(row=1, column=0, sticky="ew", pady=(4, 10), ipady=6)
        tk.Label(form, text="全短语（松开后发送）", bg="#1c1f26", fg="#d5dbe8", anchor="w", font=("Microsoft YaHei UI", 9)).grid(row=2, column=0, sticky="ew")
        body = tk.Text(form, bg="#111317", fg="white", insertbackground="white", font=("Microsoft YaHei UI", 11), wrap="word")
        body.grid(row=3, column=0, sticky="nsew", pady=(4, 0))

        selected = {"index": 0}

        def refresh(select: int = 0) -> None:
            listbox.delete(0, tk.END)
            for phrase in self.phrases:
                listbox.insert(tk.END, phrase.wheel_label)
            if self.phrases:
                listbox.selection_set(min(select, len(self.phrases) - 1))
                show(min(select, len(self.phrases) - 1))

        def show(_event=None) -> None:
            picked = listbox.curselection()
            if not picked:
                return
            selected["index"] = picked[0]
            phrase = self.phrases[picked[0]]
            label.delete(0, tk.END)
            label.insert(0, phrase.label)
            body.delete("1.0", tk.END)
            body.insert("1.0", phrase.text)

        def collect() -> list[dict]:
            items = [{"label": phrase.label, "text": phrase.text} for phrase in self.phrases]
            picked = listbox.curselection()
            index = picked[0] if picked else selected["index"]
            if items and 0 <= index < len(items):
                items[index] = {"label": label.get().strip(), "text": body.get("1.0", tk.END).strip()}
            return items

        def persist(select: int = 0) -> None:
            with self.lock:
                self.phrases = self.store.save(collect())
            refresh(select)

        def add() -> None:
            items = collect()
            items.append({"label": "新短语", "text": "新短语"})
            with self.lock:
                self.phrases = self.store.save(items)
            refresh(len(self.phrases) - 1)

        def delete() -> None:
            picked = listbox.curselection()
            items = collect()
            if picked:
                del items[picked[0]]
            with self.lock:
                self.phrases = self.store.save(items)
            refresh(0)

        listbox.bind("<<ListboxSelect>>", show)
        buttons = tk.Frame(win, bg="#1c1f26")
        buttons.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 16))
        tk.Button(buttons, text="添加", command=add, width=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="删除", command=delete, width=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="导入", command=lambda: self.events.put(("import",)), width=8).pack(side="left", padx=(0, 8))
        tk.Button(buttons, text="导出", command=lambda: self.events.put(("export",)), width=8).pack(side="left")
        tk.Button(buttons, text="保存", command=lambda: persist(listbox.curselection()[0] if listbox.curselection() else selected["index"]), width=8).pack(side="right")
        refresh(0)
        self.editor = win

    def _create_tray_window(self):
        class_name = "PhraseWheelTray"
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = self.wnd_proc
        window_class.hInstance = kernel32.GetModuleHandleW(None)
        window_class.lpszClassName = class_name
        user32.RegisterClassW(ctypes.byref(window_class))
        hwnd = user32.CreateWindowExW(0, class_name, "中键短语", 0, 0, 0, 0, 0, 0, None, window_class.hInstance, None)
        return hwnd

    def _add_tray_icon(self) -> None:
        icon = NOTIFYICONDATAW()
        icon.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        icon.hWnd = self.tray_hwnd
        icon.uID = 1
        icon.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        icon.uCallbackMessage = WM_APP
        icon.hIcon = render_tray_icon(max(32, int(user32.GetSystemMetrics(49))))
        icon.szTip = "中键短语 — 长按中键"
        ok = shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(icon))
        if ok:
            icon.uFlags = 0x10  # NIF_INFO
            icon.szInfoTitle = "中键短语已启动"
            icon.szInfo = "图标在任务栏右下角。看不到时，点开旁边的箭头。长按鼠标中键使用。"
            icon.dwInfoFlags = 1
            shell32.Shell_NotifyIconW(1, ctypes.byref(icon))  # NIM_MODIFY
        log.info("tray icon=%s", bool(ok))

    def _tray_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_APP and int(lparam) in (WM_RBUTTONUP, WM_LBUTTONUP):
            self._show_tray_menu(hwnd)
            return 0
        if msg == 0x0011:  # WM_QUERYENDSESSION
            return 1
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _show_tray_menu(self, hwnd) -> None:
        menu = user32.CreatePopupMenu()
        user32.AppendMenuW(menu, 0, 1, "编辑短语")
        user32.AppendMenuW(menu, 0, 6, "导入短语")
        user32.AppendMenuW(menu, 0, 7, "导出短语")
        user32.AppendMenuW(menu, 0x00000800, 0, None)  # separator
        modes = (
            (3, DISPLAY_BRIEF, "显示简介"),
            (4, DISPLAY_FULL, "显示全短语"),
            (5, DISPLAY_BOTH, "显示简介+全短语"),
        )
        for command_id, mode, title in modes:
            flags = 0x00000008 if self.display_mode == mode else 0  # MF_CHECKED
            user32.AppendMenuW(menu, flags, command_id, title)
        user32.AppendMenuW(menu, 0x00000800, 0, None)
        user32.AppendMenuW(menu, 0, 2, "退出")
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        user32.SetForegroundWindow(hwnd)
        command = user32.TrackPopupMenu(menu, 0x0100 | 0x0002, pt.x, pt.y, 0, hwnd, None)
        user32.DestroyMenu(menu)
        if command == 1:
            self.events.put(("edit",))
        elif command == 6:
            self.events.put(("import",))
        elif command == 7:
            self.events.put(("export",))
        elif command in (3, 4, 5):
            mode = {3: DISPLAY_BRIEF, 4: DISPLAY_FULL, 5: DISPLAY_BOTH}[command]
            with self.lock:
                self.display_mode = self.store.set_display_mode(mode)
        elif command == 2:
            self.events.put(("quit",))

    def _dialog_parent(self) -> tk.Misc:
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.lift()
            return self.editor
        assert self.root is not None
        return self.root

    def _export_phrases(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self._dialog_parent(),
            title="导出短语",
            defaultextension=".txt",
            filetypes=[("短语文本", "*.txt"), ("所有文件", "*.*")],
            initialfile=export_filename(datetime.now()),
        )
        if not path:
            return
        Path(path).write_text("\ufeff" + export_phrases(self.phrases), encoding="utf-8")
        messagebox.showinfo("导出短语", f"已导出 {len(self.phrases)} 条。\n{path}", parent=self._dialog_parent())

    def _import_phrases(self) -> None:
        path = filedialog.askopenfilename(
            parent=self._dialog_parent(),
            title="导入短语",
            filetypes=[("短语文本", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            raw = Path(path).read_bytes()
        except OSError as exc:
            messagebox.showerror("导入失败", f"无法读取文件：{exc}", parent=self._dialog_parent())
            return
        if raw.startswith(b"\xef\xbb\xbf"):
            raw = raw[3:]
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            messagebox.showerror("导入失败", "文件不是 UTF-8，未替换现有短语。", parent=self._dialog_parent())
            return
        phrases, errors = parse_phrase_file(text)
        parent = self._dialog_parent()
        if errors:
            messagebox.showerror("导入失败", "未改动现有短语。\n" + "\n".join(errors[:8]), parent=parent)
            return
        if not phrases:
            messagebox.showwarning("导入失败", "文件里没有可用短语，未改动现有内容。", parent=parent)
            return
        mode = self._ask_import_mode(parent, len(phrases), len(self.phrases))
        if mode is None:
            return
        if mode == "merge":
            merged, note = merge_phrases(self.phrases, phrases)
            action = "已增量导入"
        else:
            merged, note = merge_phrases([], phrases)
            action = "已全部替换"
        detail = f"\n{note}。" if note else ""
        with self.lock:
            self.phrases = self.store.save([{"label": item.label, "text": item.text} for item in merged])
        if self.editor is not None and self.editor.winfo_exists():
            self.editor.destroy()
            self.editor = None
            self._open_editor()
        messagebox.showinfo("导入短语", f"{action}，当前共 {len(self.phrases)} 条。{detail}", parent=self._dialog_parent())

    def _ask_import_mode(self, parent: tk.Misc, incoming: int, current: int) -> str | None:
        choice: dict[str, str | None] = {"mode": None}
        dialog = tk.Toplevel(parent)
        dialog.title("导入短语")
        dialog.configure(bg="#1c1f26")
        dialog.attributes("-topmost", True)
        dialog.resizable(False, False)
        dialog.grab_set()
        text = (
            f"文件里有 {incoming} 条，当前有 {current} 条。\n\n"
            "增量导入：保留现有短语，再加入文件中的短语。现有短语算第一条。\n"
            "全部替换：用文件内容覆盖当前列表。\n\n"
            "两种方式都会处理冲突，包括文件里已经存在的冲突：\n"
            "简称和全短语都相同的只保留一条；\n"
            "简称相同但全短语不同的，第一条保持原简介，后面的加上 -1、-2，编号被占用就跳过。"
        )
        tk.Label(
            dialog,
            text=text,
            bg="#1c1f26",
            fg="white",
            justify="left",
            anchor="w",
            font=("Microsoft YaHei UI", 10),
            wraplength=420,
        ).pack(padx=18, pady=(16, 10), anchor="w")

        def choose(mode: str) -> None:
            choice["mode"] = mode
            dialog.destroy()

        bar = tk.Frame(dialog, bg="#1c1f26")
        bar.pack(pady=(0, 16))
        tk.Button(bar, text="增量导入", width=12, command=lambda: choose("merge")).pack(side="left", padx=6)
        tk.Button(bar, text="全部替换", width=12, command=lambda: choose("replace")).pack(side="left", padx=6)
        tk.Button(bar, text="取消", width=8, command=dialog.destroy).pack(side="left", padx=6)
        dialog.update_idletasks()
        width = max(dialog.winfo_reqwidth(), 460)
        height = dialog.winfo_reqheight()
        screen_w = dialog.winfo_screenwidth()
        screen_h = dialog.winfo_screenheight()
        dialog.geometry(f"{width}x{height}+{(screen_w - width) // 2}+{(screen_h - height) // 2}")
        dialog.wait_window()
        return choice["mode"]


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _enable_dpi() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            log.debug("dpi awareness unavailable", exc_info=True)


def _tell_already_running() -> None:
    user32.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    user32.MessageBoxW.restype = ctypes.c_int
    user32.MessageBoxW(
        None,
        "中键短语已在运行。\n请看任务栏右下角的托盘图标；如果没有，点开旁边的箭头。",
        "中键短语",
        0x00000040 | 0x00040000 | 0x00010000,
    )


def _single_instance() -> bool:
    kernel32.CreateMutexW(None, False, "Local\\PhraseWheel.single")
    return kernel32.GetLastError() != ERROR_ALREADY_EXISTS


def main() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(data_dir() / "midphrase.log"),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    if not _single_instance():
        log.info("already running")
        _tell_already_running()
        return
    _bind_win32()
    if "--edit" in sys.argv:
        # Open the editor after the wheel process starts.
        pass
    App().start()


if __name__ == "__main__":
    main()
