"""JADEN: Katakana readings and romanized address lines.

Readings come from Japan Post's postal-code data (katakana and romaji for
every municipality and town), so they follow the official romanization Japan
Post uses for mail rather than a guessed transliteration.

    東京都港区芝公園4丁目2番8号 -> kana:   トウキョウトミナトクシバコウエン
                                  romaji: 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011
"""

import json
import unicodedata
from pathlib import Path
from typing import Dict, Optional, List, Any, Final

from .data.gazetteer import TownEntry, resolve_data_dir
from .data.loader import MunicipalityRecord
from .models.codes import PrefectureRecord

# Administrative suffixes that Japan Post writes as separate words ('MINATO KU')
_SUFFIXES: Final[frozenset] = frozenset({"SHI", "KU", "GUN", "MACHI", "CHO", "MURA", "SON", "TO", "FU", "KEN"})

_READINGS: Optional[Dict[str, Dict[str, str]]] = None


def _municipality_readings() -> Dict[str, Dict[str, str]]:
    global _READINGS
    if _READINGS is None:
        for directory in (resolve_data_dir(), Path(__file__).parent / "data"):
            path = directory / "municipality_readings.json"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    _READINGS = json.load(f)
                break
        else:
            _READINGS = {}
    return _READINGS


def _kana(text: Optional[str]) -> str:
    return unicodedata.normalize("NFKC", text or "")


def kana_reading(pref: Optional[PrefectureRecord], muni: Optional[MunicipalityRecord],
                 town: Optional[TownEntry]) -> Optional[str]:
    """Katakana reading of the named part of the address (no block numbers)."""
    if muni is None:
        return None
    muni_kana = _municipality_readings().get(muni.lg_code, {}).get("kana") or _kana(muni.kana)
    if not muni_kana:
        return None
    parts = [_kana(pref.kana) if pref else "", muni_kana]
    if town is not None:
        if not town.kana:
            return None  # a partial reading is worse than none on a furigana field
        parts.append(town.kana)
    return "".join(parts)


def _words(romaji: str) -> List[str]:
    """'SAPPORO SHI CHUO KU' -> ['Sapporo-shi', 'Chuo-ku']"""
    out: List[str] = []
    for tok in romaji.split():
        if tok in _SUFFIXES and out:
            out[-1] += "-" + tok.lower()
        else:
            out.append("-".join(p.capitalize() for p in tok.split("-")))
    return out


def romaji_address(pref: Optional[PrefectureRecord], muni: Optional[MunicipalityRecord],
                   town: Optional[TownEntry], components: Any) -> Optional[str]:
    """English-order address line: building, numbers + town, ward, city, prefecture, postal code."""
    if muni is None:
        return None
    muni_romaji = _municipality_readings().get(muni.lg_code, {}).get("romaji")
    if not muni_romaji:
        return None
    c = components
    numbers = [n for n in (c.chome, c.ban, c.go) if n is not None]
    if not numbers:
        numbers = [n for n in (c.banchi, c.edaban) if n is not None]
    number_str = "-".join(str(n) for n in numbers)

    first = []
    if town is not None:
        if not town.romaji:
            return None
        town_words = " ".join(_words(town.romaji))
        if c.hokkaido_grid is not None and c.hokkaido_grid.chome is not None and c.ban is None and c.banchi is None:
            first.append(f"{town_words} {c.hokkaido_grid.chome}-chome")
        else:
            first.append(f"{number_str} {town_words}".strip())
    elif number_str:
        first.append(number_str)

    # Wards and counties come before their city / town in English order
    admin = list(reversed(_words(muni_romaji)))
    pref_part = pref.romaji if pref else ""
    if c.postal_code:
        pref_part = f"{pref_part} {c.postal_code}".strip()

    lead = " ".join(x for x in (c.building, c.floor, c.unit) if x)
    parts = ([lead] if lead else []) + first + admin + ([pref_part] if pref_part else [])
    return ", ".join(p for p in parts if p)
