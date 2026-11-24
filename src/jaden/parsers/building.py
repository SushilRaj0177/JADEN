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
    r"(?P<floor>(?:B\d+|(?:\d+[・、~〜])*\d+|地下\d+|地下[一二三四五六七八九十]+|[一二三四五六七八九十]+(?=階))[\s]*(?:階|[Ff](?![a-z])))",
)
_KANJI_DIGIT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}

# A room on its own: a bare number ('… 1', '… 302'), a lettered room ('A-302', '302A', 'B101'), or a
# wing and room ('2-302')
_ROOM_ALONE: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:\d{1,5}|[A-Za-z]-?\d{1,4}|\d{1,4}-?(?![Ff]$)[A-Za-z]|\d{1,2}-\d{1,4})(?:\s*(?:号室|室))?|[A-Za-z]\s*(?:号室|室))$")   # '3B', 'B-3', '10-1', 'B室'
# A basement level written alone after the building name: 'サカエチカ B1'
_BASEMENT_TOKEN: Final[re.Pattern[str]] = re.compile(r"(?:^|\s)(?P<floor>B\d{1,2})(?=\s|$)")

# Room / Unit patterns: e.g. '301号室', '502号', '101号室'
_ROOM_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?P<room>\d{1,4}(?:-\d{1,4})+[\s]*(?:号室|ごうしつ|室)|(?:(?<![A-Za-z])[A-Za-z]-?)?\d+[A-Za-z]?[\s]*(?:号室|ごうしつ|室)|\d+[\s]*号(?!棟|館|地)"
    r"|(?:^|\s)\d{3,4}(?:\s|$))"
)
# A room numbered in two parts: '207-1号室'
_SPLIT_ROOM: Final[re.Pattern[str]] = re.compile(r"^(?P<room>\d{1,4}(?:-\d{1,4})+[A-Za-z]?)\s*(?:号室|ごうしつ|室)$")
# A wing then a room, with no building name: 'A-201号室', '1-201号室' ('B棟305' keeps B棟 as the building)
_WING_THEN_ROOM: Final[re.Pattern[str]] = re.compile(
    r"^(?P<wing>[A-Za-z]|\d{1,2})\s*(?P<sep>-)\s*(?P<room>\d{2,4})\s*(?:号室|ごうしつ|室|号)?$")

# English unit labels: '#302', 'Apt 302', 'Apt. 302', 'Room 302', 'Rm 302', 'Unit 302'
_LABELLED_ROOM: Final[re.Pattern[str]] = re.compile(
    r"(?:^|\s)(?:#|(?:apt|apartment|room|rm|unit)\.?\s*#?)\s*(?P<room>\d+[A-Za-z]?)(?=\s|$)", re.IGNORECASE
)

# A room number glued to the end of a building name: 'グランドメゾン芝公園302', 'コーポ田中-101'
_TRAILING_ROOM: Final[re.Pattern[str]] = re.compile(
    r"^(?P<name>.*[^\d\s\-#])(?:\s*-\s*)?(?P<room>\d{3,4})$"
)


# A short unit set apart after the name: 'メゾン芝 4A', 'コーポ田中 B-3', 'ハイツ 10-1' (a lone '2' stays in the name)
_SHORT_UNIT_AFTER_NAME: Final[re.Pattern[str]] = re.compile(
    r"^(?P<name>.*\S)\s+(?P<room>\d{1,4}[A-Za-z]|[A-Za-z]-?\d{1,4}|\d{1,2}-\d{1,4})$")


# A wing number and room glued to the name: 'コーポ1-201', 'ハイツ山田 2-101' (wing 1, room 201)
_TRAILING_WING_ROOM: Final[re.Pattern[str]] = re.compile(
    r"^(?P<name>.*[^\d\s\-#])\s*(?P<room>\d{1,2}\s*-\s*\d{2,4})$"
)


# What a building name looks like, so '番割31-11' or '町目3-10' (a 字 or a misspelt 丁目 before a lot
# number) is not read as wing and room: two letters of katakana or Latin (ケ and ノ also appear in place
# names), or a word for a building
def _looks_like_building(name: str) -> bool:
    letters = [c for c in name if ("ァ" <= c <= "ヺ" or c == "ー" or c.isascii() and c.isalpha()) and c not in "ケヶノ"]
    return len(letters) >= 2 or re.search(r"団地|ビル|荘|館|寮|住宅|棟|宿舎|社宅|会館", name) is not None


def _room_alone(text: str) -> str:
    """'B室' -> 'B', '10-1号室' -> '10-1'; a plain '101号室' keeps its mark."""
    return re.sub(r"\s*(?:号室|室)$", "", text) if re.search(r"[A-Za-z-]", text) else text


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

        # The same building text written twice ('アースビルディング 303 アースビルディング 303'): one copy
        words = working.split()
        if len(words) >= 2 and len(words) % 2 == 0 and words[:len(words) // 2] == words[len(words) // 2:]:
            working = " ".join(words[:len(words) // 2])

        # A mark left over with no number of its own ('4-2-8号', '12番地') is no building
        if re.fullmatch(r"(?:号室?|番地?|階|地)", working):
            return None, None, None

        # 0. A room on its own: '4-2-8-101', '… 1', 'A-302', '2-302'; or a wing and room ('A-201号室')
        if _ROOM_ALONE.match(working):
            return None, None, _room_alone(working)
        wing_room = _WING_THEN_ROOM.match(working)
        if wing_room:
            return None, None, f"{wing_room.group('wing').upper()}-{wing_room.group('room')}"
        split_room = _SPLIT_ROOM.match(working)
        if split_room:
            return None, None, split_room.group("room")

        # 1. Extract Floor if present. Two floors ('2階・3階') stay in the building text: neither is the address's
        floor_range = re.match(r"^(\d{1,2})-(\d{1,2})\s*(階|[Ff](?![A-Za-z]))(?=\s|$)", working)
        if floor_range and int(floor_range.group(1)) < int(floor_range.group(2)):
            # '1-2階' on its own (written '1・2階') is floors 1 and 2
            working = f"{floor_range.group(1)}・{floor_range.group(2)}{floor_range.group(3)}{working[floor_range.end():]}"
        floors = list(_FLOOR_PATTERN.finditer(working))
        floor_match = (floors[0] if len(floors) == 1 else None) or (None if floors else _BASEMENT_TOKEN.search(working))
        if floor_match:
            floor = re.sub(r"(?<=\d)[、\-](?=\d)", "・", floor_match.group("floor").strip())   # '1-2階' is 1・2階
            kanji = re.match(r"(地下)?([一二三四五六七八九十]+)", floor)
            if kanji:
                digits = kanji.group(2)
                n = (_KANJI_DIGIT.get(digits[0], 1) * 10 + _KANJI_DIGIT.get(digits[2:3], 0) if "十" in digits[1:2]
                     else 10 + _KANJI_DIGIT.get(digits[1:2], 0) if digits.startswith("十") else _KANJI_DIGIT.get(digits, 0))
                floor = f"{kanji.group(1) or ''}{n}{floor[kanji.end():]}"
            working = (working[:floor_match.start()] + " " + working[floor_match.end():]).strip()
            rest = working.lstrip("-,、，・ ").strip()
            if _ROOM_ALONE.match(rest):
                return None, floor, _room_alone(rest)   # '3F-301': floor 3, room 301; '3F B室'
            working = working.rstrip("-,、，・ ")   # 'Via701-3階' reads like 'Via701 3階'

        # 2. Extract Room/Unit if present. Two rooms ('101号室、102号室', '411号・509号') are kept together as
        # written: neither alone is the address's room
        marks = re.findall(r"(\d+[A-Za-z]?)\s*(号室|号(?!棟|館|地))", working)
        if len({n for n, _ in marks}) >= 2:
            together = re.sub(r"\s+", " ", working).strip(" -,、") or None
            return together, floor, None
        if len(marks) >= 2:
            # The same room written twice ('メゾン花池101号メゾン花池101号室'): one room, each copy taken out
            number = marks[0][0]
            rest = re.sub(rf"(?<!\d){re.escape(number)}\s*(?:号室|号(?!棟|館|地))", " ", working)
            together = re.sub(r"\s+", " ", rest).strip(" -,、・") or None
            return together, floor, f"{number}{marks[0][1]}"
        labelled = _LABELLED_ROOM.search(working)
        room_match = _ROOM_PATTERN.search(working)
        trailing = _TRAILING_ROOM.match(working)
        wing_room = _TRAILING_WING_ROOM.match(working)
        short_unit = _SHORT_UNIT_AFTER_NAME.match(working)
        if labelled:
            unit = labelled.group("room")
            working = (working[:labelled.start()] + " " + working[labelled.end():]).strip()
        elif room_match:
            unit = room_match.group("room").strip()
            working = (working[:room_match.start()] + " " + working[room_match.end():]).strip()
        elif wing_room and len(wing_room.group("name").strip()) >= 2 and _looks_like_building(wing_room.group("name")):
            unit = re.sub(r"\s+", "", wing_room.group("room"))
            working = wing_room.group("name").strip()
            if working.endswith("第"):
                # 'ライオンズマンション第2-305': 第2 is the building's number, 305 the room
                number, _, unit = unit.partition("-")
                working += number
        elif trailing and len(trailing.group("name").strip()) >= 2:
            unit = trailing.group("room")
            working = trailing.group("name").strip()
        elif short_unit and len(short_unit.group("name").strip()) >= 2:
            unit = short_unit.group("room")          # 'メゾン芝 4A', 'コーポ田中 B-3', 'ハイツ 10-1'
            working = short_unit.group("name").strip()

        # 3. Clean remaining text as building name
        building: Optional[str] = re.sub(r"\s+", " ", working).strip(" -,、")
        if not building:
            building = None

        return building, floor, unit
