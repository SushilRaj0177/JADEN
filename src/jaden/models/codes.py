"""JADEN: Official JIS codes and Local Government Code data structures.

Implements strict validation according to:
- JIS X 0401:1973 (Prefecture code 01-47)
- JIS X 0402:2020 / MIC standard (6-digit code with Modulus 11 check digit)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TaxonomyTier(str, Enum):
    """Four-tier taxonomy of truth separating statutory facts from heuristics."""
    TIER_1_STATUTORY = "tier_1_statutory"          # Legally defined in statute (JIS, 1962 Act, Real Property Act)
    TIER_2_CONVENTIONAL = "tier_2_conventional"    # Documented real-world conventions (Kyoto street names, Hokkaido grid)
    TIER_3_HEURISTIC = "tier_3_heuristic"          # Inferred/heuristic handling (omitted prefecture, dash resolution)
    TIER_4_SYSTEM = "tier_4_system_assumption"     # JADEN schema normalization artifact


class AddressRegime(str, Enum):
    """Statutory addressing regime distinguishing residential vs cadastral domains."""
    GAIKU_HOSHIKI = "gaiku_hoshiki"      # 住居表示 (街区方式: 丁目・番・号) under Act No. 119 of 1962
    CHIBAN = "chiban"                    # 地番区域 (番地・枝番/支号) under Real Property Registration Act (Act No. 123 of 2004)
    UNSPECIFIED = "unspecified"          # Hyphenated or bare numbers without statutory distinguishing markers


def calculate_modulus11_check_digit(d5: str) -> str:
    """Calculates the 6th check digit for a 5-digit JIS X 0402 municipality code.

    Official MIC (総務省) Modulus 11 formula:
    Weights for digits d1..d5: [6, 5, 4, 3, 2]
    Sum = sum(di * wi)
    Remainder R = Sum mod 11
    If R <= 1: Check digit = (11 - R) mod 10
    If R >= 2: Check digit = 11 - R
    """
    if len(d5) != 5 or not d5.isdigit():
        raise ValueError(f"Base municipality code must be exactly 5 digits, got '{d5}'")

    weights = [6, 5, 4, 3, 2]
    digits = [int(c) for c in d5]
    s = sum(d * w for d, w in zip(digits, weights))
    r = s % 11
    if r <= 1:
        return str((11 - r) % 10)
    return str(11 - r)


@dataclass(frozen=True, slots=True)
class PrefectureRecord:
    """Represents a prefecture defined under JIS X 0401."""
    code: str              # 2 digits: "01" to "47"
    name: str              # Full name: e.g. "東京都", "北海道", "京都府", "神奈川県"
    stem: str              # Name without suffix: e.g. "東京", "北海", "京都", "神奈川"
    suffix: str            # "都", "道", "府", "県"
    kana: str              # Half/Full Katakana: e.g. "トウキョウト"
    romaji: str            # Romanized name: e.g. "Tokyo"

    def __post_init__(self) -> None:
        if not (len(self.code) == 2 and self.code.isdigit() and 1 <= int(self.code) <= 47):
            raise ValueError(f"Invalid JIS X 0401 prefecture code: '{self.code}'")


@dataclass(frozen=True, slots=True)
class LocalGovernmentCode:
    """Represents a 6-digit Local Government Code (全国地方公共団体コード)."""
    code: str

    def __post_init__(self) -> None:
        if len(self.code) != 6 or not self.code.isdigit():
            raise ValueError(f"Local Government Code must be 6 digits, got '{self.code}'")

    @property
    def prefecture_code(self) -> str:
        """JIS X 0401 2-digit prefecture code."""
        return self.code[:2]

    @property
    def municipality_base_code(self) -> str:
        """JIS X 0402 5-digit base municipality code."""
        return self.code[:5]

    @property
    def check_digit(self) -> str:
        """The 6th check digit."""
        return self.code[5]

    def is_valid_checksum(self) -> bool:
        """Validates if the 6th digit matches the official Modulus 11 check digit."""
        expected = calculate_modulus11_check_digit(self.municipality_base_code)
        return self.check_digit == expected
