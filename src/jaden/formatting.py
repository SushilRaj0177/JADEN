"""JADEN: Output formats for a normalized address.

    canonical   東京都港区芝公園4丁目2番8号 グランドメゾン芝公園 302
    hyphen      東京都港区芝公園4-2-8 グランドメゾン芝公園 302     (the compact form most systems store)
    en          Grand Maison 302, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011
    lines()     ('〒105-0011', '東京都港区芝公園4丁目2番8号', 'グランドメゾン芝公園 302')

The hyphen form is lossless for JADEN: normalizing it again gives the same result.
"""

from typing import List, Tuple

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
        numbers = [n for n in (c.ban, c.go) if n is not None] or [n for n in (c.banchi, c.edaban) if n is not None]
        out += "-".join(str(n) for n in numbers)
    elif c.lot_number is not None:
        out += (f"{c.chome}丁目" if c.chome is not None else "") + c.lot_number
    elif c.chome is not None and c.ban is None and c.banchi is None:
        out += f"{c.chome}丁目"
    else:
        numbers = [n for n in (c.chome, c.ban, c.go) if n is not None]
        if c.banchi is not None:
            numbers = ([c.chome] if c.chome is not None else []) + [n for n in (c.banchi, c.edaban) if n is not None]
        out += "-".join(str(n) for n in numbers)
    tail = _secondary(res)
    return f"{out} {tail}" if tail else out


def format_address(res: NormalizedAddress, style: str = "canonical") -> str:
    if style == "canonical":
        return res.canonical
    if style == "hyphen":
        return hyphenated(res) if res.confidence_score > 0 else res.canonical
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
