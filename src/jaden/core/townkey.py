"""JADEN: Orthographic matching keys for town (町字) names.

The same town is routinely written several ways:

- small/large ke and the particle ga: 霞が関 / 霞ヶ関 / 霞ケ関 / 霞ヵ関
- the genitive no: 一の宮 / 一ノ宮
- kanji vs Arabic numerals: 北一条西 / 北1条西, 十条 / 10条
- traditional vs simplified kanji: 澤 / 沢, 濱 / 浜, 邊 / 辺
- an optional 大字 / 字 prefix in cadastral areas: 大字南長野 / 南長野

``town_key`` folds all of these into one comparison key. It is applied to both
the gazetteer and the user's input, so the folding only needs to be consistent,
not linguistically exact. Keys are never shown to users.
"""

import re
import unicodedata
from typing import Final, Dict, Optional, Tuple

from .constants import KANJI_DIGITS, KANJI_POWERS
from .kanji_numerals import parse_kanji_number

# Bump whenever town_key output changes; compiled data stores keys built with this version
TOWN_KEY_VERSION: Final[int] = 1

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
}

_KANJI_NUM_CHARS: Final[str] = "".join(list(KANJI_DIGITS) + list(KANJI_POWERS))
_KANJI_RUN: Final[re.Pattern[str]] = re.compile(f"[{_KANJI_NUM_CHARS}]+")
_TRANSLATION: Final[Dict[int, str]] = {
    **{ord(c): "ケ" for c in _KE_VARIANTS},
    **{ord(c): "ノ" for c in _NO_VARIANTS},
    **{ord(k): v for k, v in _ITAIJI.items()},
    ord(" "): None, ord("　"): None, ord("・"): None,  # type: ignore[dict-item]
}

_CHOME_SUFFIX: Final[re.Pattern[str]] = re.compile(rf"^(?P<base>.+?)(?P<num>[{_KANJI_NUM_CHARS}]+|\d+)丁目$")


def _kanji_runs_to_digits(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        val = parse_kanji_number(m.group(0))
        return str(val) if val is not None else m.group(0)
    return _KANJI_RUN.sub(repl, text)


def town_key(name: str, strip_aza: bool = True) -> str:
    """Folds a town name into its orthographic comparison key."""
    if not name:
        return ""
    s = unicodedata.normalize("NFKC", name).translate(_TRANSLATION)
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
