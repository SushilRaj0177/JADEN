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


# Context-bounded patterns protecting proper nouns (一番街, 一番館, 三番町, 麻布十番)
_CHOME_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"([{_KANJI_NUM_CHARS}]+)丁目"
)
_BANCHI_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"([{_KANJI_NUM_CHARS}]+)番地"
)
_BAN_CHI_GO_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"([{_KANJI_NUM_CHARS}]+)番(地の|号)"
)
_BAN_AFTER_CHOME_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(\d+丁目)([{_KANJI_NUM_CHARS}]+)番(?!町|丁|街|館|割|組|場|屋|通|筋)"
)
_GO_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(番|\d+-)([{_KANJI_NUM_CHARS}]+)号"
)
_EDABAN_KANJI_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(番地の)([{_KANJI_NUM_CHARS}]+)"
)

# Hyphenated numbers containing Kanji numerals (e.g. '三-二-一' -> '3-2-1', '六本木三-二-一' -> '六本木3-2-1')
# Protects building names such as '第一-3ビル' and trailing building keywords
_NUM_OR_KANJI: Final[str] = rf"(?:\d+|[{_KANJI_NUM_CHARS}]+)"
_HYPHEN_KANJI_SEQ_PATTERN: Final[re.Pattern[str]] = re.compile(
    rf"(?<!第)({_NUM_OR_KANJI}(?:-{_NUM_OR_KANJI})+)(?!ビル|号館|館|マンション|アパート|ハイツ|レジデンス|タワー)"
)


def normalize_kanji_numerals_in_blocks(text: str) -> str:
    """Normalizes Kanji numerals strictly within block/lot/chome contexts.

    Leaves proper nouns untouched (e.g. '港区六本木三丁目' -> '港区六本木3丁目',
    '千代田区三番町1-2' -> '千代田区三番町1-2', '港区一番街1-1' -> '港区一番街1-1',
    '港区麻布十番1-1' -> '港区麻布十番1-1').
    """
    # 1. 丁目
    text = _CHOME_KANJI_PATTERN.sub(
        lambda m: f"{parse_kanji_number(m.group(1))}丁目" if parse_kanji_number(m.group(1)) is not None else m.group(0),
        text
    )
    # 2. 番地 (banchi)
    text = _BANCHI_KANJI_PATTERN.sub(
        lambda m: f"{parse_kanji_number(m.group(1))}番地" if parse_kanji_number(m.group(1)) is not None else m.group(0),
        text
    )
    # 3. 番地の / 番号 (ban followed by chi/go)
    text = _BAN_CHI_GO_PATTERN.sub(
        lambda m: f"{parse_kanji_number(m.group(1))}番{m.group(2)}" if parse_kanji_number(m.group(1)) is not None else m.group(0),
        text
    )
    # 4. 番 following 丁目 (e.g. 12丁目五番)
    text = _BAN_AFTER_CHOME_PATTERN.sub(
        lambda m: f"{m.group(1)}{parse_kanji_number(m.group(2))}番" if parse_kanji_number(m.group(2)) is not None else m.group(0),
        text
    )
    # 5. 号 (go following ban or hyphen)
    text = _GO_KANJI_PATTERN.sub(
        lambda m: f"{m.group(1)}{parse_kanji_number(m.group(2))}号" if parse_kanji_number(m.group(2)) is not None else m.group(0),
        text
    )
    # 6. 枝番 (edaban following 番地の)
    text = _EDABAN_KANJI_PATTERN.sub(
        lambda m: f"{m.group(1)}{parse_kanji_number(m.group(2))}" if parse_kanji_number(m.group(2)) is not None else m.group(0),
        text
    )

    # 7. Hyphenated numbers containing Kanji numerals (e.g. '三-二-一' -> '3-2-1')
    def _convert_hyphen_seq(m: re.Match[str]) -> str:
        seq = m.group(1)
        if not any(c in _KANJI_NUM_CHARS for c in seq):
            return seq
        parts = seq.split("-")
        converted = []
        for p in parts:
            if p.isdigit():
                converted.append(p)
            else:
                val = parse_kanji_number(p)
                if val is not None:
                    converted.append(str(val))
                else:
                    return seq
        return "-".join(converted)

    text = _HYPHEN_KANJI_SEQ_PATTERN.sub(_convert_hyphen_seq, text)

    return text
