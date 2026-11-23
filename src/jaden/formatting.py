"""JADEN: Output formats for a normalized address.

    canonical   東京都港区芝公園4丁目2番8号 グランドメゾン芝公園 302
    hyphen      東京都港区芝公園4-2-8 グランドメゾン芝公園 302     (the compact form most systems store)
    en          Grand Maison 302, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011
    lines()     ('〒105-0011', '東京都港区芝公園4丁目2番8号', 'グランドメゾン芝公園 302')

The hyphen form is lossless for JADEN: normalizing it again gives the same result.
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .models.address import NormalizedAddress

STYLES = ("canonical", "hyphen", "en")


def _admin_part(res: NormalizedAddress) -> str:
    c = res.components
    parts = [c.prefecture or "", c.county or "", c.city or ""]
    if c.ward and c.ward not in (c.city or ""):
        parts.append(c.ward)
    if c.kyoto_direction:
        parts.append(c.kyoto_direction.raw_clause)
    return "".join(parts)


def _secondary(res: NormalizedAddress) -> str:
    c = res.components
    return " ".join(x for x in (c.building, c.floor, c.unit) if x)


def hyphenated(res: NormalizedAddress) -> str:
    c = res.components
    out = _admin_part(res) + (c.town or "")
    grid = c.hokkaido_grid
    if grid is not None:
        out += f"{grid.cardinal_ns}{grid.jo}条{grid.cardinal_ew}{grid.chome}丁目"
        if c.ban is not None:
            out += "-".join(str(n) for n in (c.ban, c.go) if n is not None)
        elif c.banchi is not None:
            out += f"{c.banchi}番地" + (str(c.edaban) if c.edaban is not None else "")
    elif c.lot_number is not None:
        out += (f"{c.chome}丁目" if c.chome is not None else "") + c.lot_number
    elif c.chome is not None and c.ban is None and c.banchi is None:
        out += f"{c.chome}丁目"
    else:
        if c.banchi is not None:
            # A lot keeps its 番地, or '3008-1' would read back as 3008番1号: '3008番地1', '1丁目20番地48'
            out += (f"{c.chome}丁目" if c.chome is not None else "") + f"{c.banchi}番地" + \
                (str(c.edaban) if c.edaban is not None else "")
        elif c.chome is not None and c.ban is not None and (c.go is None or c.chome_verified is not True):
            # '3丁目1718番': '3-1718' would read back as 3番1718号; a 丁目 the registry does not list
            # ('宇地泊1丁目20番7号') would read back as a lot number
            out += f"{c.chome}丁目" + "-".join(str(n) for n in (c.ban, c.go) if n is not None)
        else:
            out += "-".join(str(n) for n in (c.chome, c.ban, c.go) if n is not None)
    tail = _secondary(res)
    return f"{out} {tail}" if tail else out


def format_address(res: NormalizedAddress, style: str = "canonical") -> str:
    if style == "canonical":
        return res.canonical
    if style == "hyphen":
        # Without one municipality the text is not interpreted, so there is nothing to shorten
        resolved = res.confidence_score > 0 and res.components.lg_code and not res.components.is_ambiguous
        return hyphenated(res) if resolved else res.canonical
    if style == "en":
        return res.romaji or ""
    raise ValueError(f"unknown style '{style}'; use one of {', '.join(STYLES)}")


def address_lines(res: NormalizedAddress) -> Tuple[str, ...]:
    c = res.components
    lines: List[str] = []
    if c.postal_code:
        lines.append(f"〒{c.postal_code}")
    tail = _secondary(res)
    base = res.canonical[: len(res.canonical) - len(tail)].rstrip() if tail and res.canonical.endswith(tail) else res.canonical
    lines.append(base)
    if tail:
        lines.append(tail)
    return tuple(lines)


# ------------------------------------------------------------------ labels
_TO_FULLWIDTH = {c: c + 0xFEE0 for c in range(0x21, 0x7F)}
_TO_FULLWIDTH[0x20] = 0x3000
_TO_FULLWIDTH[ord("-")] = ord("－")


@dataclass(frozen=True)
class LabelLines:
    """An address split into lines that fit a label or a form with fixed field lengths."""
    lines: Tuple[str, ...]
    fits: bool                   # every part fitted in the lines and width given
    width: int
    count: str                   # 'chars' or 'bytes' (Shift_JIS bytes: full-width 2, half-width 1)
    overflow: str = ""           # what did not fit

    def to_dict(self) -> Dict[str, object]:
        return {"lines": list(self.lines), "fits": self.fits, "width": self.width, "count": self.count,
                "overflow": self.overflow}


def _measure(text: str, count: str) -> int:
    if count == "chars":
        return len(text)
    return sum(1 if (ord(ch) < 0x80 or 0xFF61 <= ord(ch) <= 0xFF9F) else 2 for ch in text)


def _cut(text: str, width: int, count: str) -> Tuple[str, str]:
    """The longest head of ``text`` that fits, not ending inside a run of digits when that can be avoided."""
    end = 0
    while end < len(text) and _measure(text[:end + 1], count) <= width:
        end += 1
    if 0 < end < len(text) and text[end - 1].isdigit() and text[end].isdigit():
        back = end
        while back > 0 and text[back - 1].isdigit():
            back -= 1
        if back > 0:
            end = back
    return text[:end].rstrip(), text[end:].lstrip()


def label_lines(res: NormalizedAddress, width: int = 20, max_lines: int = 3, count: str = "chars",
                style: str = "hyphen", fullwidth: bool = False, postal_line: bool = False) -> LabelLines:
    """The address in at most ``max_lines`` lines of at most ``width`` characters (or Shift_JIS bytes),
    broken between its parts: prefecture and municipality, town and numbers, building, floor and room.
    A part longer than a line is cut, never inside a number. ``fullwidth`` writes digits, letters and
    hyphens in full width, as many label systems require."""
    if width < 4 or max_lines < 1:
        raise ValueError("width must be at least 4 and max_lines at least 1")
    if count not in ("chars", "bytes"):
        raise ValueError("count must be 'chars' or 'bytes'")
    c = res.components
    text = format_address(res, style)
    tail = _secondary(res)
    resolved = res.confidence_score > 0 and bool(c.lg_code) and not c.is_ambiguous
    # (text, joined to the previous part with a space): the prefecture, county, municipality and town
    # run together as written; the building and the room are set apart
    parts: List[Tuple[str, bool]] = []
    if resolved:
        body = text[: len(text) - len(tail)].rstrip() if tail and text.endswith(tail) else text
        admin = _admin_part(res)
        if body.startswith(admin):
            muni = admin[len(c.prefecture or "") + len(c.county or ""):]
            parts += [(c.prefecture or "", False), (c.county or "", False), (muni, False), (body[len(admin):], False)]
        else:
            parts.append((body, False))
        parts += [(c.building or "", True), (" ".join(x for x in (c.floor, c.unit) if x), True)]
    else:
        parts.append((text, False))
    parts = [(t, sp) for t, sp in parts if t]
    if fullwidth:
        parts = [(t.translate(_TO_FULLWIDTH), sp) for t, sp in parts]
    space = "　" if fullwidth else " "

    lines: List[str] = []
    if postal_line and c.postal_code:
        lines.append(f"〒{c.postal_code}".translate(_TO_FULLWIDTH) if fullwidth else f"〒{c.postal_code}")
    current = ""
    for part, spaced in parts:
        joined = f"{current}{space if spaced else ''}{part}"
        if current and _measure(joined, count) <= width:
            current = joined
            continue
        if current:
            lines.append(current)
        current = part
        while _measure(current, count) > width:
            head, current = _cut(current, width, count)
            if not head:
                head, current = current[:1], current[1:]
            lines.append(head)
    if current:
        lines.append(current)
    fits = len(lines) <= max_lines
    return LabelLines(tuple(lines[:max_lines]), fits, width, count,
                      "" if fits else space.join(lines[max_lines:]))
