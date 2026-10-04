"""JADEN: Kyoto conventional street-intersection navigation parser (通り名解析).

Parses Tier 2 Kyoto navigation syntax (Tōri-mei + Direction: 上る/下る/東入/西入)
and isolates the underlying cadastral town name (町名) and lot number.
"""

import re
from typing import Optional, Tuple, Final
from ..models.address import KyotoDirectionClause
from ..core.constants import KYOTO_DIRECTIONS

# Directional tokens regex - sorted by length descending to match '西入る' before '西入'
_DIR_TOKENS = "|".join(re.escape(k) for k in sorted(KYOTO_DIRECTIONS.keys(), key=len, reverse=True))

# Regex matching Kyoto intersection syntax:
# [Street 1 with '通'] + [Cross street] + [Direction token]
_KYOTO_INTERSECTION_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?:(?P<street1>[^通\s\d]+通))?"
    rf"(?P<street2>[^上下東西\s\d]+)?"
    rf"(?P<direction>{_DIR_TOKENS})"
)


class KyotoParser:
    """Parses Kyoto City street-intersection directional clauses."""

    @staticmethod
    def parse(text: str) -> Tuple[Optional[KyotoDirectionClause], str]:
        """Detects and extracts Kyoto intersection direction clauses from text.

        Args:
            text: Address string starting after the Ward (e.g., '寺町通御池上る上本能寺前町488番地').

        Returns:
            Tuple of (KyotoDirectionClause or None, remaining_address_text).
        """
        match = _KYOTO_INTERSECTION_PATTERN.search(text)
        if not match:
            return None, text

        start, end = match.span()
        # Only treat as intersection clause if it occurs near the start of the post-ward text
        if start > 5:
            return None, text

        s1 = match.group("street1") or ""
        s2 = match.group("street2") or ""
        dir_token = match.group("direction")
        cardinal = KYOTO_DIRECTIONS.get(dir_token, "unknown")
        raw_clause = text[start:end]

        clause = KyotoDirectionClause(
            street_1=s1,
            street_2=s2,
            direction=dir_token,
            cardinal=cardinal,
            raw_clause=raw_clause,
        )

        remaining = (text[:start] + text[end:]).strip()
        return clause, remaining
