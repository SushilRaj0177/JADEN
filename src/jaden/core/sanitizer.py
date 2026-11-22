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

# Leading postal code: '〒105-0011', '〒 105 - 0011', '郵便番号:1050011', a bare '105-0011', or a bare
# '1050011' followed by a space (a seven-digit number glued to the address is a lot number, not a code)
_POSTAL_CODE_PREFIX: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:〒|郵便番号|郵便)\s*[:：]?\s*(?:\d{3}\s*[-ー]?\s*\d{4}(?!\d))?|\d{3}\s?[-ー]\s?\d{4}(?!\d)|\d{7}(?=\s))\s*"
)

# Characters that carry nothing: zero-width spaces and joiners, soft hyphens, direction marks, BOM (format
# characters, Cf) and control characters (Cc). Line and paragraph separators become spaces.
_INVISIBLE: Final[re.Pattern[str]] = re.compile(r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
                                                r"\u00ad\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]")
_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[\u2028\u2029\u0085]")

# '4丁目-2-8', '4丁目ー2ー8', '4丁目の2の8': the mark between 丁目 and the block is not part of either
_AFTER_CHOME: Final[re.Pattern[str]] = re.compile(r"(\d丁目)\s*[-の]\s*(?=\d)")
_NO_AFTER_CHOME: Final[re.Pattern[str]] = re.compile(r"(\d丁目\d+)の(\d+)")
# '10の1番地', '887-2番地': lot 10, branch 1 (written as 10番地の1); after 丁目, '4丁目2-8番地' is 2番8号
_NO_BEFORE_BANCHI: Final[re.Pattern[str]] = re.compile(r"(?<![\d-])(\d+)[の-](\d+)番地(?!の|\d|-)")
_BANCHI_AFTER_CHOME_PAIR: Final[re.Pattern[str]] = re.compile(r"(\d丁目\d+-\d+)番地(?!の|\d|-)")
# '4 - 2 - 8': spaces around a hyphen between numbers
_SPACED_HYPHEN: Final[re.Pattern[str]] = re.compile(r"(?<=\d)\s*-\s*(?=\d)")
# A phone or fax number after the address: 'TEL 03-1234-5678', '電話：03(1234)5678'
_TRAILING_PHONE: Final[re.Pattern[str]] = re.compile(
    r"\s*[(（]?\s*(?:TEL|Tel|tel|FAX|Fax|fax|電話番号|電話|℡|ＴＥＬ)\s*[.:：]?\s*[\d\s()（）+-]{6,}[)）]?\s*$")


def clean_characters(raw_text: str) -> str:
    """NFKC, no invisible or control characters, and one hyphen for every dash: the first step of every
    reading of an address (the parser, the postal-code reader, extraction), so they all see the same text."""
    text = unicodedata.normalize("NFKC", raw_text or "")
    text = _INVISIBLE.sub("", text)
    text = _SEPARATORS.sub(" ", text)
    return _UNCONDITIONAL_DASH_PATTERN.sub("-", text)

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

_CHOONPU_AFTER_MARKER: Final[re.Pattern[str]] = re.compile(r"(?:(?<=番地)|(?<=丁目)|(?<=番)|(?<=号))ー+(?=\d)")

# '1,111' with exactly three digits after the comma and no digit around it
_THOUSANDS: Final[re.Pattern[str]] = re.compile(r"(?<![\d,.-])(\d{1,2}),(\d{3})(?![\d,])")

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

    # Step 1: NFKC (full-width digits -> 123), invisible characters removed, every dash a hyphen
    text = clean_characters(raw_text).strip(" \t\r\n")

    # Step 2: Contextual Chōonpu (ー) resolution before unconditional dash pass
    # Replace 'ー' with '-' only when connecting numbers (e.g. 1ー2 -> 1-2)
    # Loop to handle chained dashes like 1ー2ー3
    prev = None
    while prev != text:
        prev = text
        text = _CONTEXTUAL_CHOONPU_PATTERN.sub(r"\1-\2", text)

    # 'ー' between a block marker and a number is a hyphen too ('421番地ー1')
    text = _CHOONPU_AFTER_MARKER.sub("-", text)

    # Step 4: Collapse consecutive hyphens (e.g. '--' -> '-')
    text = re.sub(r"-+", "-", text)

    # Number forms around 丁目 and 番地 that the block parser reads in their usual spelling
    text = _SPACED_HYPHEN.sub("-", text)
    text = _AFTER_CHOME.sub(r"\1", text)
    prev = None
    while prev != text:
        prev = text
        text = _NO_AFTER_CHOME.sub(r"\1-\2", text)
    text = _BANCHI_AFTER_CHOME_PAIR.sub(r"\1", text)
    text = _NO_BEFORE_BANCHI.sub(r"\1番地の\2", text)

    # A phone or fax number after the address is not part of it
    text = _TRAILING_PHONE.sub("", text)

    # A lot number typed with a thousands separator ('氷川1,111' is lot 1111)
    text = _THOUSANDS.sub(r"\1\2", text)

    # Step 5: Strip leading labels, country name and postal code (in any order)
    prev = None
    while prev != text:
        prev = text
        text = _LEADING_LABEL.sub("", text.lstrip())
        text = _POSTAL_CODE_PREFIX.sub("", text)

    # Step 6: Whitespace normalization (including embedded newlines and carriage returns)
    text = _WHITESPACE_PATTERN.sub(" ", text)

    return text.strip()
