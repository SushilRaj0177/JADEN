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

import bisect
import gzip
import json
import math
import os
import re
import threading
import unicodedata
from array import array
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from ..core.townkey import TOWN_KEY_VERSION, kana_key, town_key

_BUNDLED_DIR = Path(__file__).parent
# Grid cell of the nearest-town index, in degrees (about 2 km)
_CELL_DEG = 0.02
# Bounding box of every registered point (Okinotorishima to Etorofu, Yonaguni to Minamitorishima), with room
_JAPAN_LAT = (20.0, 46.0)
_NOT_CACHED = object()
# Small kana read as their full-size form, so 'キッ' and 'キツ' both find 'キッカワ'
_SMALL_KANA = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")
_JAPAN_LON = (122.0, 154.5)
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


def _chome_spec(spec: str) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """(whole 丁目 ranges, partly covered 丁目 ranges) of a Japan Post row ('1-3,~4' -> ([(1, 3)], [(4, 4)]))."""
    whole: List[Tuple[int, int]] = []
    partly: List[Tuple[int, int]] = []
    for part in spec.split(","):
        target = partly if part.startswith("~") else whole
        low, _, high = part.lstrip("~").partition("-")
        if low.isdigit() and (not high or high.isdigit()):
            target.append((int(low), int(high or low)))
    return whole, partly


def _rows_for_chome(rows: List[Tuple[str, str]], chome: Optional[int]) -> List[Tuple[str, str]]:
    """The postal rows of one town that can hold an address in ``chome`` (None: no 丁目 written)."""
    if len({code for code, _ in rows}) == 1:
        return rows
    plain = [r for r in rows if r[1] == ""]
    if chome is None:
        return plain or rows
    whole = [r for r in rows if any(a <= chome <= b for a, b in _chome_spec(r[1])[0])]
    partly = [r for r in rows if any(a <= chome <= b for a, b in _chome_spec(r[1])[1])]
    rest = [r for r in rows if r[1] == "-"]
    unknown = [r for r in rows if r[1] == "?"]
    if whole and not partly:
        return whole
    if partly:
        return partly + whole + rest
    # The 丁目 is named by no row: it is in the remainder, unless a row this cannot read may hold it
    for group in (rest, [r for r in rows if r[1] == "*"], plain):
        if group:
            return group + unknown
    return rows


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
        self._kana_index: Dict[str, Dict[str, List[TownEntry]]] = {}
        self._grid: Optional[Tuple[Dict[Tuple[int, int], List[int]], List[float], List[float], List[int]]] = None
        self._postal_by_town: Dict[str, Dict[str, List[Tuple[str, str]]]] = {}
        self._postal_index: Optional[Tuple["array[int]", "array[int]"]] = None
        self._blocks_present: Dict[str, bool] = {}
        self._key_version_ok: Optional[bool] = None
        self._block_tables: Dict[str, Optional[_Table]] = {}
        self._blocks: Dict[str, Dict[Tuple[str, int, int], BlockPoint]] = {}
        self._lock = threading.RLock()  # re-entrant: loaders call each other
        self._prefix_indexes: Dict[str, Tuple[List[str], List[Tuple[str, str]]]] = {}
        self._match_cache: Dict[Tuple[str, str], Optional["TownMatch"]] = {}

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
        cache_key = (lg_code, text)
        # One read, not 'in' then '[]': another thread may clear the cache in between
        cached = self._match_cache.get(cache_key, _NOT_CACHED)
        if cached is not _NOT_CACHED:
            return cached  # type: ignore[return-value]
        found: Optional[TownMatch] = None
        clipped = text[:_MAX_KEY_CHARS]
        for towns in (self.towns_in(lg_code), self.postal_towns_in(lg_code)):
            if not towns:
                continue
            for end in range(len(clipped), 0, -1):
                entry = towns.get(town_key(clipped[:end]))
                if entry is not None:
                    found = TownMatch(lg_code, entry, end, exact=(end == len(text)))
                    break
            if found is not None:
                break
        if len(self._match_cache) > 20_000:
            self._match_cache.clear()
        self._match_cache[cache_key] = found
        return found

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

    def towns_by_kana(self, lg_code: str) -> Dict[str, List[TownEntry]]:
        """Towns of one municipality (MLIT and Japan Post) by folded katakana reading."""
        cached = self._kana_index.get(lg_code)
        if cached is None:
            cached = {}
            for towns in (self.towns_in(lg_code), self.postal_towns_in(lg_code)):
                for entry in towns.values():
                    if entry.kana:
                        cached.setdefault(kana_key(entry.kana), []).append(entry)
            self._kana_index[lg_code] = cached
        return cached

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

    def _postal_code_index(self) -> Tuple["array[int]", "array[int]"]:
        """Postal codes in ascending order and the offset of each one's line (built on first use)."""
        with self._lock:
            if self._postal_index is None:
                text = self._postal().text
                pairs = sorted((int(m.group(1)), m.start()) for m in re.finditer(r"^(\d{7})\t", text, re.MULTILINE))
                self._postal_index = (array("l", [c for c, _ in pairs]), array("l", [o for _, o in pairs]))
            return self._postal_index

    def postal_records(self, postal_code: str) -> List[PostalRecord]:
        code = postal_code.replace("-", "")
        if not (code.isdigit() and len(code) == 7):
            return []
        codes, offsets = self._postal_code_index()
        text = self._postal().text
        out: List[PostalRecord] = []
        number = int(code)
        for i in range(bisect.bisect_left(codes, number), bisect.bisect_right(codes, number)):
            start = offsets[i]
            nl = text.find("\n", start)
            out.append(self._parse_postal(text[start:nl if nl >= 0 else len(text)])[0])
        return out

    def _postal_rows(self, lg_code: str) -> Dict[str, List[Tuple[str, str]]]:
        """Town key -> [(postal code, 丁目 the row is limited to)] for one municipality; '' is the municipality-wide row."""
        by_town = self._postal_by_town.get(lg_code)
        if by_town is None:
            by_town = {}
            for ln in self._postal().lines(lg_code):
                parts = ln.split("\t")
                if len(parts) < 7 or parts[6] == "building":
                    continue
                key = parts[2] if self._keys_current() else town_key(parts[3])
                by_town.setdefault(key, []).append((parts[0], parts[8] if len(parts) > 8 else ""))
            self._postal_by_town[lg_code] = by_town
        return by_town

    def postal_codes_of_town(self, lg_code: str, town: str, chome: Optional[int] = None) -> Optional[List[str]]:
        """Postal codes Japan Post lists for a town, or None when it does not list the town.

        Japan Post names towns a little differently from MLIT, so after the town's own key the
        longest listed town its name starts with is used ('田辺西垣内' is in 田辺, '古町通9番町' in
        古町通). Where a town is split between codes, ``chome`` picks the rows that can hold that
        丁目 ('北一条西' 1–19丁目 / 20–28丁目); more than one code comes back when it cannot tell.
        """
        by_town = self._postal_rows(lg_code)
        key = town_key(town) if town else ""
        if not key:
            return None
        rows = by_town.get(key)
        if rows is None and town.startswith("字") and len(town) == 2:
            rows = by_town.get(town_key(town[1:]))      # '字東' is 東
        if rows is None:
            # A one-character town counts only when the name marks it off with 字 ('平字南町' is in 平)
            name = town[2:] if town.startswith("大字") else town
            shortest = 1 if name[1:2] == "字" else 2
            for end in range(len(key) - 1, shortest - 1, -1):
                rows = by_town.get(key[:end])
                if rows is not None:
                    break
        if rows is None:
            return None
        return sorted({code for code, _ in _rows_for_chome(rows, chome)})

    def postal_codes_for(self, lg_code: str, town: Optional[str], chome: Optional[int] = None) -> List[str]:
        """Postal codes registered for a town (the municipality-wide code when the town is not listed)."""
        codes = self.postal_codes_of_town(lg_code, town, chome) if town else None
        if codes is None:
            codes = sorted({code for code, _ in self._postal_rows(lg_code).get("", [])})
        return codes

    # ------------------------------------------------------ prefix searches
    def postal_prefix(self, digits: str, limit: int = 20) -> List[PostalRecord]:
        """Postal records whose code starts with ``digits`` (3 to 7 digits), in code order."""
        if not digits.isdigit() or not 3 <= len(digits) <= 7:
            return []
        pattern = re.compile(rf"^{digits}\d{{{7 - len(digits)}}}\t.*$", re.MULTILINE)
        found = sorted(m.group(0) for m in pattern.finditer(self._postal().text))
        return [self._parse_postal(ln)[0] for ln in found[:limit]]

    def _prefix_index(self, kind: str) -> Tuple[List[str], List[Tuple[str, str]]]:
        """Sorted (sort key, (municipality code, town name)) of every registered town, one entry per town and
        municipality, keyed by town key (kind 'key') or by reading with small kana folded (kind 'kana').
        Built once, on first use: prefix lookups are then a binary search instead of a scan of the table."""
        with self._lock:
            cached = self._prefix_indexes.get(kind)
            if cached is not None:
                return cached
            seen = set()
            pairs: List[Tuple[str, Tuple[str, str]]] = []
            text = self._towns_table().text
            pos = text.find("\n") + 1
            while pos < len(text):
                nl = text.find("\n", pos)
                nl = len(text) if nl < 0 else nl
                parts = text[pos:nl].split("\t")
                pos = nl + 1
                if len(parts) < 9:
                    continue
                item = (parts[0], parts[3])
                sort_key = parts[1] if kind == "key" else parts[8].translate(_SMALL_KANA)
                if sort_key and (sort_key, item) not in seen:
                    seen.add((sort_key, item))
                    pairs.append((sort_key, item))
            if kind == "kana":
                # Towns only Japan Post lists (often 字 in rural areas) have readings too
                ptext = self._postal().text
                pos = ptext.find("\n") + 1 if ptext.startswith("postal_code") else 0
                while pos < len(ptext):
                    nl = ptext.find("\n", pos)
                    nl = len(ptext) if nl < 0 else nl
                    parts = ptext[pos:nl].split("\t")
                    pos = nl + 1
                    if len(parts) < 7 or not parts[3] or not parts[4] or parts[6] != "town":
                        continue
                    item = (parts[1], parts[3])
                    sort_key = unicodedata.normalize("NFKC", parts[4]).translate(_SMALL_KANA)
                    if (sort_key, item) not in seen:
                        seen.add((sort_key, item))
                        pairs.append((sort_key, item))
            pairs.sort()
            index = ([k for k, _ in pairs], [v for _, v in pairs])
            self._prefix_indexes[kind] = index
            return index

    def _prefix_lookup(self, kind: str, prefix: str, prefecture_code: Optional[str], limit: int) -> List[Tuple[str, str]]:
        keys, items = self._prefix_index(kind)
        out: List[Tuple[str, str]] = []
        seen = set()
        for i in range(bisect.bisect_left(keys, prefix), len(keys)):
            if not keys[i].startswith(prefix):
                break
            item = items[i]
            if prefecture_code and not item[0].startswith(prefecture_code):
                continue
            if item not in seen:
                seen.add(item)
                out.append(item)
                if len(out) >= limit:
                    break
        return out

    def town_prefix(self, key_prefix: str, prefecture_code: Optional[str] = None,
                    limit: int = 50) -> List[Tuple[str, str]]:
        """(municipality code, registered town name) for towns whose key starts with ``key_prefix``, nationwide
        or in one prefecture. One entry per town (丁目 collapsed)."""
        if not key_prefix:
            return []
        return self._prefix_lookup("key", key_prefix, prefecture_code, limit)

    def municipalities_with_reading(self, reading: str) -> List[str]:
        """Codes of the municipalities holding a town read exactly ``reading`` (a ``kana_key``)."""
        keys, items = self._prefix_index("kana")
        reading = reading.translate(_SMALL_KANA)
        out: List[str] = []
        for i in range(bisect.bisect_left(keys, reading), bisect.bisect_right(keys, reading)):
            if items[i][0] not in out:
                out.append(items[i][0])
        return out

    def town_kana_prefix(self, reading: str, limit: int = 50) -> List[Tuple[str, str]]:
        """(municipality code, town name) for towns whose reading starts with ``reading`` (a ``kana_key``)."""
        if not reading:
            return []
        return self._prefix_lookup("kana", reading.translate(_SMALL_KANA), None, limit)

    # -------------------------------------------------------- nearest town
    def _spatial(self) -> Tuple[Dict[Tuple[int, int], List[int]], List[float], List[float], List[int]]:
        """Grid index over every town point: cell -> point numbers, plus lat, lon and line offsets."""
        with self._lock:
            if self._grid is None:
                text = self._towns_table().text
                grid: Dict[Tuple[int, int], List[int]] = {}
                lats: List[float] = []
                lons: List[float] = []
                offsets: List[int] = []
                pos = text.find("\n") + 1
                size = len(text)
                while pos < size:
                    nl = text.find("\n", pos)
                    if nl < 0:
                        nl = size
                    parts = text[pos:nl].split("\t", 8)
                    if len(parts) > 7:
                        lat, lon = float(parts[6]), float(parts[7])
                        grid.setdefault((int(lat / _CELL_DEG), int(lon / _CELL_DEG)), []).append(len(lats))
                        lats.append(lat)
                        lons.append(lon)
                        offsets.append(pos)
                    pos = nl + 1
                self._grid = (grid, lats, lons, offsets)
            return self._grid

    def nearest_towns(self, latitude: float, longitude: float, limit: int = 1,
                      max_km: float = 30.0) -> List[Tuple[float, TownRecord]]:
        """The town / 丁目 points nearest to a coordinate as (distance in metres, record), nearest first."""
        # Every registered point lies within Japan's extent; far outside it there is nothing to search
        # (and near the poles the cells' east-west size goes to zero, so the ring search would not end)
        margin = max_km / 111.0
        if not (_JAPAN_LAT[0] - margin <= latitude <= _JAPAN_LAT[1] + margin
                and _JAPAN_LON[0] - margin <= longitude <= _JAPAN_LON[1] + margin):
            return []
        grid, lats, lons, offsets = self._spatial()
        text = self._towns_table().text
        cy, cx = int(latitude / _CELL_DEG), int(longitude / _CELL_DEG)
        cos_lat = math.cos(math.radians(latitude))
        best: List[Tuple[float, int]] = []
        cell_m = _CELL_DEG * 111_000 * min(1.0, max(cos_lat, 0.5))
        ring = 0
        max_ring = int(max_km * 1000 / cell_m) + 2
        while ring <= max_ring:
            for dy in range(-ring, ring + 1):
                for dx in range(-ring, ring + 1):
                    if max(abs(dy), abs(dx)) != ring:
                        continue
                    for i in grid.get((cy + dy, cx + dx), ()):
                        d = math.hypot((lats[i] - latitude) * 111_320, (lons[i] - longitude) * 111_320 * cos_lat)
                        best.append((d, i))
            best.sort()
            del best[max(limit, 8):]
            # Points in rings not yet visited are at least ring * cell away
            if len(best) >= limit and best[limit - 1][0] <= ring * cell_m:
                break
            ring += 1
        out: List[Tuple[float, TownRecord]] = []
        for d, i in best[:limit]:
            if d > max_km * 1000:
                break
            nl = text.find("\n", offsets[i])
            lg, _key, mid, name, chome, kind, lat, lon, kana, romaji = text[offsets[i]:nl if nl >= 0 else len(text)].split("\t")
            out.append((d, TownRecord(lg, mid, name, int(chome) if chome else None, kind,
                                      float(lat), float(lon), kana, romaji)))
        return out

    def block_points_in(self, lg_code: str) -> Dict[Tuple[str, int, int], BlockPoint]:
        """Block points of one municipality keyed by (town key, 丁目 or 0, block); empty without block data."""
        if lg_code not in self._blocks:
            self.block_point(lg_code, "", None, 0)
        return self._blocks.get(lg_code, {})

    # ---------------------------------------------------------------- blocks
    def block_dirs(self) -> List[Path]:
        dirs = [self.data_dir / "blocks", user_data_dir() / "blocks"]
        return [d for i, d in enumerate(dirs) if d not in dirs[:i]]

    def stale_block_prefectures(self) -> List[str]:
        """Prefectures whose installed block data was built with an older town key (re-fetch to refresh)."""
        stale = []
        for d in self.block_dirs():
            for meta_path in sorted(d.glob("*.json")) if d.exists() else ():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                if meta.get("town_key_version") != TOWN_KEY_VERSION and meta_path.stem not in stale:
                    stale.append(meta_path.stem)
        return stale

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
            # A file built by an older version stores older town keys. Most keys are unchanged and points
            # are filed per municipality, so it is still used; towns whose key changed are simply not found
            # until the prefecture is fetched again (`jaden data info` lists such files).
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


_GAZETTEER_LOCK = threading.Lock()


def get_gazetteer() -> Gazetteer:
    global _GAZETTEER
    if _GAZETTEER is None:
        with _GAZETTEER_LOCK:
            if _GAZETTEER is None:
                _GAZETTEER = Gazetteer()
    return _GAZETTEER


def reset_gazetteer() -> None:
    """Drops the cached gazetteer so the next call reloads (used after ``jaden data update``)."""
    global _GAZETTEER
    _GAZETTEER = None
