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
import re
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
    """All registered records sharing one town name inside one municipality.

    Entries found only in the Japan Post list (``source == 'postal'``) have no MLIT records:
    no point, no list of 丁目, only Japan Post's flag saying whether the town has 丁目.
    """
    name: str
    records: List[TownRecord] = field(default_factory=list)
    source: str = "mlit"
    postal_kana: str = ""
    postal_romaji: str = ""
    postal_has_chome: bool = False

    @property
    def chomes(self) -> Tuple[int, ...]:
        return tuple(sorted({r.chome for r in self.records if r.chome is not None}))

    @property
    def has_chome(self) -> bool:
        if not self.records:
            return self.postal_has_chome
        return any(r.chome is not None for r in self.records)

    @property
    def chomes_known(self) -> bool:
        return bool(self.records)

    @property
    def kana(self) -> str:
        return next((r.kana for r in self.records if r.kana), self.postal_kana)

    @property
    def romaji(self) -> str:
        return next((r.romaji for r in self.records if r.romaji), self.postal_romaji)

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


class _Table:
    """A compiled TSV kept as one string; each municipality's rows are found by string search.

    Files are sorted by municipality code, so a municipality's rows form one slice between its
    first and last occurrence. This keeps memory near the size of the text instead of one
    Python object per row, and loading costs only the decompression.
    """

    def __init__(self, text: str, lg_column: int, index_all: bool = True) -> None:
        self.text = text
        self.lg_column = lg_column
        self._ranges: Dict[str, Optional[Tuple[int, int]]] = {}
        if index_all:
            # One regex pass (in C) finds where each municipality's rows start
            pattern = r"^(\d{6})\t" if lg_column == 0 else r"^[^\t\n]*\t(\d{6})\t"
            current, begin = None, 0
            for m in re.finditer(pattern, text, re.MULTILINE):
                lg = m.group(1)
                if lg != current:
                    if current is not None:
                        self._ranges[current] = (begin, m.start())
                    current, begin = lg, m.start()
            if current is not None:
                self._ranges[current] = (begin, len(text))
            self._complete = True
        else:
            self._complete = False

    def _needle(self, lg_code: str) -> str:
        return f"\n{lg_code}\t" if self.lg_column == 0 else f"\t{lg_code}\t"

    def span(self, lg_code: str) -> Optional[Tuple[int, int]]:
        if lg_code in self._ranges or self._complete:
            return self._ranges.get(lg_code)
        needle = self._needle(lg_code)
        first = self.text.find(needle)
        result: Optional[Tuple[int, int]] = None
        if first >= 0:
            last = self.text.rfind(needle)
            begin = self.text.rfind("\n", 0, first + 1) + 1
            end = self.text.find("\n", last + 1)
            result = (begin, len(self.text) if end < 0 else end)
        self._ranges[lg_code] = result
        return result

    def __contains__(self, lg_code: str) -> bool:
        return self.span(lg_code) is not None

    def lines(self, lg_code: str) -> List[str]:
        span = self.span(lg_code)
        if span is None:
            return []
        return [ln for ln in self.text[span[0]:span[1]].split("\n") if ln]

    def all_lines(self) -> List[str]:
        return [ln for ln in self.text.split("\n")[1:] if ln]


class Gazetteer:
    """Lazily loaded in-memory town and postal-code index."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else resolve_data_dir()
        self._available: Optional[bool] = None
        self._town_table: Optional[_Table] = None
        self._postal_table: Optional[_Table] = None
        self._towns: Dict[str, Dict[str, TownEntry]] = {}
        self._lg_by_key: Optional[Dict[str, List[str]]] = None
        self._postal_only: Dict[str, Dict[str, TownEntry]] = {}
        self._postal_by_town: Dict[str, Dict[str, List[str]]] = {}
        self._blocks_present: Dict[str, bool] = {}
        self._key_version_ok: Optional[bool] = None
        self._block_tables: Dict[str, Optional[_Table]] = {}
        self._blocks: Dict[str, Dict[Tuple[str, int, int], BlockPoint]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ load
    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = (self.data_dir / "towns.tsv.gz").exists()
        return self._available

    def _read_text(self, name: str) -> str:
        path = self.data_dir / name
        if not path.exists():
            return ""
        with gzip.open(path, "rb") as f:
            return f.read().decode("utf-8")

    def _keys_current(self) -> bool:
        if self._key_version_ok is None:
            self._key_version_ok = self.provenance().get("town_key_version") == TOWN_KEY_VERSION
        return self._key_version_ok

    def _towns_table(self) -> _Table:
        with self._lock:
            if self._town_table is None:
                self._town_table = _Table(self._read_text("towns.tsv.gz"), 0)
            return self._town_table

    def _postal(self) -> _Table:
        with self._lock:
            if self._postal_table is None:
                self._postal_table = _Table(self._read_text("postal.tsv.gz"), 1)
            return self._postal_table

    def towns_in(self, lg_code: str) -> Dict[str, TownEntry]:
        """Registered towns of one municipality, keyed by ``town_key``."""
        cached = self._towns.get(lg_code)
        if cached is not None:
            return cached
        recompute = not self._keys_current()
        by_key: Dict[str, TownEntry] = {}
        for ln in self._towns_table().lines(lg_code):
            lg, key, mid, name, chome, kind, lat, lon, kana, romaji = ln.split("\t")
            if recompute:
                key = town_key(name)
            entry = by_key.get(key)
            if entry is None:
                entry = by_key[key] = TownEntry(name)
            entry.records.append(TownRecord(lg, mid, name, int(chome) if chome else None, kind,
                                            float(lat), float(lon), kana, romaji))
        self._towns[lg_code] = by_key
        return by_key

    def _parse_postal(self, ln: str) -> Tuple[PostalRecord, str, bool]:
        parts = ln.split("\t")
        code, lg, key, town, kana, romaji, kind = parts[:7]
        if not self._keys_current():
            key = town_key(town)
        has_chome = len(parts) > 7 and parts[7] == "1"
        return PostalRecord(code, lg, town, kana, romaji, kind), key, has_chome

    def _key_index(self) -> Dict[str, List[str]]:
        """Town key -> municipality codes, over MLIT and Japan Post towns (built on first use)."""
        if self._lg_by_key is None:
            recompute = not self._keys_current()
            index: Dict[str, List[str]] = {}
            for ln in self._towns_table().all_lines():
                parts = ln.split("\t", 4)
                lg, key = parts[0], (town_key(parts[3]) if recompute else parts[1])
                lgs = index.setdefault(key, [])
                if not lgs or lgs[-1] != lg:
                    lgs.append(lg)
            # Towns only Japan Post lists still count when asking "where else does this town exist?"
            for ln in self._postal().all_lines():
                rec, key, _ = self._parse_postal(ln)
                if rec.kind == "town" and key and rec.lg_code not in index.get(key, ()):
                    index.setdefault(key, []).append(rec.lg_code)
            self._lg_by_key = index
        return self._lg_by_key

    def provenance(self) -> Dict[str, Any]:
        path = self.data_dir / "gazetteer_provenance.json"
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # --------------------------------------------------------------- queries
    def has_municipality(self, lg_code: str) -> bool:
        return lg_code in self._towns_table()

    def match_town(self, lg_code: str, text: str) -> Optional[TownMatch]:
        """Longest registered town name at the start of ``text`` within one municipality.

        MLIT towns are tried first; a town only Japan Post lists is used when MLIT has nothing.
        """
        if not text:
            return None
        clipped = text[:_MAX_KEY_CHARS]
        for towns in (self.towns_in(lg_code), self.postal_towns_in(lg_code)):
            if not towns:
                continue
            for end in range(len(clipped), 0, -1):
                entry = towns.get(town_key(clipped[:end]))
                if entry is not None:
                    return TownMatch(lg_code, entry, end, exact=(end == len(text)))
        return None

    def postal_towns_in(self, lg_code: str) -> Dict[str, TownEntry]:
        """Towns Japan Post lists for a municipality that the MLIT list does not have."""
        cached = self._postal_only.get(lg_code)
        if cached is not None:
            return cached
        mlit = self.towns_in(lg_code)
        out: Dict[str, TownEntry] = {}
        for ln in self._postal().lines(lg_code):
            rec, key, has_chome = self._parse_postal(ln)
            if rec.kind != "town" or not rec.town or key in mlit:
                continue
            entry = out.get(key)
            if entry is None:
                out[key] = TownEntry(rec.town, [], "postal", rec.kana, rec.romaji, has_chome)
            elif has_chome:
                entry.postal_has_chome = True
        self._postal_only[lg_code] = out
        return out

    def municipalities_with_town(self, text: str) -> List[Tuple[str, TownMatch]]:
        """All municipalities containing a town that matches the start of ``text`` (longest match per municipality)."""
        index = self._key_index()
        clipped = text[:_MAX_KEY_CHARS]
        found: Dict[str, TownMatch] = {}
        for end in range(len(clipped), 0, -1):
            key = town_key(clipped[:end])
            for lg in index.get(key, ()):
                if lg not in found:
                    entry = self.towns_in(lg).get(key) or self.postal_towns_in(lg).get(key)
                    if entry is not None:
                        found[lg] = TownMatch(lg, entry, end, exact=(end == len(text)))
        return list(found.items())

    def municipalities_with_exact_town(self, texts: List[str]) -> List[str]:
        """Municipality codes having a town whose whole name equals one of ``texts``."""
        index = self._key_index()
        out: List[str] = []
        for text in texts:
            for lg in index.get(town_key(text), ()):
                if lg not in out:
                    out.append(lg)
        return out

    def postal_records(self, postal_code: str) -> List[PostalRecord]:
        code = postal_code.replace("-", "")
        text = self._postal().text
        out: List[PostalRecord] = []
        needle = f"\n{code}\t"
        pos = text.find(needle)
        while pos >= 0:
            nl = text.find("\n", pos + 1)
            out.append(self._parse_postal(text[pos + 1:nl if nl >= 0 else len(text)])[0])
            pos = text.find(needle, pos + 1)
        return out

    def postal_codes_for(self, lg_code: str, town: Optional[str]) -> List[str]:
        """Postal codes registered for a town (falls back to the municipality-wide code)."""
        by_town = self._postal_by_town.get(lg_code)
        if by_town is None:
            by_town = {}
            for ln in self._postal().lines(lg_code):
                rec, key, _ = self._parse_postal(ln)
                if rec.kind != "building":
                    by_town.setdefault(key, []).append(rec.postal_code)
            self._postal_by_town[lg_code] = by_town
        key = town_key(town) if town else ""
        codes = by_town.get(key) if key else None
        return sorted(set(codes or by_town.get("", [])))

    # ---------------------------------------------------------------- blocks
    def block_dirs(self) -> List[Path]:
        dirs = [self.data_dir / "blocks", user_data_dir() / "blocks"]
        return [d for i, d in enumerate(dirs) if d not in dirs[:i]]

    def blocks_available(self, prefecture_code: str) -> bool:
        if prefecture_code not in self._blocks_present:
            self._blocks_present[prefecture_code] = any(
                (d / f"{prefecture_code}.tsv.gz").exists() for d in self.block_dirs())
        return self._blocks_present[prefecture_code]

    def _load_blocks(self, prefecture_code: str) -> Optional[_Table]:
        if prefecture_code in self._block_tables:
            return self._block_tables[prefecture_code]
        table: Optional[_Table] = None
        for d in self.block_dirs():
            path = d / f"{prefecture_code}.tsv.gz"
            if not path.exists():
                continue
            meta_path = d / f"{prefecture_code}.json"
            meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
            if meta.get("town_key_version") != TOWN_KEY_VERSION:
                continue  # built with an older key; ask the user to re-fetch rather than mis-match
            with gzip.open(path, "rb") as f:
                table = _Table(f.read().decode("utf-8"), 0, index_all=False)
            break
        self._block_tables[prefecture_code] = table
        return table

    def block_point(self, lg_code: str, town_name: str, chome: Optional[int], block: int) -> Optional[BlockPoint]:
        """Point of block ``block`` in a town / 丁目, when that prefecture's block data is installed."""
        points = self._blocks.get(lg_code)
        if points is None:
            table = self._load_blocks(lg_code[:2])
            points = {}
            for ln in table.lines(lg_code) if table else ():
                lg, key, ch, blk, lat, lon, jukyo = ln.split("\t")
                points[(key, int(ch) if ch else 0, int(blk))] = BlockPoint(float(lat), float(lon), jukyo == "1")
            self._blocks[lg_code] = points
        return points.get((town_key(town_name), chome or 0, block))


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
