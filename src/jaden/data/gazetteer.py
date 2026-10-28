"""JADEN: Town-level gazetteer and postal-code index.

Loads the compiled MLIT town list and Japan Post postal-code list (see
``build_gazetteer``) and answers the questions the engine needs:

- Does this town exist in this municipality, and which 丁目 does it have?
- Which of several candidate municipalities contains this town?
- Which municipality (and town) does this postal code belong to?
- What are the town's reading, romanization and representative point?

Data directory resolution (first match wins):
1. ``$JADEN_DATA_DIR``
2. the user data directory written by ``jaden data update``
   (``$XDG_DATA_HOME/jaden`` or ``~/.local/share/jaden``)
3. the files bundled inside the package
"""

import gzip
import json
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..core.townkey import TOWN_KEY_VERSION, town_key

_BUNDLED_DIR = Path(__file__).parent
# Longest town key in the national list is under 30 characters; inputs are clipped to this
_MAX_KEY_CHARS = 40


def user_data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "jaden"


def resolve_data_dir() -> Path:
    env = os.environ.get("JADEN_DATA_DIR")
    if env:
        return Path(env)
    user_dir = user_data_dir()
    if (user_dir / "towns.tsv.gz").exists() and (user_dir / "postal.tsv.gz").exists():
        return user_dir
    return _BUNDLED_DIR


@dataclass(frozen=True, slots=True)
class TownRecord:
    """One registered town or 丁目 (one MLIT row)."""
    lg_code: str
    machiaza_id: str
    name: str                 # registered name without 丁目, e.g. '芝公園', '大字南長野'
    chome: Optional[int]
    kind: str                 # '1' 大字, '2' 字, '3' 丁目, '0' unspecified
    latitude: float
    longitude: float
    kana: str = ""
    romaji: str = ""


@dataclass(slots=True)
class TownEntry:
    """All registered records sharing one town name inside one municipality."""
    name: str
    records: List[TownRecord] = field(default_factory=list)

    @property
    def chomes(self) -> Tuple[int, ...]:
        return tuple(sorted({r.chome for r in self.records if r.chome is not None}))

    @property
    def has_chome(self) -> bool:
        return any(r.chome is not None for r in self.records)

    @property
    def kana(self) -> str:
        return next((r.kana for r in self.records if r.kana), "")

    @property
    def romaji(self) -> str:
        return next((r.romaji for r in self.records if r.romaji), "")

    def record_for(self, chome: Optional[int]) -> Optional[TownRecord]:
        if chome is not None:
            return next((r for r in self.records if r.chome == chome), None)
        plain = [r for r in self.records if r.chome is None]
        return plain[0] if len(plain) == 1 else None


@dataclass(frozen=True, slots=True)
class TownMatch:
    """Result of matching the start of an input string against one municipality's towns."""
    lg_code: str
    entry: TownEntry
    consumed: int             # characters of the input covered by the town name
    exact: bool               # True when the whole input town string was consumed


@dataclass(frozen=True, slots=True)
class BlockPoint:
    """Representative point of one city block (街区) from MLIT block-level data."""
    latitude: float
    longitude: float
    jukyo_hyoji: bool         # True: 住居表示 街区符号; False: 地番


@dataclass(frozen=True, slots=True)
class PostalRecord:
    postal_code: str
    lg_code: str
    town: str                 # '' when the code covers the whole municipality
    kana: str
    romaji: str
    kind: str                 # 'town', 'building', 'municipality'


class Gazetteer:
    """Lazily loaded in-memory town and postal-code index."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else resolve_data_dir()
        self._raw_towns: Optional[Dict[str, List[str]]] = None
        self._recompute_keys = False
        self._towns: Dict[str, Dict[str, TownEntry]] = {}
        self._lg_by_key: Optional[Dict[str, List[str]]] = None
        self._postal: Optional[Dict[str, List[str]]] = None
        self._postal_by_town: Optional[Dict[Tuple[str, str], List[str]]] = None
        self._key_version_ok: Optional[bool] = None
        self._blocks: Dict[str, Optional[Dict[Tuple[str, str, int, int], BlockPoint]]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ load
    @property
    def available(self) -> bool:
        return (self.data_dir / "towns.tsv.gz").exists()

    def _read_lines(self, name: str) -> List[str]:
        path = self.data_dir / name
        if not path.exists():
            return []
        with gzip.open(path, "rb") as f:
            lines = f.read().decode("utf-8").split("\n")
        return [ln for ln in lines[1:] if ln]

    def _keys_current(self) -> bool:
        if self._key_version_ok is None:
            self._key_version_ok = self.provenance().get("town_key_version") == TOWN_KEY_VERSION
        return self._key_version_ok

    def _load_raw_towns(self) -> Dict[str, List[str]]:
        # Rows stay as raw lines grouped by municipality; each group is parsed on first use
        with self._lock:
            if self._raw_towns is None:
                raw: Dict[str, List[str]] = {}
                for ln in self._read_lines("towns.tsv.gz"):
                    raw.setdefault(ln[:6], []).append(ln)
                self._raw_towns = raw
                self._recompute_keys = not self._keys_current()
            return self._raw_towns

    def towns_in(self, lg_code: str) -> Dict[str, TownEntry]:
        """Registered towns of one municipality, keyed by ``town_key``."""
        cached = self._towns.get(lg_code)
        if cached is not None:
            return cached
        by_key: Dict[str, TownEntry] = {}
        for ln in self._load_raw_towns().get(lg_code, ()):
            lg, key, mid, name, chome, kind, lat, lon, kana, romaji = ln.split("\t")
            if self._recompute_keys:
                key = town_key(name)
            entry = by_key.get(key)
            if entry is None:
                entry = by_key[key] = TownEntry(name)
            entry.records.append(TownRecord(lg, mid, name, int(chome) if chome else None, kind,
                                            float(lat), float(lon), kana, romaji))
        self._towns[lg_code] = by_key
        return by_key

    def _key_index(self) -> Dict[str, List[str]]:
        if self._lg_by_key is None:
            index: Dict[str, List[str]] = {}
            for lg, lines in self._load_raw_towns().items():
                for ln in lines:
                    key = ln.split("\t", 2)[1] if not self._recompute_keys else town_key(ln.split("\t", 4)[3])
                    lgs = index.setdefault(key, [])
                    if not lgs or lgs[-1] != lg:
                        lgs.append(lg)
            self._lg_by_key = index
        return self._lg_by_key

    def _load_postal(self) -> Dict[str, List[str]]:
        with self._lock:
            if self._postal is None:
                raw: Dict[str, List[str]] = {}
                for ln in self._read_lines("postal.tsv.gz"):
                    raw.setdefault(ln[:7], []).append(ln)
                self._postal = raw
            return self._postal

    def _parse_postal(self, ln: str) -> Tuple[PostalRecord, str]:
        code, lg, key, town, kana, romaji, kind = ln.split("\t")
        if not self._keys_current():
            key = town_key(town)
        return PostalRecord(code, lg, town, kana, romaji, kind), key

    def provenance(self) -> Dict[str, Any]:
        path = self.data_dir / "gazetteer_provenance.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # --------------------------------------------------------------- queries
    def has_municipality(self, lg_code: str) -> bool:
        return lg_code in self._load_raw_towns()

    def match_town(self, lg_code: str, text: str) -> Optional[TownMatch]:
        """Longest registered town name at the start of ``text`` within one municipality."""
        towns = self.towns_in(lg_code)
        if not towns or not text:
            return None
        clipped = text[:_MAX_KEY_CHARS]
        for end in range(len(clipped), 0, -1):
            entry = towns.get(town_key(clipped[:end]))
            if entry is not None:
                return TownMatch(lg_code, entry, end, exact=(end == len(text)))
        return None

    def municipalities_with_town(self, text: str) -> List[Tuple[str, TownMatch]]:
        """All municipalities containing a town that matches the start of ``text`` (longest match per municipality)."""
        index = self._key_index()
        clipped = text[:_MAX_KEY_CHARS]
        found: Dict[str, TownMatch] = {}
        for end in range(len(clipped), 0, -1):
            key = town_key(clipped[:end])
            for lg in index.get(key, ()):
                if lg not in found:
                    found[lg] = TownMatch(lg, self.towns_in(lg)[key], end, exact=(end == len(text)))
        return list(found.items())

    def postal_records(self, postal_code: str) -> List[PostalRecord]:
        lines = self._load_postal().get(postal_code.replace("-", ""), [])
        return [self._parse_postal(ln)[0] for ln in lines]

    def postal_codes_for(self, lg_code: str, town: Optional[str]) -> List[str]:
        """Postal codes registered for a town (falls back to the municipality-wide code)."""
        if self._postal_by_town is None:
            by_town: Dict[Tuple[str, str], List[str]] = {}
            for lines in self._load_postal().values():
                for ln in lines:
                    rec, key = self._parse_postal(ln)
                    if rec.kind != "building":
                        by_town.setdefault((rec.lg_code, key), []).append(rec.postal_code)
            self._postal_by_town = by_town
        key = town_key(town) if town else ""
        codes = self._postal_by_town.get((lg_code, key)) if key else None
        return sorted(set(codes or self._postal_by_town.get((lg_code, ""), [])))


    # ---------------------------------------------------------------- blocks
    def block_dirs(self) -> List[Path]:
        dirs = [self.data_dir / "blocks", user_data_dir() / "blocks"]
        return [d for i, d in enumerate(dirs) if d not in dirs[:i]]

    def blocks_available(self, prefecture_code: str) -> bool:
        return any((d / f"{prefecture_code}.tsv.gz").exists() for d in self.block_dirs())

    def _load_blocks(self, prefecture_code: str) -> Optional[Dict[Tuple[str, str, int, int], BlockPoint]]:
        if prefecture_code in self._blocks:
            return self._blocks[prefecture_code]
        table: Optional[Dict[Tuple[str, str, int, int], BlockPoint]] = None
        for d in self.block_dirs():
            path = d / f"{prefecture_code}.tsv.gz"
            if not path.exists():
                continue
            meta_path = d / f"{prefecture_code}.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            if meta.get("town_key_version") != TOWN_KEY_VERSION:
                continue  # built with an older key; ask the user to re-fetch rather than mis-match
            table = {}
            with gzip.open(path, "rb") as f:
                for ln in f.read().decode("utf-8").split("\n")[1:]:
                    if not ln:
                        continue
                    lg, key, chome, block, lat, lon, jukyo = ln.split("\t")
                    table[(lg, key, int(chome) if chome else 0, int(block))] = BlockPoint(
                        float(lat), float(lon), jukyo == "1")
            break
        self._blocks[prefecture_code] = table
        return table

    def block_point(self, lg_code: str, town_name: str, chome: Optional[int], block: int) -> Optional[BlockPoint]:
        """Point of block ``block`` in a town / 丁目, when that prefecture's block data is installed."""
        table = self._load_blocks(lg_code[:2])
        if not table:
            return None
        return table.get((lg_code, town_key(town_name), chome or 0, block))


_GAZETTEER: Optional[Gazetteer] = None


def get_gazetteer() -> Gazetteer:
    global _GAZETTEER
    if _GAZETTEER is None:
        _GAZETTEER = Gazetteer()
    return _GAZETTEER


def reset_gazetteer() -> None:
    """Drops the cached gazetteer so the next call reloads (used after ``jaden data update``)."""
    global _GAZETTEER
    _GAZETTEER = None
