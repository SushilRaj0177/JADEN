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

_PREFECTURE_NAMES: Final[str] = (
    "北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|"
    "新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|"
    "奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|"
    "熊本県|大分県|宮崎県|鹿児島県|沖縄県"
)
# Leading postal code: '〒105-0011', '〒 105 - 0011', '郵便番号:1050011', a bare '105-0011', a bare
# '1050011' followed by a space or glued to a prefecture name ('1050011東京都'); otherwise a seven-digit
# number glued to the address is a lot number, not a code
_POSTAL_CODE_PREFIX: Final[re.Pattern[str]] = re.compile(
    r"^(?:(?:〒|郵便番号|郵便)\s*[:：]?\s*(?:\d{3}\s*[-ー]?\s*\d{4}(?!\d))?|\d{3}\s?[-ー]\s?\d{4}(?!\d)|\d{7}(?=\s)"
    rf"|\d{{7}}(?={_PREFECTURE_NAMES}))\s*"
)

# Characters that carry nothing: zero-width spaces and joiners, soft hyphens, direction marks, BOM (format
# characters, Cf) and control characters (Cc). Line and paragraph separators become spaces.
# Also lone surrogates and U+FFFD (what a decoder leaves for a broken character), variation selectors,
# the combining grapheme joiner, Arabic letter mark, Hangul fillers, the object replacement character and
# tag characters.
_INVISIBLE: Final[re.Pattern[str]] = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f\u00ad\u034f\u061c\u115f\u1160\u180b-\u180f"
    "\u200b-\u200f\u202a-\u202e\u2060-\u206f\u3164\ufe00-\ufe0f\ufeff\uffa0\ufff0-\ufffd\ud800-\udfff"
    "\U000e0000-\U000e007f\U000e0100-\U000e01ef]")
_SEPARATORS: Final[re.Pattern[str]] = re.compile(r"[\u2028\u2029\u0085]")

# '4丁目-2-8', '4丁目ー2ー8', '4丁目の2の8': the mark between 丁目 and the block is not part of either
_AFTER_CHOME: Final[re.Pattern[str]] = re.compile(r"(\d丁目)\s*[-の]\s*(?=\d)")
_NO_AFTER_CHOME: Final[re.Pattern[str]] = re.compile(r"(\d丁目\d+)の(\d+)")
# '10の1番地', '887-2番地': lot 10, branch 1 (written as 10番地の1); after 丁目, '4丁目2-8番地' is 2番8号
_NO_BEFORE_BANCHI: Final[re.Pattern[str]] = re.compile(r"(?<![\d-])(\d+)[の-](\d+)番地(?!の|\d|-)")
_BANCHI_AFTER_CHOME_PAIR: Final[re.Pattern[str]] = re.compile(r"(\d丁目\d+-\d+)番地(?!の|\d|-)")
# '4 - 2 - 8': spaces around a hyphen between numbers; '9・4' and '209の-1' are 9-4 and 209-1
_SPACED_HYPHEN: Final[re.Pattern[str]] = re.compile(r"(?<=\d)\s*(?:-|・|の-)\s*(?=\d)")
# Labels swapped after 丁目: '3号5番地', '35号1番', '18号36号' are block 3 house 5, 35-1, 18-36
_SWAPPED_AFTER_CHOME: Final[re.Pattern[str]] = re.compile(r"(\d丁目)(\d+)号(\d+)(?:番地|番|号)(?![\dの-])")
# A phone or fax number after the address: 'TEL 03-1234-5678', '電話：03(1234)5678'
_PHONE_LABEL: Final[str] = r"(?:TEL|Tel|tel|FAX|Fax|fax|電話番号|電話|℡|ＴＥＬ|携帯電話|携帯|ケータイ|Mobile|mobile)"
_TRAILING_PHONE: Final[re.Pattern[str]] = re.compile(
    rf"\s*[(（]?\s*{_PHONE_LABEL}(?:\s*[/／・&＆、]\s*{_PHONE_LABEL})*\s*[.:：]?\s*[\d\s()（）+-]{{6,}}[)）]?\s*$")
# A separator between numbers: '4-2、8', '2、85', '99-,5-19' are 4-2-8, 2-85, 99-5-19; after 番 or 丁目 it
# goes ('2番、8号'). (A thousands separator, '1,111', is read before this.)
_COMMA_BEFORE_ROOM: Final[re.Pattern[str]] = re.compile(r"(?<=\d)\s*[、，,]\s*(?=\d+\s*(?:号室|室|階|[Ff](?![a-z])))")
_COMMA_BETWEEN_NUMBERS: Final[re.Pattern[str]] = re.compile(r"(?<=\d)-?\s*[、，,]\s*-?(?=\d)")
# '516-1-2階', '745-1-1F', '1303-2-21号室': after a lot number too large to be a 丁目 (no 丁目 is above 84)
# and its branch, a number glued to a floor or room mark is the floor or room, not a third block number.
# ('具志2-4-13階' is different: 2丁目4番1号 3階, which the block parser reads.)
_FLOOR_AFTER_PAIR: Final[re.Pattern[str]] = re.compile(
    r"(?<![\d-])((?:9[1-9]|[1-9]\d{2,})-\d+)-(?=\d+(?:階|[Ff](?![a-z])|号室|室))")
_COMMA_AFTER_MARKER: Final[re.Pattern[str]] = re.compile(r"(?<=[番目])\s*[、，,]\s*(?=\d)")
# '10之1番地', '10ノ1番地', '732番地之6': the old spellings of の between lot numbers
_OLD_NO: Final[re.Pattern[str]] = re.compile(r"(?<=\d)[之ノ](?=\d)|(?<=\d番地)[之ノ](?=\d)")
# '4695番ノ1ノ1': a lot written 番 then の (番地の)
_BAN_NO: Final[re.Pattern[str]] = re.compile(r"(?<=\d)番[之ノの](?=\d+(?![\d]*号))")
# The municipality written twice around a prefecture suffix (広島市県広島市安佐南区, a slip for 広島県広島市)
_REPEATED_MUNICIPALITY: Final[re.Pattern[str]] = re.compile(r"([^\d\s]{1,6}?[市区町村郡])[都道府県]\1")


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
    text = _SWAPPED_AFTER_CHOME.sub(r"\1\2番\3号", text)
    prev = None
    while prev != text:
        prev = text
        text = _NO_AFTER_CHOME.sub(r"\1-\2", text)
    text = _BANCHI_AFTER_CHOME_PAIR.sub(r"\1", text)
    text = _NO_BEFORE_BANCHI.sub(r"\1番地の\2", text)

    # A phone or fax number after the address is not part of it
    text = _TRAILING_PHONE.sub("", text)

    # A lot number typed with a thousands separator ('氷川1,111' is lot 1111); any other comma between
    # numbers separates them
    text = _THOUSANDS.sub(r"\1\2", text)
    text = _COMMA_AFTER_MARKER.sub("", text)
    text = _COMMA_BEFORE_ROOM.sub(" ", text)
    text = _COMMA_BETWEEN_NUMBERS.sub("-", text)
    text = _FLOOR_AFTER_PAIR.sub(r"\1 ", text)
    text = _BAN_NO.sub("番地の", text)
    text = _OLD_NO.sub("の", text)
    text = _NO_BEFORE_BANCHI.sub(r"\1番地の\2", text)
    text = _REPEATED_MUNICIPALITY.sub(r"\1", text)

    # Step 5: Strip leading labels, country name and postal code (in any order)
    prev = None
    while prev != text:
        prev = text
        text = _LEADING_LABEL.sub("", text.lstrip())
        text = _POSTAL_CODE_PREFIX.sub("", text)

    # Step 6: Whitespace normalization (including embedded newlines and carriage returns)
    text = _WHITESPACE_PATTERN.sub(" ", text)

    return text.strip()
