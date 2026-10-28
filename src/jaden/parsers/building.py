"""JADEN: Building name, floor, and room unit parser.

Isolates secondary unit identifiers (階数, 部屋番号) from commercial/residential
building names (e.g., '六本木ヒルズ森タワー 50F', 'ハイツ田中 201号室').

Real-world tails seen on forms and shipping labels:
    '-101'                   room written as a fourth block number ('4-2-8-101')
    '-5F'                    floor written the same way
    'グランドメゾン芝公園302'   room number glued to the building name
    'B棟305号室', '#302', 'Apt 302', 'Room 1205'
    '3F', '3階', 'B1F', '地下1階'
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

# English unit labels: '#302', 'Apt 302', 'Apt. 302', 'Room 302', 'Rm 302', 'Unit 302'
_LABELLED_ROOM: Final[re.Pattern[str]] = re.compile(
    r"(?:^|\s)(?:#|(?:apt|apartment|room|rm|unit)\.?\s*#?)\s*(?P<room>\d+[A-Za-z]?)(?=\s|$)", re.IGNORECASE
)

# A room number glued to the end of a building name: 'グランドメゾン芝公園302', 'コーポ田中-101'
_TRAILING_ROOM: Final[re.Pattern[str]] = re.compile(
    r"^(?P<name>.*[^\d\s\-#])(?:\s*-\s*)?(?P<room>\d{3,4})$"
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

        # Separators left over from the block numbers ('-101', ', ハイツ田中')
        working = tail.strip().lstrip("-,、，・ ").strip()
        floor: Optional[str] = None
        unit: Optional[str] = None

        # 0. A bare number joined to the block numbers by a hyphen is a room ('4-2-8-101')
        if tail.strip().startswith("-") and working.isdigit():
            return None, None, working

        # 1. Extract Floor if present
        floor_match = _FLOOR_PATTERN.search(working)
        if floor_match:
            floor = floor_match.group("floor").strip()
            working = (working[:floor_match.start()] + " " + working[floor_match.end():]).strip()

        # 2. Extract Room/Unit if present
        labelled = _LABELLED_ROOM.search(working)
        room_match = _ROOM_PATTERN.search(working)
        trailing = _TRAILING_ROOM.match(working)
        if labelled:
            unit = labelled.group("room")
            working = (working[:labelled.start()] + " " + working[labelled.end():]).strip()
        elif room_match:
            unit = room_match.group("room").strip()
            working = (working[:room_match.start()] + " " + working[room_match.end():]).strip()
        elif trailing and len(trailing.group("name").strip()) >= 2:
            unit = trailing.group("room")
            working = trailing.group("name").strip()

        # 3. Clean remaining text as building name
        building: Optional[str] = re.sub(r"\s+", " ", working).strip(" -,、")
        if not building:
            building = None

        return building, floor, unit
