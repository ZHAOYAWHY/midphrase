"""QuickLauncher-style glass popup, painted with GDI+ and shown as a layered window."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from phrase_wheel.logic import PAD, PANEL_WIDTH, PopupMetrics, SHADOW, popup_metrics

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
gdiplus = ctypes.windll.gdiplus

WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000
SW_SHOWNOACTIVATE = 4
SW_HIDE = 0
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040

PixelFormat32bppARGB = 0x26200A
SmoothingModeAntiAlias = 4
TextRenderingHintAntiAlias = 4


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("BlendFlags", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
    ]


class RECTF(ctypes.Structure):
    _fields_ = [("x", ctypes.c_float), ("y", ctypes.c_float), ("w", ctypes.c_float), ("h", ctypes.c_float)]


class BitmapData(ctypes.Structure):
    _fields_ = [
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("Stride", ctypes.c_int),
        ("PixelFormat", ctypes.c_int),
        ("Scan0", ctypes.c_void_p),
        ("Reserved", ctypes.c_void_p),
    ]


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", ctypes.c_int),
        ("SuppressExternalCodecs", ctypes.c_int),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HCURSOR),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


_TOKEN = ctypes.c_ulong()
_STARTED = False
_WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


def _bind() -> None:
    c_void = ctypes.c_void_p
    f = ctypes.c_float
    gdiplus.GdipCreateBitmapFromScan0.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, c_void, ctypes.POINTER(c_void)]
    gdiplus.GdipGetImageGraphicsContext.argtypes = [c_void, ctypes.POINTER(c_void)]
    gdiplus.GdipSetSmoothingMode.argtypes = [c_void, ctypes.c_int]
    gdiplus.GdipSetTextRenderingHint.argtypes = [c_void, ctypes.c_int]
    gdiplus.GdipSetCompositingMode.argtypes = [c_void, ctypes.c_int]
    gdiplus.GdipGraphicsClear.argtypes = [c_void, ctypes.c_uint]
    gdiplus.GdipCreatePath.argtypes = [ctypes.c_int, ctypes.POINTER(c_void)]
    gdiplus.GdipAddPathArc.argtypes = [c_void, f, f, f, f, f, f]
    gdiplus.GdipClosePathFigure.argtypes = [c_void]
    gdiplus.GdipCreateSolidFill.argtypes = [ctypes.c_uint, ctypes.POINTER(c_void)]
    gdiplus.GdipFillPath.argtypes = [c_void, c_void, c_void]
    gdiplus.GdipDeleteBrush.argtypes = [c_void]
    gdiplus.GdipDeletePath.argtypes = [c_void]
    gdiplus.GdipCreatePen1.argtypes = [ctypes.c_uint, f, ctypes.c_int, ctypes.POINTER(c_void)]
    gdiplus.GdipDrawPath.argtypes = [c_void, c_void, c_void]
    gdiplus.GdipDeletePen.argtypes = [c_void]
    gdiplus.GdipCreateFontFamilyFromName.argtypes = [ctypes.c_wchar_p, c_void, ctypes.POINTER(c_void)]
    gdiplus.GdipCreateFont.argtypes = [c_void, f, ctypes.c_int, ctypes.c_int, ctypes.POINTER(c_void)]
    gdiplus.GdipDeleteFont.argtypes = [c_void]
    gdiplus.GdipDeleteFontFamily.argtypes = [c_void]
    gdiplus.GdipCreateStringFormat.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(c_void)]
    gdiplus.GdipDrawString.argtypes = [c_void, ctypes.c_wchar_p, ctypes.c_int, c_void, ctypes.POINTER(RECTF), c_void, c_void]
    gdiplus.GdipDeleteStringFormat.argtypes = [c_void]
    gdiplus.GdipDeleteGraphics.argtypes = [c_void]
    gdiplus.GdipDisposeImage.argtypes = [c_void]
    gdiplus.GdipBitmapLockBits.argtypes = [c_void, ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.POINTER(BitmapData)]
    gdiplus.GdipBitmapUnlockBits.argtypes = [c_void, ctypes.POINTER(BitmapData)]
    user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT), ctypes.POINTER(SIZE),
        wintypes.HDC, ctypes.POINTER(POINT), wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD,
    ]


def _argb(a: int, r: int, g: int, b: int) -> int:
    return (a << 24) | (r << 16) | (g << 8) | b


def _startup() -> None:
    global _STARTED
    if _STARTED:
        return
    _bind()
    info = GdiplusStartupInput(1, None, 0, 0)
    status = gdiplus.GdiplusStartup(ctypes.byref(_TOKEN), ctypes.byref(info), None)
    if status != 0:
        raise OSError(f"GdiplusStartup failed: {status}")
    _STARTED = True


def _round_rect(path, x, y, w, h, radius) -> None:
    radius = min(radius, w / 2, h / 2)
    diameter = radius * 2
    gdiplus.GdipAddPathArc(path, ctypes.c_float(x), ctypes.c_float(y), ctypes.c_float(diameter), ctypes.c_float(diameter), ctypes.c_float(180), ctypes.c_float(90))
    gdiplus.GdipAddPathArc(path, ctypes.c_float(x + w - diameter), ctypes.c_float(y), ctypes.c_float(diameter), ctypes.c_float(diameter), ctypes.c_float(270), ctypes.c_float(90))
    gdiplus.GdipAddPathArc(path, ctypes.c_float(x + w - diameter), ctypes.c_float(y + h - diameter), ctypes.c_float(diameter), ctypes.c_float(diameter), ctypes.c_float(0), ctypes.c_float(90))
    gdiplus.GdipAddPathArc(path, ctypes.c_float(x), ctypes.c_float(y + h - diameter), ctypes.c_float(diameter), ctypes.c_float(diameter), ctypes.c_float(90), ctypes.c_float(90))
    gdiplus.GdipClosePathFigure(path)


def _fill_round(graphics, x, y, w, h, radius, color) -> None:
    path = ctypes.c_void_p()
    brush = ctypes.c_void_p()
    gdiplus.GdipCreatePath(0, ctypes.byref(path))
    _round_rect(path, x, y, w, h, radius)
    gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
    gdiplus.GdipFillPath(graphics, brush, path)
    gdiplus.GdipDeleteBrush(brush)
    gdiplus.GdipDeletePath(path)


def _font(family_name: str, px: float, bold: bool = False):
    family = ctypes.c_void_p()
    font = ctypes.c_void_p()
    if gdiplus.GdipCreateFontFamilyFromName(family_name, None, ctypes.byref(family)) != 0:
        return None, None
    style = 1 if bold else 0
    if gdiplus.GdipCreateFont(family, ctypes.c_float(px), style, 2, ctypes.byref(font)) != 0:
        gdiplus.GdipDeleteFontFamily(family)
        return None, None
    return family, font


def _draw_text(graphics, text: str, font, x, y, w, h, color) -> None:
    if not text or font is None:
        return
    brush = ctypes.c_void_p()
    fmt = ctypes.c_void_p()
    gdiplus.GdipCreateSolidFill(color, ctypes.byref(brush))
    gdiplus.GdipCreateStringFormat(0x1000, 0, ctypes.byref(fmt))
    rect = RECTF(float(x), float(y), float(w), float(h))
    gdiplus.GdipDrawString(graphics, text, -1, font, ctypes.byref(rect), fmt, brush)
    gdiplus.GdipDeleteStringFormat(fmt)
    gdiplus.GdipDeleteBrush(brush)


def render_popup(labels: list[tuple[str, str]], hover: int | None) -> tuple[bytes, PopupMetrics]:
    """Return premultiplied top-down BGRA pixels and the layout they use."""
    _startup()
    metrics = popup_metrics(len(labels))
    width, height = metrics.width, metrics.height
    bitmap = ctypes.c_void_p()
    graphics = ctypes.c_void_p()
    if gdiplus.GdipCreateBitmapFromScan0(width, height, 0, PixelFormat32bppARGB, None, ctypes.byref(bitmap)) != 0:
        raise OSError("bitmap create failed")
    gdiplus.GdipGetImageGraphicsContext(bitmap, ctypes.byref(graphics))
    gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias)
    gdiplus.GdipSetTextRenderingHint(graphics, TextRenderingHintAntiAlias)
    gdiplus.GdipSetCompositingMode(graphics, 0)
    gdiplus.GdipGraphicsClear(graphics, 0)

    panel_x, panel_y = float(SHADOW), float(SHADOW)
    panel_w, panel_h = float(PANEL_WIDTH), float(height - SHADOW * 2)
    for spread, alpha in ((10, 18), (6, 28), (3, 36)):
        _fill_round(graphics, panel_x - spread, panel_y - spread + 2, panel_w + spread * 2, panel_h + spread * 2, 16, alpha << 24)
    _fill_round(graphics, panel_x, panel_y, panel_w, panel_h, 12, _argb(245, 36, 36, 40))
    _stroke_round(graphics, panel_x + 0.5, panel_y + 0.5, panel_w - 1, panel_h - 1, 12, _argb(70, 255, 255, 255))

    title_family, title_font = _font("Microsoft YaHei UI", 15, bold=True)
    if title_font is None:
        title_family, title_font = _font("Microsoft YaHei", 15, bold=True)
    body_family, body_font = _font("Microsoft YaHei UI", 12)
    if body_font is None:
        body_family, body_font = _font("Microsoft YaHei", 12)
    _draw_text(graphics, "短语", title_font, SHADOW + PAD, SHADOW + 6, 80, 20, _argb(255, 255, 255, 255))
    _draw_text(graphics, "移到对应短语后松开即发送", body_font, SHADOW + PAD, SHADOW + 26, PANEL_WIDTH - PAD * 2, 18, _argb(210, 210, 214, 222))

    for index, (label, detail) in enumerate(labels):
        rx, ry, rw, rh = metrics.rows[index]
        selected = index == hover
        fill = _argb(150, 10, 132, 255) if selected else _argb(32, 255, 255, 255)
        _fill_round(graphics, rx, ry, rw, rh, 8, fill)
        if detail:
            _draw_text(graphics, label, title_font, rx + 14, ry + 3, rw - 28, 22, _argb(255, 255, 255, 255))
            _draw_text(graphics, detail, body_font, rx + 14, ry + 24, rw - 28, 18, _argb(220, 220, 224, 232))
        else:
            _draw_text(graphics, label, title_font, rx + 14, ry + 12, rw - 28, 22, _argb(255, 255, 255, 255))

    pixels = _read_premultiplied(bitmap, width, height)
    for obj, deleter in (
        (title_font, gdiplus.GdipDeleteFont),
        (body_font, gdiplus.GdipDeleteFont),
        (title_family, gdiplus.GdipDeleteFontFamily),
        (body_family, gdiplus.GdipDeleteFontFamily),
        (graphics, gdiplus.GdipDeleteGraphics),
        (bitmap, gdiplus.GdipDisposeImage),
    ):
        if obj:
            deleter(obj)
    return pixels, metrics


def _stroke_round(graphics, x, y, w, h, radius, color) -> None:
    path = ctypes.c_void_p()
    pen = ctypes.c_void_p()
    gdiplus.GdipCreatePath(0, ctypes.byref(path))
    _round_rect(path, x, y, w, h, radius)
    gdiplus.GdipCreatePen1(color, ctypes.c_float(1), 2, ctypes.byref(pen))
    gdiplus.GdipDrawPath(graphics, pen, path)
    gdiplus.GdipDeletePen(pen)
    gdiplus.GdipDeletePath(path)


def _read_premultiplied(bitmap, width: int, height: int) -> bytes:
    data = BitmapData()
    rect = (ctypes.c_int * 4)(0, 0, width, height)
    status = gdiplus.GdipBitmapLockBits(bitmap, rect, 1, PixelFormat32bppARGB, ctypes.byref(data))
    if status != 0 or not data.Scan0:
        raise OSError(f"lock bits failed: {status}")
    try:
        out = bytearray(width * height * 4)
        stride = abs(data.Stride)
        for y in range(height):
            src_y = y if data.Stride > 0 else height - 1 - y
            row = ctypes.string_at(data.Scan0 + src_y * stride, width * 4)
            for x in range(width):
                b, g, r, a = row[x * 4 : x * 4 + 4]
                out[(y * width + x) * 4 : (y * width + x) * 4 + 4] = bytes((b * a // 255, g * a // 255, r * a // 255, a))
        return bytes(out)
    finally:
        gdiplus.GdipBitmapUnlockBits(bitmap, ctypes.byref(data))


def render_tray_icon(size: int = 32) -> ctypes.wintypes.HICON:
    """Dark rounded list mark, sized for the tray."""
    _startup()
    size = max(16, int(size))
    bitmap = ctypes.c_void_p()
    graphics = ctypes.c_void_p()
    if gdiplus.GdipCreateBitmapFromScan0(size, size, 0, PixelFormat32bppARGB, None, ctypes.byref(bitmap)) != 0:
        raise OSError("tray bitmap failed")
    gdiplus.GdipGetImageGraphicsContext(bitmap, ctypes.byref(graphics))
    gdiplus.GdipSetSmoothingMode(graphics, SmoothingModeAntiAlias)
    gdiplus.GdipGraphicsClear(graphics, 0)
    inset = max(1, size // 16)
    radius = max(4, size // 4)
    _fill_round(graphics, inset, inset, size - inset * 2, size - inset * 2, radius, _argb(255, 32, 32, 36))
    _stroke_round(graphics, inset + 0.5, inset + 0.5, size - inset * 2 - 1, size - inset * 2 - 1, radius, _argb(80, 255, 255, 255))
    bar_x = size * 0.28
    bar_w = size * 0.44
    bar_h = max(2, size * 0.08)
    gap = size * 0.16
    top = size * 0.30
    for index, color in enumerate((_argb(230, 255, 255, 255), _argb(255, 10, 132, 255), _argb(170, 255, 255, 255))):
        _fill_round(graphics, bar_x, top + index * gap, bar_w, bar_h, bar_h / 2, color)
    pixels = _read_premultiplied(bitmap, size, size)
    gdiplus.GdipDeleteGraphics(graphics)
    gdiplus.GdipDisposeImage(bitmap)
    return _hicon_from_pixels(pixels, size, size)


def _hicon_from_pixels(pixels: bytes, width: int, height: int):
    class ICONINFO(ctypes.Structure):
        _fields_ = [
            ("fIcon", wintypes.BOOL),
            ("xHotspot", wintypes.DWORD),
            ("yHotspot", wintypes.DWORD),
            ("hbmMask", wintypes.HBITMAP),
            ("hbmColor", wintypes.HBITMAP),
        ]

    bmi = (ctypes.c_byte * 40)()
    ctypes.memmove(bmi, (40).to_bytes(4, "little"), 4)
    ctypes.memmove(ctypes.addressof(bmi) + 4, width.to_bytes(4, "little", signed=True), 4)
    ctypes.memmove(ctypes.addressof(bmi) + 8, (-height).to_bytes(4, "little", signed=True), 4)
    ctypes.memmove(ctypes.addressof(bmi) + 12, (1).to_bytes(2, "little"), 2)
    ctypes.memmove(ctypes.addressof(bmi) + 14, (32).to_bytes(2, "little"), 2)
    screen = user32.GetDC(None)
    bits = ctypes.c_void_p()
    color = gdi32.CreateDIBSection(screen, bmi, 0, ctypes.byref(bits), None, 0)
    if not color or not bits:
        user32.ReleaseDC(None, screen)
        raise OSError("tray dib failed")
    ctypes.memmove(bits, pixels, len(pixels))
    mask = gdi32.CreateBitmap(width, height, 1, 1, None)
    info = ICONINFO(True, 0, 0, mask, color)
    user32.CreateIconIndirect.restype = wintypes.HICON
    icon = user32.CreateIconIndirect(ctypes.byref(info))
    gdi32.DeleteObject(color)
    gdi32.DeleteObject(mask)
    user32.ReleaseDC(None, screen)
    if not icon:
        raise OSError("CreateIconIndirect failed")
    return icon


def place_popup(press_x: int, press_y: int, metrics: PopupMetrics) -> tuple[int, int]:
    vx = int(user32.GetSystemMetrics(76))
    vy = int(user32.GetSystemMetrics(77))
    vw = int(user32.GetSystemMetrics(78))
    vh = int(user32.GetSystemMetrics(79))
    left = press_x - 28 - SHADOW
    top = press_y + 14 - SHADOW
    left = max(vx + 4, min(left, vx + vw - metrics.width - 4))
    top = max(vy + 4, min(top, vy + vh - metrics.height - 4))
    return left, top


class GlassPopup:
    def __init__(self) -> None:
        self.hwnd = None
        self._proc = _WNDPROC(self._wndproc)
        self._class = "PhraseGlassPopup"

    def _ensure(self) -> None:
        if self.hwnd:
            return
        instance = ctypes.windll.kernel32.GetModuleHandleW(None)
        window_class = WNDCLASSW()
        window_class.lpfnWndProc = ctypes.cast(self._proc, ctypes.c_void_p)
        window_class.hInstance = instance
        window_class.lpszClassName = self._class
        user32.RegisterClassW(ctypes.byref(window_class))
        self.hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            self._class,
            "短语",
            WS_POPUP,
            0,
            0,
            10,
            10,
            None,
            None,
            instance,
            None,
        )

    def show(self, left: int, top: int, pixels: bytes, width: int, height: int) -> None:
        self._ensure()
        self._present(left, top, pixels, width, height)
        user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        user32.SetWindowPos(self.hwnd, HWND_TOPMOST, left, top, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW)

    def hide(self) -> None:
        if self.hwnd:
            user32.ShowWindow(self.hwnd, SW_HIDE)

    def _present(self, left: int, top: int, pixels: bytes, width: int, height: int) -> None:
        bmi = (ctypes.c_byte * 40)()
        ctypes.memmove(bmi, (40).to_bytes(4, "little"), 4)
        ctypes.memmove(ctypes.addressof(bmi) + 4, width.to_bytes(4, "little", signed=True), 4)
        ctypes.memmove(ctypes.addressof(bmi) + 8, (-height).to_bytes(4, "little", signed=True), 4)
        ctypes.memmove(ctypes.addressof(bmi) + 12, (1).to_bytes(2, "little"), 2)
        ctypes.memmove(ctypes.addressof(bmi) + 14, (32).to_bytes(2, "little"), 2)
        bits = ctypes.create_string_buffer(pixels)
        screen = user32.GetDC(None)
        mem = gdi32.CreateCompatibleDC(screen)
        hbmp = gdi32.CreateDIBSection(screen, bmi, 0, None, None, 0)
        # CreateDIBSection with NULL bits pointer writes into the bitmap; copy after.
        selected = gdi32.SelectObject(mem, hbmp)
        # Recreate with a pointer so we can write pixels directly.
        gdi32.SelectObject(mem, selected)
        gdi32.DeleteObject(hbmp)
        pv = ctypes.c_void_p()
        hbmp = gdi32.CreateDIBSection(screen, bmi, 0, ctypes.byref(pv), None, 0)
        if not hbmp or not pv:
            user32.ReleaseDC(None, screen)
            raise OSError("DIB section failed")
        ctypes.memmove(pv, pixels, len(pixels))
        gdi32.SelectObject(mem, hbmp)
        dst = POINT(left, top)
        size = SIZE(width, height)
        src = POINT(0, 0)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(dst), ctypes.byref(size), mem, ctypes.byref(src), 0, ctypes.byref(blend), ULW_ALPHA)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(mem)
        user32.ReleaseDC(None, screen)

    def _wndproc(self, hwnd, msg, wparam, lparam):
        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, ctypes.c_size_t, ctypes.c_ssize_t]
        user32.DefWindowProcW.restype = ctypes.c_ssize_t
        return user32.DefWindowProcW(hwnd, msg, ctypes.c_size_t(wparam).value, ctypes.c_ssize_t(lparam).value)
