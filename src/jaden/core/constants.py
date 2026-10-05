"""JADEN: Authoritative standards, statutory citations, and character constants.

All specifications, legal acts, and encoding standards referenced herein are
verified against official Japanese government bodies (MIC, JISC, Digital Agency).
"""

from typing import Final, Dict, Set, Tuple

# ============================================================================
# STATUTORY AND OFFICIAL SPECIFICATION CITATIONS
# ============================================================================

STANDARD_JIS_X_0401: Final[str] = (
    "JIS X 0401:1973 (revised 2014) Codes for the identification of prefectures "
    "[都道府県コード] (Japanese Industrial Standards Committee)"
)

STANDARD_JIS_X_0402: Final[str] = (
    "JIS X 0402:2020 Identification codes for cities, towns and villages "
    "[市区町村コード] (Japanese Industrial Standards Committee)"
)

STANDARD_MIC_LG_CODE: Final[str] = (
    "全国地方公共団体コード仕様 (Ministry of Internal Affairs and Communications / 総務省) "
    "6-digit composite code: 2-digit JIS X 0401 + 3-digit municipality + 1-digit Modulus 11 check digit"
)

ACT_JUKYO_HYOJI: Final[str] = (
    "住居表示に関する法律 (昭和37年5月10日法律第119号 / Act on Indication of Residential Address, 1962). "
    "Establishes Gaiku-hoshiki (街区方式: 街区符号 + 住居番号) for urban residential areas."
)

ACT_REAL_PROPERTY: Final[str] = (
    "不動産登記法 (平成16年6月18日法律第123号 / Real Property Registration Act, 2004) & Civil Code. "
    "Establishes Chiban (地番区域: 大字・字 + 番地 + 支号/枝番) for cadastral land identification."
)

SPEC_DIGITAL_AGENCY_ABR: Final[str] = (
    "デジタル庁 アドレス・ベース・レジストリ データ仕様書 (Digital Agency Address Base Registry, 2024-2025). "
    "Comprehensive national master catalogs for 町字 (Machi-aza), 街区 (Gaiku), and 住居番号 (Jukyo-bango)."
)

# ============================================================================
# UNICODE CHARACTER SETS & CODEPOINTS
# ============================================================================

# Japanese hyphen and dash variants observed across CJK user input
# Mapped to (Codepoint, Unicode Name, Always Hyphen?)
DASH_VARIANTS: Final[Dict[str, Tuple[str, str, bool]]] = {
    "-": ("U+002D", "HYPHEN-MINUS", True),
    "－": ("U+FF0D", "FULLWIDTH HYPHEN-MINUS", True),
    "‐": ("U+2010", "HYPHEN", True),
    "‑": ("U+2011", "NON-BREAKING HYPHEN", True),
    "‒": ("U+2012", "FIGURE DASH", True),
    "–": ("U+2013", "EN DASH", True),
    "—": ("U+2014", "EM DASH", True),
    "―": ("U+2015", "HORIZONTAL BAR", True),
    "−": ("U+2212", "MINUS SIGN", True),
    "～": ("U+FF5E", "FULLWIDTH TILDE", True),
    "〜": ("U+301C", "WAVE DASH", True),
    "~": ("U+007E", "TILDE (NFKC COMPATIBILITY OF FULLWIDTH TILDE)", True),
    "─": ("U+2500", "BOX DRAWINGS LIGHT HORIZONTAL", True),
    "━": ("U+2501", "BOX DRAWINGS HEAVY HORIZONTAL", True),
    "﹣": ("U+FE63", "SMALL HYPHEN-MINUS", True),
    "﹘": ("U+FE58", "SMALL EM DASH", True),
    # U+30FC is the Katakana Chōonpu (prolonged sound mark).
    # It must ONLY be treated as a hyphen in contextual numeric splits (e.g. 1ー2ー3),
    # NEVER inside katakana proper nouns (e.g. タワー, センター).
    "ー": ("U+30FC", "KATAKANA-HIRAGANA PROLONGED SOUND MARK", False),
}

# Unconditional dash characters (safe for direct regex/table substitution outside katakana words)
UNCONDITIONAL_DASH_CHARS: Final[Set[str]] = {
    char for char, (_, _, is_unconditional) in DASH_VARIANTS.items() if is_unconditional
}

# Whitespace code points in Japanese text
WHITESPACE_CHARS: Final[Set[str]] = {
    "\u0020",  # ASCII space
    "\u3000",  # IDEOGRAPHIC SPACE (Japanese full-width space)
    "\u00A0",  # NO-BREAK SPACE
    "\u0009",  # HORIZONTAL TAB
    "\n",      # LINE FEED
    "\r",      # CARRIAGE RETURN
}

# ============================================================================
# KANJI NUMERALS MAPPING (ARABIC & DAIJI EQUIVALENTS)
# ============================================================================

# Single-digit mappings
KANJI_DIGITS: Final[Dict[str, int]] = {
    "〇": 0, "零": 0,
    "一": 1, "壱": 1,
    "二": 2, "弐": 2,
    "三": 3, "参": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}

# Positional multiplier units
KANJI_POWERS: Final[Dict[str, int]] = {
    "十": 10, "拾": 10,
    "百": 100,
    "千": 1000,
}

# ============================================================================
# KYOTO CONVENTIONAL DIRECTIONAL SYNTAX
# ============================================================================

# Cardinal directions relative to street intersections in Kyoto City (京都市)
KYOTO_DIRECTIONS: Final[Dict[str, str]] = {
    "上る": "north",
    "上ル": "north",
    "上ラル": "north",
    "あがる": "north",
    "下る": "south",
    "下ル": "south",
    "くだる": "south",
    "東入": "east",
    "東入る": "east",
    "東入ル": "east",
    "ひがしいる": "east",
    "西入": "west",
    "西入る": "west",
    "西入ル": "west",
    "にしいる": "west",
}

# ============================================================================
# ADMINISTRATIVE SUFFIXES
# ============================================================================

PREFECTURE_SUFFIXES: Final[Tuple[str, ...]] = ("都", "道", "府", "県")
MUNICIPALITY_SUFFIXES: Final[Tuple[str, ...]] = ("市", "区", "町", "村")
COUNTY_SUFFIX: Final[str] = "郡"
