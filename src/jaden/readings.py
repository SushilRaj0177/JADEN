"""JADEN: Katakana readings and romanized address lines.

Readings come from Japan Post's postal-code data (katakana and romaji for
every municipality and town), so they follow the official romanization Japan
Post uses for mail rather than a guessed transliteration.

    東京都港区芝公園4丁目2番8号 -> kana:   トウキョウトミナトクシバコウエン
                                  romaji: 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011
"""

import json
import re
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


def _english_unit(unit: Optional[str]) -> Optional[str]:
    """'101号室' / '101号' / '101' -> '#101' for an English address line."""
    if not unit:
        return None
    digits = re.match(r"^(\d+(?:-\d+)*[A-Za-z]?|[A-Za-z](?:-?\d+)?)(?:号室|室|号)?$", unit)     # a wing stays with its room: '#1-201', '#207-1'
    return f"#{digits.group(1)}" if digits else unit


def _english_floor(floor: Optional[str]) -> Optional[str]:
    """'5階' -> '5F', '地下1階' -> 'B1F'."""
    if not floor:
        return None
    m = re.match(r"^(地下|B)?\s*(\d+)\s*(?:階|[Ff])$", floor) or re.match(r"^(B)(\d+)$", floor)   # 'B2' is B2F
    if not m:
        return floor
    return f"{'B' if m.group(1) else ''}{m.group(2)}F"


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
    house = (c.ban, c.go) if c.ban is not None or c.go is not None else (c.banchi, c.edaban)
    numbers = [n for n in (c.chome, *house) if n is not None]   # '5丁目13番地の1' keeps its 13-1
    number_str = "-".join(str(n) for n in numbers)
    if c.chome is not None and c.chome_verified is not True and len(numbers) == 3:
        number_str = f"{c.chome}-chome-{numbers[1]}-{numbers[2]}"   # a 丁目 the registry does not list
    elif c.chome is not None and len(numbers) == 1:
        number_str = f"{c.chome}-chome"           # a lone '8' would read back as a block number
    elif c.chome is not None and len(numbers) == 2:
        number_str = f"{c.chome}-chome-{numbers[1]}"   # '2-17' alone would read back as a lot and its branch
    after_town = ""
    if (c.chome is None and c.ban is None and c.banchi is not None and town is not None
            and (getattr(town, "chomes", None) or getattr(town, "postal_has_chome", False))):
        # '1-68' would read back as 1丁目68 in a town that has 丁目: the lot keeps its 番地
        number_str = f"{c.banchi}番地" + (f"{c.edaban}" if c.edaban is not None else "")
    if c.lot_number:
        lead = f"{c.chome}-chome" if c.chome is not None else ""
        if re.match(r"\d", c.lot_number):
            number_str = f"{lead}-{c.lot_number}" if lead else c.lot_number   # a three-part lot ('17-24-13')
        else:
            number_str, after_town = lead, c.lot_number   # '乙394' is written in Japanese after the town

    first = []
    written = re.sub(r"^大字", "", c.town or "")
    if town is not None and not town.romaji:
        town = None          # no published reading: the town is written in Japanese inside the English line
    if town is not None:
        town_words = " ".join(_words(town.romaji))
        base = re.sub(r"^字", "", town.name.replace("大字", ""))
        plain = re.sub(r"^字", "", written.replace("大字", ""))
        from .romaji import _index, romaji_key
        if len(_index().town_entries(muni.lg_code).get(romaji_key(town.romaji), ())) > 1:
            town_words += " " + town.name        # 志水町 and 清水町 are both 'Shimizucho': the name says which
        if not plain.startswith(base) and c.koaza and c.koaza not in town_words:
            koaza = c.koaza                            # '羽入字東原' read as town 羽入東, 字 原: the 字 kept
            overlap = next((i for i in range(len(koaza), 0, -1) if town.name.endswith(koaza[:i])), 0)
            if koaza[overlap:]:
                town_words += f" 字{koaza[overlap:]}"
        if plain.startswith(base) and plain[len(base):]:
            below = plain[len(base):]                   # a 字 below the town has no reading: kept as written
            if below.startswith(base) or (c.koaza and below.endswith(c.koaza) and not below.startswith(("字", "大字"))
                                          and re.match(r"[ァ-ヺー]", below)):
                below = "字" + below                    # '身延身延', 'タカノス': marked as the 字 it is
            town_words += " " + below
        if c.kyoto_direction is not None and getattr(c, "town_homonyms", 0) > 1:
            town_words += " " + c.kyoto_direction.raw_clause   # which of Kyoto's same-named towns
        if c.hokkaido_grid is not None and c.hokkaido_grid.chome is not None and c.ban is None and c.banchi is None:
            first.append(f"{town_words} {c.hokkaido_grid.chome}-chome")
        else:
            first.append(f"{number_str} {town_words} {after_town}".strip())
    elif c.hokkaido_grid is not None and c.hokkaido_grid.jo is not None:
        # A grid town with no published reading ('北6条西' in 標津町) is written in Japanese where the town goes
        g = c.hokkaido_grid
        rest_numbers = "-".join(str(n) for n in (c.ban, c.go) if n is not None) or \
            "-".join(str(n) for n in (c.banchi, c.edaban) if n is not None)
        first.append(f"{rest_numbers} {g.cardinal_ns}{g.jo}条{g.cardinal_ew}"
                     f"{f'{g.chome}丁目' if g.chome is not None else ''}{after_town}".strip())
    elif written and c.hokkaido_grid is None:
        first.append(f"{number_str} {written}{after_town}".strip())   # a town the registry does not hold, as written
    elif c.kyoto_direction is not None:
        # No town, only the Kyoto clause: it is written in Japanese where the town would be
        first.append(f"{number_str} {c.kyoto_direction.raw_clause}{after_town}".strip())
    elif number_str or after_town:
        first.append(f"{number_str} {after_town}".strip())

    # Wards and counties come before their city / town in English order
    admin = list(reversed(_words(muni_romaji)))
    pref_part = pref.romaji if pref else ""
    if c.postal_code:
        pref_part = f"{pref_part} {c.postal_code}".strip()

    lead = " ".join(x for x in (c.building, _english_floor(c.floor), _english_unit(c.unit)) if x)
    parts = ([lead] if lead else []) + first + admin + ([pref_part] if pref_part else [])
    return ", ".join(p for p in parts if p)
