"""JADEN: Building name, floor, and room unit parser.

Isolates secondary unit identifiers (階数, 部屋番号) from commercial/residential
building names (e.g., '六本木ヒルズ森タワー 50F', 'ハイツ田中 201号室').
"""

import re
from typing import Optional, Tuple, Final

# Floor patterns: e.g. '50F', '50階', 'B1F', '地下1階', '3f'
# In Japanese, CJK characters (e.g. 'タワー') are \w, so \b before digits fails.
_FLOOR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<floor>(?:B\d+|\d+|地下\d+)[\s]*(?:階|[Ff]))(?:\s|$|[A-Za-z0-9])?",
)

# Room / Unit patterns: e.g. '301号室', '502号', '101号室'
_ROOM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<room>\d+[\s]*(?:号室|号)|(?:^|\s)\d{3,4}(?:\s|$))"
)


class BuildingParser:
    """Parses building name, floor, and unit numbers from tail strings."""

    @staticmethod
    def parse(tail: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extracts (building_name, floor, unit) from address tail.

        Args:
            tail: Unparsed tail string following the block numbers.

        Returns:
            Tuple of (building_name, floor, unit).
        """
        if not tail:
            return None, None, None

        working = tail.strip()
        floor: Optional[str] = None
        unit: Optional[str] = None

        # 1. Extract Floor if present
        floor_match = _FLOOR_PATTERN.search(working)
        if floor_match:
            floor = floor_match.group("floor").strip()
            working = (working[:floor_match.start()] + " " + working[floor_match.end():]).strip()

        # 2. Extract Room/Unit if present
        room_match = _ROOM_PATTERN.search(working)
        if room_match:
            unit = room_match.group("room").strip()
            working = (working[:room_match.start()] + " " + working[room_match.end():]).strip()

        # 3. Clean remaining text as building name
        building = re.sub(r"\s+", " ", working).strip()
        if not building:
            building = None

        return building, floor, unit
