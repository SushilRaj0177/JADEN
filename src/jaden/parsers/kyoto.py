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

# Major historical Kyoto thoroughfares that can appear without explicit '通'
_KYOTO_MAJOR_STREETS = [
    "烏丸", "御池", "四条", "河原町", "堀川", "丸太町", "五条", "三条", "七条", "八条", "九条", "十条",
    "寺町", "新町", "室町", "東洞院", "西洞院", "大宮", "千本", "西大路", "東大路", "北大路",
    "油小路", "木屋町", "先斗町", "川端", "白川", "今出川", "鞍馬口", "紫竹", "下立売", "上立売",
    "上長者町", "下長者町", "中立売", "二条", "六角", "蛸薬師", "錦小路", "綾小路", "仏光寺", "高辻", "松原"
]
_STREETS_PATTERN = "|".join(sorted(_KYOTO_MAJOR_STREETS, key=len, reverse=True))

# Pattern 1: Street 1 has explicit '通' or '筋' (supports cardinal streets like 東洞院通, 下立売通)
_KYOTO_INTERSECTION_P1: Final[re.Pattern[str]] = re.compile(
    rf"(?:^|\s)(?P<street1>[^\s\d]+?[通筋])(?P<street2>[^\s\d]+?)(?P<direction>{_DIR_TOKENS})"
)

# Pattern 2: Street 1 is a known major street without explicit '通' (e.g. 烏丸御池上る, 四条河原町東入)
_KYOTO_INTERSECTION_P2: Final[re.Pattern[str]] = re.compile(
    rf"(?:^|\s)(?P<street1>{_STREETS_PATTERN})(?P<street2>[^\s\d]+?)(?P<direction>{_DIR_TOKENS})"
)


class KyotoParser:
    """Parses Kyoto City street-intersection directional clauses."""

    @staticmethod
    def parse(text: str) -> Tuple[Optional[KyotoDirectionClause], str]:
        """Detects and extracts Kyoto intersection direction clauses from text.

        Correctly handles thoroughfares containing cardinal characters
        (e.g., '東洞院通', '西洞院通', '下立売通', '上長者町通').

        Args:
            text: Address string starting after the Ward (e.g., '御池通東洞院東入笹屋町436').

        Returns:
            Tuple of (KyotoDirectionClause or None, remaining_address_text).
        """
        match = _KYOTO_INTERSECTION_P1.search(text)
        if not match:
            match = _KYOTO_INTERSECTION_P2.search(text)

        if not match:
            return None, text

        start, end = match.span()
        # Only treat as intersection clause if it occurs near the start of the post-ward text
        if start > 5:
            return None, text

        s1 = match.group("street1").strip()
        s2 = match.group("street2").strip()
        dir_token = match.group("direction").strip()
        cardinal = KYOTO_DIRECTIONS.get(dir_token, "unknown")
        raw_clause = text[start:end].strip()

        clause = KyotoDirectionClause(
            street_1=s1,
            street_2=s2,
            direction=dir_token,
            cardinal=cardinal,
            raw_clause=raw_clause,
        )

        remaining = (text[:start] + text[end:]).strip()
        return clause, remaining
