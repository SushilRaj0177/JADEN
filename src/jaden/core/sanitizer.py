"""JADEN: Context-aware Japanese text sanitizer & Unicode homogenizer.

Applies:
- Unicode NFKC normalization (UAX #15)
- CJK whitespace collapse (U+3000, U+00A0, tabs -> ASCII space)
- Unconditional dash normalization (U+FF0D, U+2010..U+2015, U+2212, U+FF5E, U+301C -> '-')
- Context-aware Chōonpu handling (U+30FC): converted to '-' only between numeric/block
  tokens (e.g., '1ー2ー3' -> '1-2-3'), strictly preserved in Katakana loanwords (e.g., 'タワー').
"""

import re
import unicodedata
from typing import Final

from .constants import UNCONDITIONAL_DASH_CHARS

# Regex matching unconditional dashes
_UNCONDITIONAL_DASH_PATTERN: Final[re.Pattern[str]] = re.compile(
    "[" + re.escape("".join(UNCONDITIONAL_DASH_CHARS)) + "]"
)

# Regex matching contextual Chōonpu (ー / U+30FC) when functioning as a delimiter between digits/Kanji numerals
# Preceded by digit/Kanji numeral, followed by digit/Kanji numeral
_CONTEXTUAL_CHOONPU_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"([\d〇一二三四五六七八九十壱弐参拾]+)ー+([\d〇一二三四五六七八九十壱弐参拾]+)"
)

# Regex matching leading Japanese postal code prefix (〒NNN-NNNN, 〒NNNNNNN, 〒, NNN-NNNN)
_POSTAL_CODE_PREFIX: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:〒|郵便番号|郵便)\s*[:：]?\s*(?:\d{3}[-ー]?\d{4}|\d{7})?|\d{3}[-ー]\d{4})\s*"
)

_PREFECTURES: Final[str] = (
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
    "新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|"
    "奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|"
    "熊本県|大分県|宮崎県|鹿児島県|沖縄県"
)

# Form labels and a leading country name: '住所：', 'お届け先 ', '日本、', 'Japan '.
# '日本' is removed only before a separator, a postal code or a prefecture, never from '日本橋'.
_LEADING_LABEL: Final[re.Pattern[str]] = re.compile(
    rf"^(?:(?:ご?住所|所在地|お届け先|送付先|配送先|送り先)\s*[:：]?|"
    rf"(?:日本国?|JAPAN|Japan)(?=[\s,、。]|〒|郵便|{_PREFECTURES}))[\s,、。]*"
)

# Whitespace cleaner: collapses Japanese full-width space (U+3000), NBSP, tabs, newlines, CRs, multiple spaces
_WHITESPACE_PATTERN: Final[re.Pattern[str]] = re.compile(r"[\u0020\u3000\u00A0\t\r\n]+")


def sanitize_address_text(raw_text: str) -> str:
    """Sanitizes raw Japanese address text into canonical homogenized form.

    Args:
        raw_text: Raw address string input by user or extracted from forms.

    Returns:
        Sanitized string with normalized digits, unified hyphens, and preserved proper nouns.
    """
    if not raw_text:
        return ""

    # Strip Unicode BOM (U+FEFF) and surrounding whitespace
    text = raw_text.strip("\ufeff \t\r\n")

    # Step 1: Unicode NFKC Normalization (converts full-width numbers １２３ -> 123, etc.)
    text = unicodedata.normalize("NFKC", text)

    # Step 2: Contextual Chōonpu (ー) resolution before unconditional dash pass
    # Replace 'ー' with '-' only when connecting numbers (e.g. 1ー2 -> 1-2)
    # Loop to handle chained dashes like 1ー2ー3
    prev = None
    while prev != text:
        prev = text
        text = _CONTEXTUAL_CHOONPU_PATTERN.sub(r"\1-\2", text)

    # Step 3: Unconditional dash normalization
    text = _UNCONDITIONAL_DASH_PATTERN.sub("-", text)

    # Step 4: Collapse consecutive hyphens (e.g. '--' -> '-')
    text = re.sub(r"-+", "-", text)

    # Step 5: Strip leading labels, country name and postal code (in any order)
    prev = None
    while prev != text:
        prev = text
        text = _LEADING_LABEL.sub("", text.lstrip())
        text = _POSTAL_CODE_PREFIX.sub("", text)

    # Step 6: Whitespace normalization (including embedded newlines and carriage returns)
    text = _WHITESPACE_PATTERN.sub(" ", text)

    return text.strip()
