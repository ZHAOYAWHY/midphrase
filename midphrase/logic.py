"""Pure phrase-wheel decisions. No Windows calls, so tests can run headless."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def list_index(x: float, y: float, left: float, top: float, width: float, row_height: float, count: int) -> int | None:
    """Return the row under a point, or None when the point is outside the list."""
    if count <= 0 or row_height <= 0 or width <= 0:
        return None
    if x < left or x >= left + width or y < top or y >= top + count * row_height:
        return None
    return int((y - top) // row_height)


def list_origin(press_x: int, press_y: int, count: int, *, width: int, row_height: int, screen_w: int, screen_h: int) -> tuple[int, int]:
    """Place the list just below the press point, clamped to the screen."""
    height = max(row_height, count * row_height)
    left = press_x - 24
    top = press_y + 12
    left = max(8, min(left, max(8, screen_w - width - 8)))
    top = max(8, min(top, max(8, screen_h - height - 8)))
    return left, top


PANEL_WIDTH = 300
SHADOW = 18
PAD = 10
HEADER = 54
ROW_H = 46
ROW_GAP = 6


@dataclass(frozen=True)
class PopupMetrics:
    width: int
    height: int
    header_bottom: int
    rows: tuple[tuple[int, int, int, int], ...]


def popup_metrics(count: int) -> PopupMetrics:
    """Content-box geometry. Window origin includes the shadow margin."""
    rows = []
    y = SHADOW + PAD + HEADER + 4
    inner_w = PANEL_WIDTH - PAD * 2
    for _ in range(max(count, 0)):
        rows.append((SHADOW + PAD, y, inner_w, ROW_H))
        y += ROW_H + ROW_GAP
    content_bottom = (rows[-1][1] + rows[-1][3] + PAD + SHADOW) if rows else SHADOW + PAD + HEADER + PAD + SHADOW
    return PopupMetrics(PANEL_WIDTH + SHADOW * 2, content_bottom, SHADOW + PAD + HEADER, tuple(rows))


def hit_row(x: float, y: float, left: float, top: float, rows: tuple[tuple[int, int, int, int], ...]) -> int | None:
    local_x = x - left
    local_y = y - top
    for index, (rx, ry, rw, rh) in enumerate(rows):
        if rx <= local_x < rx + rw and ry <= local_y < ry + rh:
            return index
    return None


def sector_index(dx: float, dy: float, count: int, dead_zone: float) -> int | None:
    """Map a pointer offset to a clockwise slice. 12 o'clock is slice 0."""
    if count <= 0:
        return None
    if math.hypot(dx, dy) < dead_zone:
        return None
    # Screen Y grows downward, so atan2 increases clockwise.
    angle = math.atan2(dy, dx)
    offset = (angle + math.pi / 2) % (math.tau)
    return int(offset / (math.tau / count)) % count


@dataclass(frozen=True)
class Action:
    kind: str
    index: int | None = None


class Gesture:
    """Middle-button gesture: short click, or long-press wheel then release."""

    def __init__(self, long_press_ms: int = 400, move_slop: int = 12) -> None:
        self.long_press_ms = long_press_ms
        self.move_slop = move_slop
        self._phase = "idle"
        self._x = 0
        self._y = 0
        self._t = 0

    @property
    def origin(self) -> tuple[int, int]:
        return self._x, self._y

    @property
    def open(self) -> bool:
        return self._phase == "open"

    def down(self, x: int, y: int, now_ms: int) -> str:
        self._phase = "holding"
        self._x, self._y, self._t = x, y, now_ms
        return "wait"

    def move(self, x: int, y: int, now_ms: int) -> str:
        return self._advance(x, y, now_ms)

    def tick(self, x: int, y: int, now_ms: int) -> str:
        return self._advance(x, y, now_ms)

    def up(self, x: int, y: int, now_ms: int, phrase_count: int, dead_zone: float) -> Action:
        phase = self._phase
        origin_x, origin_y = self._x, self._y
        self._phase = "idle"
        if phase != "open":
            return Action("short_click")
        index = sector_index(x - origin_x, y - origin_y, phrase_count, dead_zone)
        if index is None:
            return Action("cancel")
        return Action("commit", index)

    def _advance(self, x: int, y: int, now_ms: int) -> str:
        if self._phase != "holding":
            return "wait"
        moved = math.hypot(x - self._x, y - self._y)
        if moved > self.move_slop:
            self._phase = "dragged"
            return "wait"
        if now_ms - self._t >= self.long_press_ms:
            self._phase = "open"
            return "open"
        return "wait"


DEFAULT_PHRASES = (
    {"label": "收到", "text": "收到"},
    {"label": "马上处理", "text": "好的，马上处理"},
    {"label": "谢谢", "text": "谢谢"},
    {"label": "我看一下", "text": "我看一下，稍后回复你"},
    {"label": "没问题", "text": "没问题"},
    {"label": "稍后回复", "text": "现在不方便，稍后回复你"},
)


@dataclass(frozen=True)
class Phrase:
    label: str
    text: str

    @property
    def wheel_label(self) -> str:
        return self.label or self.text


DISPLAY_BRIEF = "brief"
DISPLAY_FULL = "full"
DISPLAY_BOTH = "both"
DISPLAY_MODES = (DISPLAY_BRIEF, DISPLAY_FULL, DISPLAY_BOTH)


def row_caption(phrase: Phrase, mode: str) -> tuple[str, str]:
    """What a candidate row shows. The sent text is always phrase.text."""
    brief = phrase.label or phrase.text
    full = phrase.text
    if mode == DISPLAY_FULL:
        return full, ""
    if mode == DISPLAY_BOTH and full != brief:
        return brief, full
    return brief, ""


class PhraseStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.display_mode = DISPLAY_BOTH

    def load(self) -> list[Phrase]:
        if not self.path.is_file():
            self.display_mode = DISPLAY_BOTH
            return [Phrase(item["label"], item["text"]) for item in DEFAULT_PHRASES]
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.display_mode = _normalize_display_mode(data.get("display_mode"))
        return _phrases_from_raw(data.get("phrases", []))

    def save(self, raw_items: list[dict]) -> list[Phrase]:
        phrases = _phrases_from_raw(raw_items)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "long_press_ms": 400,
            "display_mode": self.display_mode,
            "phrases": [{"label": item.label, "text": item.text} for item in phrases],
        }
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return phrases

    def set_display_mode(self, mode: str) -> str:
        mode = _normalize_display_mode(mode)
        if self.path.is_file():
            data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            data = {"phrases": [dict(item) for item in DEFAULT_PHRASES]}
        data["display_mode"] = mode
        self.display_mode = mode
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return self.display_mode


def _normalize_display_mode(mode: object) -> str:
    text = str(mode or "").strip().lower()
    if text in DISPLAY_MODES:
        return text
    return DISPLAY_BOTH


def _phrases_from_raw(raw_items: list[dict]) -> list[Phrase]:
    phrases: list[Phrase] = []
    for item in raw_items:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        label = str(item.get("label", "")).strip() or text
        phrases.append(Phrase(label, text))
    return phrases


def export_filename(when: datetime) -> str:
    return when.strftime("中键短语-%Y%m%d-%H%M.txt")


EXPORT_HEADER = """# 以 # 开头的行是说明，导入时会忽略。
# 请用 UTF-8 保存，也不要改成 CSV。
# 一行一条短语。简称和全短语之间按一次 Tab，不要用空格代替，一行里不要有第二个 Tab。
# 只有字符串、没有 Tab：这句话同时作为简称和全短语。
# 以 Tab 开头：没有简称，用全短语补上。以 Tab 结尾：没有全短语，用简称补上。
# 简称和全短语都相同：只保留第一条。
# 简称相同、全短语不同：第一条保持原简介，后面的改为 简介-1、简介-2；编号已被占用就跳过。
"""


def export_phrases(phrases: list[Phrase]) -> str:
    """One phrase per line: short name, tab, full phrase. UTF-8 text, no BOM."""
    lines = [f"{phrase.label}\t{phrase.text}" for phrase in phrases]
    body = "\n".join(lines)
    return EXPORT_HEADER + (body + "\n" if body else "")


def import_phrases(text: str) -> tuple[list[Phrase], list[str]]:
    phrases, errors, _note = load_import(text)
    return phrases, errors


def load_import(text: str) -> tuple[list[Phrase], list[str], str]:
    """Parse a phrase file and resolve duplicate short names inside that file."""
    phrases, errors = parse_phrase_file(text)
    if errors:
        return [], errors, ""
    resolved, note = merge_phrases([], phrases)
    return resolved, [], note


def parse_phrase_file(text: str) -> tuple[list[Phrase], list[str]]:
    """Read phrase lines without applying conflict suffixes yet."""
    if "\x00" in text:
        return [], ["文件含有二进制内容，已拒绝导入"]
    phrases: list[Phrase] = []
    errors: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip("\ufeff").rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.count("\t") > 1:
            errors.append(f"第 {number} 行有多余的制表符，无法区分简称和全短语")
            continue
        if "\t" not in line:
            value = line.strip()
            if value:
                phrases.append(Phrase(value, value))
            continue
        short, full = line.split("\t", 1)
        short = short.strip()
        full = full.strip()
        if not short and not full:
            continue
        if not short:
            short = full
        if not full:
            full = short
        phrases.append(Phrase(short, full))
    if errors:
        return [], errors
    return phrases, []


def merge_phrases(existing: list[Phrase], incoming: list[Phrase]) -> tuple[list[Phrase], str]:
    """Keep earlier phrases, then apply the same conflict rules to the whole list.

    Existing phrases come first, so they keep their short names. Conflicts already
    present in the imported file are resolved in the same pass, after those.
    """
    combined = [*existing, *incoming]
    unique = _drop_exact_duplicates(combined)
    resolved = _resolve_import_conflicts(combined)
    renamed = sum(before.label != after.label for before, after in zip(unique, resolved))
    return resolved, _import_note(len(combined) - len(unique), renamed)


def _import_note(dropped: int, renamed: int) -> str:
    parts: list[str] = []
    if dropped:
        parts.append(f"去掉 {dropped} 条完全相同的记录")
    if renamed:
        parts.append(f"{renamed} 条简介重复，已加上 -1、-2 这样的后缀")
    return "；".join(parts)


def _drop_exact_duplicates(phrases: list[Phrase]) -> list[Phrase]:
    seen: set[tuple[str, str]] = set()
    unique: list[Phrase] = []
    for phrase in phrases:
        key = (phrase.label, phrase.text)
        if key in seen:
            continue
        seen.add(key)
        unique.append(phrase)
    return unique


def _resolve_import_conflicts(phrases: list[Phrase]) -> list[Phrase]:
    unique = _drop_exact_duplicates(phrases)
    used = {phrase.label for phrase in unique}
    resolved: list[Phrase] = []
    seen_labels: set[str] = set()
    for phrase in unique:
        label = phrase.label
        if label in seen_labels:
            number = 1
            while f"{label}-{number}" in used:
                number += 1
            label = f"{label}-{number}"
            used.add(label)
        else:
            seen_labels.add(phrase.label)
        resolved.append(Phrase(label, phrase.text))
    return resolved
