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
    r"^(?:〒\s*(?:\d{3}[-ー]?\d{4}|\d{7})?|\d{3}[-ー]\d{4})\s*"
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

    # Step 2: Strip leading Japanese postal code prefix if present
    text = _POSTAL_CODE_PREFIX.sub("", text)

    # Step 3: Contextual Chōonpu (ー) resolution before unconditional dash pass
    # Replace 'ー' with '-' only when connecting numbers (e.g. 1ー2 -> 1-2)
    # Loop to handle chained dashes like 1ー2ー3
    prev = None
    while prev != text:
        prev = text
        text = _CONTEXTUAL_CHOONPU_PATTERN.sub(r"\1-\2", text)

    # Step 4: Unconditional dash normalization
    text = _UNCONDITIONAL_DASH_PATTERN.sub("-", text)

    # Step 5: Collapse consecutive hyphens (e.g. '--' -> '-')
    text = re.sub(r"-+", "-", text)

    # Step 6: Whitespace normalization (including embedded newlines and carriage returns)
    text = _WHITESPACE_PATTERN.sub(" ", text)

    return text.strip()
