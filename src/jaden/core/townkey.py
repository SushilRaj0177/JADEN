"""JADEN: Orthographic matching keys for town (町字) names.

The same town is routinely written several ways:

- small/large ke and the particle ga: 霞が関 / 霞ヶ関 / 霞ケ関 / 霞ヵ関
- the genitive no: 一の宮 / 一ノ宮
- kanji vs Arabic numerals: 北一条西 / 北1条西, 十条 / 10条
- traditional vs simplified kanji: 澤 / 沢, 濱 / 浜, 邊 / 辺
- an optional 大字 / 字 prefix in cadastral areas: 大字南長野 / 南長野
- the okurigana of 通り: 昭和通り / 昭和通

``town_key`` folds all of these into one comparison key. It is applied to both
the gazetteer and the user's input, so the folding only needs to be consistent,
not linguistically exact. Keys are never shown to users.
"""

import re
import unicodedata
from functools import lru_cache
from typing import Final, Dict, Optional, Tuple

from .constants import KANJI_DIGITS, KANJI_POWERS
from .kanji_numerals import parse_kanji_number

# Bump whenever town_key output changes; compiled data stores keys built with this version
TOWN_KEY_VERSION: Final[int] = 3

_KE_VARIANTS: Final[str] = "ヶケヵがガｹ"
_NO_VARIANTS: Final[str] = "のノ"

# Traditional / variant forms frequently found in registered town names and user input.
_ITAIJI: Final[Dict[str, str]] = {
    "澤": "沢", "濱": "浜", "邊": "辺", "邉": "辺", "齋": "斎", "齊": "斉",
    "嶋": "島", "嶌": "島", "萬": "万", "冨": "富", "櫻": "桜", "龍": "竜",
    "與": "与", "國": "国", "壽": "寿", "鹽": "塩", "瀧": "滝", "藏": "蔵",
    "廣": "広", "曾": "曽", "惠": "恵", "眞": "真", "淺": "浅", "條": "条",
    "會": "会", "舊": "旧", "槇": "槙", "髙": "高", "﨑": "崎",
    "籠": "篭", "實": "実", "繩": "縄", "驛": "駅", "缺": "欠", "峯": "峰",
    # Old and variant forms met in registered company addresses and typed input
    "臺": "台", "彌": "弥", "塲": "場", "麴": "麹", "栁": "柳", "渕": "淵", "濵": "浜",
    "德": "徳", "豐": "豊", "榮": "栄", "靜": "静", "寶": "宝", "鐵": "鉄", "圓": "円",
    "學": "学", "禮": "礼", "增": "増", "莊": "荘", "來": "来", "兒": "児", "黑": "黒",
    "橫": "横", "巖": "巌", "當": "当", "藝": "芸", "龜": "亀", "澁": "渋", "攝": "摂",
    "氣": "気", "穗": "穂", "鄕": "郷", "內": "内", "淸": "清", "靑": "青", "步": "歩",
    "狹": "狭", "敎": "教", "賴": "頼", "瀨": "瀬", "禪": "禅", "彈": "弾", "縣": "県",
    "聲": "声", "樂": "楽", "藥": "薬", "應": "応", "燈": "灯", "鷄": "鶏",
    "嶽": "岳", "檜": "桧", "礪": "砺", "蘆": "芦", "藪": "薮", "鷗": "鴎", "驒": "騨",
    "竈": "釜", "竃": "釜", "諌": "諫", "鯵": "鰺", "舘": "館", "埜": "野", "曻": "昇",
    "梼": "檮", "珎": "珍", "嵜": "崎",
    "碕": "崎", "舩": "船", "桒": "桑", "栢": "柏", "杦": "杉", "椙": "杉", "槗": "橋",
}

_KANJI_NUM_CHARS: Final[str] = "".join(list(KANJI_DIGITS) + list(KANJI_POWERS))
_KANJI_RUN: Final[re.Pattern[str]] = re.compile(f"[{_KANJI_NUM_CHARS}]+")
# One character in, one character out: text folded with this keeps its length and offsets,
# so a match found in the folded text can be cut out of the original
FOLD_SAME_LENGTH: Final[Dict[int, str]] = {
    **{ord(c): "ケ" for c in _KE_VARIANTS},
    **{ord(c): "ノ" for c in _NO_VARIANTS},
    **{ord(k): v for k, v in _ITAIJI.items() if k != v},
}
_TRANSLATION: Final[Dict[int, str]] = {
    **FOLD_SAME_LENGTH,
    ord(" "): None, ord("　"): None, ord("・"): None,  # type: ignore[dict-item]
}


def fold_same_length(text: str) -> str:
    """Folds ヶ/ケ/が, の/ノ and old kanji forms without changing the length of the text."""
    return text.translate(FOLD_SAME_LENGTH)

_CHOME_SUFFIX: Final[re.Pattern[str]] = re.compile(rf"^(?P<base>.+?)(?P<num>[{_KANJI_NUM_CHARS}]+|\d+)丁目$")


def _kanji_runs_to_digits(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        val = parse_kanji_number(m.group(0))
        return str(val) if val is not None else m.group(0)
    return _KANJI_RUN.sub(repl, text)


@lru_cache(maxsize=1 << 15)
def spelling_key(name: str) -> str:
    """Like ``town_key`` but keeps kanji numerals as written, for comparing spellings character by character
    ('千歳町' must stay three characters, not become '1000歳町')."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).translate(_TRANSLATION).replace("通り", "通")
    if s.startswith("大字"):
        s = s[2:]
    elif s.startswith("字") and len(s) > 2:
        s = s[1:]
    return s


def is_numeral(ch: str) -> bool:
    return ch.isdigit() or ch in _KANJI_NUM_CHARS


@lru_cache(maxsize=1 << 16)
def town_key(name: str, strip_aza: bool = True) -> str:
    """Folds a town name into its orthographic comparison key."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).translate(_TRANSLATION).replace("通り", "通")
    if strip_aza:
        if s.startswith("大字"):
            s = s[2:]
        elif s.startswith("字") and len(s) > 2:
            s = s[1:]
    return _kanji_runs_to_digits(s)


def split_chome(name: str) -> Tuple[str, Optional[int]]:
    """Splits a registered town name into its base and 丁目 number.

    '芝公園四丁目' -> ('芝公園', 4); '大字南長野' -> ('大字南長野', None)
    """
    m = _CHOME_SUFFIX.match(name)
    if not m:
        return name, None
    num = m.group("num")
    val = int(num) if num.isdigit() else parse_kanji_number(num)
    if val is None:
        return name, None
    return m.group("base"), val


_SMALL_KANA: Final[Dict[int, str]] = {ord(a): b for a, b in zip("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")}
_KANA_ONLY: Final[re.Pattern[str]] = re.compile(r"^[\u3041-\u3096\u30a1-\u30fa\u30fc\d]+$")


def is_kana(text: str) -> bool:
    """True when ``text`` is written only in hiragana / katakana (digits allowed)."""
    return bool(text) and bool(_KANA_ONLY.match(unicodedata.normalize("NFKC", text))) and not text.isdigit()


def kana_key(text: str) -> str:
    """Folds a reading for comparison: hiragana -> katakana, small kana -> large, no spaces.

    'しばこうえん', 'シバコウエン' and 'ｼﾊﾞｺｳｴﾝ' share one key; so do 'キョウ' and 'キヨウ',
    because data and people disagree on small kana.
    """
    s = unicodedata.normalize("NFKC", text).replace(" ", "")
    s = "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in s)
    return s.translate(_SMALL_KANA)


def one_edit_apart(a: str, b: str) -> bool:
    """True when two different strings differ by one substitution, insertion, deletion or adjacent swap."""
    if a == b:
        return False
    la, lb = len(a), len(b)
    if abs(la - lb) > 1:
        return False
    if la == lb:
        diff = [i for i in range(la) if a[i] != b[i]]
        if len(diff) == 1:
            return True
        return len(diff) == 2 and diff[1] == diff[0] + 1 and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]]
    if la > lb:
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i:] == b[i + 1:]
