"""JADEN: Strongly-typed data models for normalized Japanese addresses.

Distinguishes between statutory residential addressing (住居表示: 街区方式),
cadastral lot addressing (地番区域), and conventional systems (Kyoto, Hokkaido).
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any
import json
from .codes import TaxonomyTier


@dataclass(frozen=True, slots=True)
class KyotoDirectionClause:
    """Represents a Kyoto conventional street-intersection navigation clause.

    Example: '寺町通御池上る' -> street_1='寺町通', street_2='御池通', direction='上る', cardinal='north'
    """
    street_1: str                 # Primary street: e.g. '寺町通'
    street_2: str                 # Cross street: e.g. '御池通' (or '御池')
    direction: str                # '上る', '下る', '東入', '西入'
    cardinal: str                 # 'north', 'south', 'east', 'west'
    raw_clause: str               # The exact matched string in the input


@dataclass(frozen=True, slots=True)
class HokkaidoGridClause:
    """Represents a Hokkaido Sapporo-style Jo-Chome cardinal grid clause.

    Example: '北1条西2丁目' -> cardinal_ns='北', jo=1, cardinal_ew='西', chome=2
    """
    cardinal_ns: Optional[str]    # '北' (North) or '南' (South)
    jo: Optional[int]             # Strip number (条)
    cardinal_ew: Optional[str]    # '東' (East) or '西' (West)
    chome: Optional[int]          # Block number (丁目)
    raw_clause: str


@dataclass(frozen=True, slots=True)
class AddressComponents:
    """Granular parsed components of a Japanese address."""
    prefecture_code: Optional[str] = None     # JIS X 0401 (e.g., '13')
    prefecture: Optional[str] = None          # e.g., '東京都'
    prefecture_inferred: bool = False         # True if inferred heuristically (Tier 3)

    lg_code: Optional[str] = None             # 6-digit 全国地方公共団体コード (e.g. '131032')
    county: Optional[str] = None              # 郡 (e.g., '愛知郡')
    city: Optional[str] = None                # 市 or 東京都特別区 (e.g., '横浜市', '港区')
    ward: Optional[str] = None                # 政令指定都市の行政区 (e.g., '中区' in 横浜市中区)

    oaza: Optional[str] = None                # 大字 (e.g., '大字新宿')
    koaza: Optional[str] = None               # 字 / 小字
    town: Optional[str] = None                # 町名 (e.g., '六本木', '丸の内', '上本能寺前町')

    # Gaiku-hoshiki (住居表示に関する法律 街区方式)
    chome: Optional[int] = None               # 丁目 (e.g., 6)
    ban: Optional[int] = None                 # 街区符号 (番, e.g., 10)
    go: Optional[int] = None                  # 住居番号 (号, e.g., 1)

    # Chiban system (不動産登記法 地番区域)
    banchi: Optional[int] = None              # 地番 (番地, e.g., 488)
    edaban: Optional[int] = None              # 支号 / 枝番 (e.g., 1 in 488番地の1)

    # Building & Unit sub-clauses
    building: Optional[str] = None            # 建物名 (e.g., '六本木ヒルズ森タワー')
    floor: Optional[str] = None               # 階数 (e.g., '50F', '3階', 'B1F')
    unit: Optional[str] = None                # 部屋番号 (e.g., '5001号室', '302')

    # Conventional navigation clauses
    kyoto_direction: Optional[KyotoDirectionClause] = None
    hokkaido_grid: Optional[HokkaidoGridClause] = None

    unparsed_tail: Optional[str] = None       # Any tail string that could not be deterministically parsed


@dataclass(frozen=True, slots=True)
class NormalizedAddress:
    """The canonical output produced by JADEN."""
    input_raw: str
    input_sanitized: str
    canonical: str
    components: AddressComponents
    tier_map: Dict[str, str] = field(default_factory=dict)
    confidence_score: float = 1.0
    latency_microseconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the normalized address to a clean dictionary."""
        return asdict(self)

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes the normalized address to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
