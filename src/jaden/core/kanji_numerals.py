"""JADEN: Disambiguated Kanji-Arabic numeral converter.

Supports:
- Positional multiplier syntax (e.g., '四百八十八' -> 488, '二十三' -> 23, '十二' -> 12)
- Direct digit sequence syntax (e.g., '一二三' -> 123)
- Legal Daiji variants (壱=1, 弐=2, 参=3, 拾=10)
- Context-bounded transformations (strictly isolated from proper nouns like 六本木, 八王子, 十条)
"""

import re
from typing import Optional, Final

from .constants import KANJI_DIGITS, KANJI_POWERS

# All recognized Kanji numeric characters
_KANJI_NUM_CHARS: Final[str] = "".join(list(KANJI_DIGITS.keys()) + list(KANJI_POWERS.keys()))
_KANJI_NUM_REGEX: Final[re.Pattern[str]] = re.compile(f"^[{_KANJI_NUM_CHARS}]+$")


def parse_kanji_number(token: str) -> Optional[int]:
    """Parses a purely Kanji numeric token into an integer.

    Handles both:
    1. Multiplier positional notation: '四百八十八' -> 488, '二十五' -> 25, '十' -> 10, '百' -> 100
    2. Direct digit string notation: '一二三' -> 123, '〇' -> 0

    Args:
        token: String containing ONLY Kanji numerals (e.g. '四十二', '壱').

    Returns:
        Integer value if successfully parsed, None otherwise.
    """
    if not token or not _KANJI_NUM_REGEX.match(token):
        return None

    # Check if string contains multiplier units (十, 百, 千, 拾)
    has_multiplier = any(unit in token for unit in KANJI_POWERS)

    if not has_multiplier:
        # Direct digit sequence: e.g. '一二三' -> 123
        res = 0
        for ch in token:
            if ch in KANJI_DIGITS:
                res = res * 10 + KANJI_DIGITS[ch]
            else:
                return None
        return res

    # Multiplier notation: parse thousands, hundreds, tens
    total = 0
    current_digit = 0

    i = 0
    while i < len(token):
        ch = token[i]
        if ch in KANJI_DIGITS:
            current_digit = KANJI_DIGITS[ch]
        elif ch in KANJI_POWERS:
            multiplier = KANJI_POWERS[ch]
            if current_digit == 0:
                # E.g. '十' (10) or '百' (100) where leading 1 is omitted
                current_digit = 1
            total += current_digit * multiplier
            current_digit = 0
        else:
            return None
        i += 1

    total += current_digit
    return total


# Pattern matching Chome clause with Kanji numerals: e.g. '三丁目' or '四十二丁目'
_CHOME_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"([{_KANJI_NUM_CHARS}]+)丁目"
)

# Pattern matching Banchi/Ban clause with Kanji numerals: e.g. '四百八十八番地' or '五番'
# Uses negative lookahead (?!町|丁) to protect proper town names like '三番町' or '一番町'
_BAN_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"([{_KANJI_NUM_CHARS}]+)(番地|番(?!町|丁)|号)"
)


def normalize_kanji_numerals_in_blocks(text: str) -> str:
    """Normalizes Kanji numerals strictly within block/lot/chome contexts.

    Leaves proper nouns untouched (e.g. '港区六本木三丁目' -> '港区六本木3丁目').
    """
    # Replace Chome
    def replace_chome(match: re.Match[str]) -> str:
        k_num = match.group(1)
        val = parse_kanji_number(k_num)
        return f"{val}丁目" if val is not None else match.group(0)

    # Replace Ban / Banchi / Go
    def replace_ban(match: re.Match[str]) -> str:
        k_num = match.group(1)
        suffix = match.group(2)
        val = parse_kanji_number(k_num)
        return f"{val}{suffix}" if val is not None else match.group(0)

    text = _CHOME_KANJI_PATTERN.sub(replace_chome, text)
    text = _BAN_KANJI_PATTERN.sub(replace_ban, text)
    return text
