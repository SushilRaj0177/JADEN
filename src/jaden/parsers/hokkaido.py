"""JADEN: Hokkaido cardinal grid address parser (条・丁目 碁盤目構造).

Parses Tier 2 Hokkaido Jo-Chome cardinal coordinate addressing
(e.g., '北1条西2丁目', '南3条東4丁目').
"""

import re
from typing import Optional, Tuple, Final
from ..models.address import HokkaidoGridClause
from ..core.kanji_numerals import parse_kanji_number

_HOKKAIDO_GRID_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<ns>北|南)(?P<jo>\d+|[〇一二三四五六七八九十]+)条"
    r"(?P<ew>東|西)(?P<chome>\d+|[〇一二三四五六七八九十]+)丁目"
)


class HokkaidoParser:
    """Parses Hokkaido cardinal grid Jo-Chome clauses."""

    @staticmethod
    def parse(text: str) -> Tuple[Optional[HokkaidoGridClause], str]:
        """Detects and extracts Hokkaido Jo-Chome grid coordinates.

        Args:
            text: Address string (e.g., '北1条西2丁目1番地').

        Returns:
            Tuple of (HokkaidoGridClause or None, remaining_address_text).
        """
        match = _HOKKAIDO_GRID_PATTERN.search(text)
        if not match:
            return None, text

        start, end = match.span()
        raw_clause = text[start:end]

        cardinal_ns = match.group("ns")
        jo_raw = match.group("jo")
        jo = int(jo_raw) if jo_raw.isdigit() else parse_kanji_number(jo_raw)

        cardinal_ew = match.group("ew")
        chome_raw = match.group("chome")
        chome = int(chome_raw) if chome_raw.isdigit() else parse_kanji_number(chome_raw)

        clause = HokkaidoGridClause(
            cardinal_ns=cardinal_ns,
            jo=jo,
            cardinal_ew=cardinal_ew,
            chome=chome,
            raw_clause=raw_clause,
        )

        remaining = (text[:start] + text[end:]).strip()
        return clause, remaining
