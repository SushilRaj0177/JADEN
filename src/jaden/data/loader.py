"""JADEN: Data loader and verified registry cache.

Loads and indexes official JIS X 0401 prefectures and JIS X 0402 / MIC
Local Government Code municipal registries.
"""

from typing import Dict, List, Optional, Tuple, Final, Any
from dataclasses import dataclass
import json
from pathlib import Path

from ..models.codes import PrefectureRecord, LocalGovernmentCode, calculate_modulus11_check_digit
from ..core.constants import STANDARD_JIS_X_0401, STANDARD_JIS_X_0402, STANDARD_MIC_LG_CODE


@dataclass(frozen=True, slots=True)
class MunicipalityRecord:
    """Represents a municipality or administrative ward defined under JIS X 0402 / MIC."""
    prefecture_code: str               # 2 digits: e.g. "13"
    prefecture_name: str               # e.g. "東京都"
    base_code: str                     # 5 digits: e.g. "13101"
    check_digit: str                   # 1 digit: e.g. "6"
    lg_code: str                       # 6 digits: e.g. "131016"
    name: str                          # e.g. "千代田区" or "横浜市中区"
    city: str                          # Primary city/special-ward name: e.g. "千代田区" or "横浜市"
    ward: Optional[str] = None         # Administrative ward: e.g. "中区" (if designated city)
    county: Optional[str] = None       # 郡 (if town/village under county)
    entity_type: str = "city"          # special_ward, designated_city, administrative_ward, city, town, village
    kana: Optional[str] = None         # Half-width/Full-width katakana reading


class AddressDataRegistry:
    """In-memory verified registry of Japanese administrative entities."""

    _DATA_DIR = Path(__file__).parent

    def __init__(self) -> None:
        self._prefectures_by_code: Dict[str, PrefectureRecord] = {}
        self._prefectures_by_name: Dict[str, PrefectureRecord] = {}
        self._prefectures_by_stem: Dict[str, PrefectureRecord] = {}
        self._municipalities_by_code: Dict[str, MunicipalityRecord] = {}
        self._municipalities_by_pref_and_name: Dict[Tuple[str, str], MunicipalityRecord] = {}
        self._municipalities_by_name_global: Dict[str, List[MunicipalityRecord]] = {}
        self._loaded: bool = False

    def load_all(self) -> None:
        """Loads prefectures and municipalities from bundled verified datasets."""
        if self._loaded:
            return
        self._load_prefectures()
        self._load_municipalities()
        self._loaded = True

    def _load_prefectures(self) -> None:
        path = self._DATA_DIR / "jis_prefectures.json"
        if not path.exists():
            raise FileNotFoundError(f"Missing JIS X 0401 dataset at: {path}")

        with open(path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)

        for item in raw_list:
            rec = PrefectureRecord(
                code=item["code"],
                name=item["name"],
                stem=item["stem"],
                suffix=item["suffix"],
                kana=item["kana"],
                romaji=item["romaji"],
            )
            self._prefectures_by_code[rec.code] = rec
            self._prefectures_by_name[rec.name] = rec
            self._prefectures_by_stem[rec.stem] = rec

    def _load_municipalities(self) -> None:
        path = self._DATA_DIR / "municipalities.json"
        if not path.exists():
            return  # Will be populated by dataset generator

        with open(path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)

        for item in raw_list:
            rec = MunicipalityRecord(
                prefecture_code=item["prefecture_code"],
                prefecture_name=item["prefecture_name"],
                base_code=item["base_code"],
                check_digit=item["check_digit"],
                lg_code=item["lg_code"],
                name=item["name"],
                city=item["city"],
                ward=item.get("ward"),
                county=item.get("county"),
                entity_type=item.get("entity_type", "city"),
                kana=item.get("kana"),
            )
            self._municipalities_by_code[rec.lg_code] = rec
            self._municipalities_by_pref_and_name[(rec.prefecture_code, rec.name)] = rec
            
            # Index by primary full name
            if rec.name not in self._municipalities_by_name_global:
                self._municipalities_by_name_global[rec.name] = []
            self._municipalities_by_name_global[rec.name].append(rec)

            # Index by bare administrative ward name if present (e.g. '中央区' in '札幌市中央区')
            if rec.ward and rec.ward != rec.name:
                if rec.ward not in self._municipalities_by_name_global:
                    self._municipalities_by_name_global[rec.ward] = []
                if rec not in self._municipalities_by_name_global[rec.ward]:
                    self._municipalities_by_name_global[rec.ward].append(rec)

    # -------------------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------------------

    def get_prefecture_by_code(self, code: str) -> Optional[PrefectureRecord]:
        self.load_all()
        return self._prefectures_by_code.get(code)

    def get_prefecture_by_name(self, name: str) -> Optional[PrefectureRecord]:
        self.load_all()
        return self._prefectures_by_name.get(name)

    def get_prefecture_by_stem(self, stem: str) -> Optional[PrefectureRecord]:
        self.load_all()
        return self._prefectures_by_stem.get(stem)

    def list_all_prefectures(self) -> List[PrefectureRecord]:
        self.load_all()
        return list(self._prefectures_by_code.values())

    def get_municipality_by_code(self, code: str) -> Optional[MunicipalityRecord]:
        self.load_all()
        return self._municipalities_by_code.get(code)

    def find_municipalities(self, name: str, prefecture_code: Optional[str] = None) -> List[MunicipalityRecord]:
        self.load_all()
        if prefecture_code:
            key = (prefecture_code, name)
            rec = self._municipalities_by_pref_and_name.get(key)
            return [rec] if rec else []
        return self._municipalities_by_name_global.get(name, [])

    def get_provenance(self) -> Dict[str, Any]:
        """Loads and returns the authoritative data provenance metadata."""
        meta_path = self._DATA_DIR / "provenance.json"
        if not meta_path.exists():
            return {}
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)


# Singleton global instance
_REGISTRY_INSTANCE: Optional[AddressDataRegistry] = None


def get_registry() -> AddressDataRegistry:
    """Returns the singleton AddressDataRegistry instance."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = AddressDataRegistry()
        _REGISTRY_INSTANCE.load_all()
    return _REGISTRY_INSTANCE
