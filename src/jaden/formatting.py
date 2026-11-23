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


def _in_number(text: str, at: int) -> bool:
    """True when a cut before ``text[at]`` would split a number such as '4-2-8' or '４－２－８'."""
    if not 0 < at < len(text):
        return False
    before, after = text[at - 1], text[at]
    dash = "-－‐"
    joined = (before.isdigit() and (after.isdigit() or after in dash)) or (before in dash and after.isdigit())
    return joined


def _cut(text: str, width: int, count: str) -> Tuple[str, str, bool]:
    """(the longest head of ``text`` that fits, the rest, whether the cut fell inside a word). A number
    such as '4-2-8' is never split when the line can break before it."""
    end = 0
    while end < len(text) and _measure(text[:end + 1], count) <= width:
        end += 1
    if _in_number(text, end):
        back = end
        while back > 0 and _in_number(text, back):
            back -= 1
        if back > 0:
            end = back
    inside = 0 < end < len(text) and not text[end - 1].isspace() and not text[end].isspace()
    return text[:end].rstrip(), text[end:].lstrip(), inside


def label_lines(res: NormalizedAddress, width: int = 20, max_lines: int = 3, count: str = "chars",
                style: str = "hyphen", fullwidth: bool = False, postal_line: bool = False) -> LabelLines:
    """The address in at most ``max_lines`` lines of at most ``width`` characters (or Shift_JIS bytes),
    broken between its parts: prefecture and municipality, town and numbers, building, floor and room
    ('en': between the comma-separated parts of the English line). A part longer than a line is cut,
    never inside a number when the line can break before it. ``fullwidth`` writes digits, letters and
    hyphens in full width, as many label systems require. Every line, the postal line included, is
    within ``width``; ``overflow`` is what did not fit, as written."""
    if width < 4 or max_lines < 1:
        raise ValueError("width must be at least 4 and max_lines at least 1")
    if count not in ("chars", "bytes"):
        raise ValueError("count must be 'chars' or 'bytes'")
    if style not in STYLES:
        raise ValueError(f"unknown style '{style}'; use one of {', '.join(STYLES)}")
    c = res.components
    resolved = res.confidence_score > 0 and bool(c.lg_code) and not c.is_ambiguous
    # (text, what joins it to the previous part on one line)
    parts: List[Tuple[str, str]] = []
    if style == "en" and resolved and res.romaji:
        pieces = res.romaji.split(", ")
        parts = [(p if i == len(pieces) - 1 else p + ",", " ") for i, p in enumerate(pieces)]
    elif resolved:
        text = format_address(res, "canonical" if style == "en" else style)
        tail = _secondary(res)
        body = text[: len(text) - len(tail)].rstrip() if tail and text.endswith(tail) else text
        admin = _admin_part(res)
        if body.startswith(admin):
            muni = admin[len(c.prefecture or "") + len(c.county or ""):]
            parts += [(c.prefecture or "", ""), (c.county or "", ""), (muni, ""), (body[len(admin):], "")]
        else:
            parts.append((body, ""))
        parts += [(c.building or "", " "), (" ".join(x for x in (c.floor, c.unit) if x), " ")]
    else:
        parts.append((res.canonical, ""))
    parts = [(t, sp) for t, sp in parts if t]
    if fullwidth:
        parts = [(t.translate(_TO_FULLWIDTH), sp.translate(_TO_FULLWIDTH)) for t, sp in parts]

    # Lines as (text, what joins it to the previous line in the overflow: the part separator, or '' when
    # the line continues a cut word)
    lines: List[Tuple[str, str]] = []
    if postal_line and c.postal_code:
        postal = f"〒{c.postal_code}"
        parts.insert(0, (postal.translate(_TO_FULLWIDTH) if fullwidth else postal, ""))
    current, current_join = "", ""
    for index, (part, joiner) in enumerate(parts):
        own_line = postal_line and c.postal_code and index <= 1      # the postal code stands alone
        joined = f"{current}{joiner}{part}"
        if current and not own_line and _measure(joined, count) <= width:
            current = joined
            continue
        if current:
            lines.append((current, current_join))
        current, current_join = part, joiner
        while _measure(current, count) > width:
            head, current, inside = _cut(current, width, count)
            if not head:
                head, current, inside = current[:1], current[1:], True
            lines.append((head, current_join))
            current_join = "" if inside else " "
    if current:
        lines.append((current, current_join))
    fits = len(lines) <= max_lines
    overflow = "".join(join + text for text, join in lines[max_lines:]).lstrip()
    return LabelLines(tuple(t for t, _ in lines[:max_lines]), fits, width, count, "" if fits else overflow)
