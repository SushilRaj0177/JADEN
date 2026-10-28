"""JADEN: Romanized (Latin-script) address input.

Converts addresses written the way they appear on international mail and
English-language forms back into Japanese, using Japan Post's official
romanization of every prefecture, municipality and town:

    '4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011' -> '〒105-0011 東京都港区芝公園4-2-8'
    'Chuo-ku, Sapporo-shi, Kita 1-jo Nishi 2-chome' -> '北海道札幌市中央区北1条西2丁目'

Spelling variation is folded into one key: macrons (Chūō), doubled vowels
(Chuuou, Oosaka), 'ou' (Tokyou), m/n before b/p (Shimbashi/Shinbashi), and
English suffixes (City, Ward, Town, Village, Prefecture).
The converted string is then parsed by the normal engine, so everything the
gazetteer checks applies to romaji input too.
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple, Set, Final

from .data.gazetteer import get_gazetteer
from .data.loader import get_registry, MunicipalityRecord

_SUFFIX_WORDS: Final[Dict[str, str]] = {
    "CITY": "SHI", "SHI": "SHI", "WARD": "KU", "KU": "KU", "TOWN": "MACHI", "MACHI": "MACHI", "CHO": "CHO",
    "VILLAGE": "MURA", "MURA": "MURA", "SON": "SON", "DISTRICT": "GUN", "COUNTY": "GUN", "GUN": "GUN",
    "PREFECTURE": "", "PREF": "", "KEN": "", "FU": "", "TO": "",
}
_TOWN_SUFFIX_EQUIV: Final[Dict[str, Set[str]]] = {"MACHI": {"MACHI", "CHO"}, "CHO": {"MACHI", "CHO"},
                                                  "MURA": {"MURA", "SON"}, "SON": {"MURA", "SON"}}
_POSTAL: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{3})-?(\d{4})(?!\d)")
_NUMBERS: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z\d])(\d+)(?:\s*-?\s*chome)?(?:\s*-\s*(\d+))?(?:\s*-\s*(\d+))?(?![A-Za-z\d])", re.IGNORECASE)
_CHOME_WORD: Final[re.Pattern[str]] = re.compile(r"(\d+)\s*-?\s*chome", re.IGNORECASE)
_JO: Final[re.Pattern[str]] = re.compile(r"\b(KITA|MINAMI)\s*(\d+)\s*-?\s*JO\s*(HIGASHI|NISHI)\b", re.IGNORECASE)


def romaji_key(text: str) -> str:
    """Folds a romanized name to a comparison key ('Chūō-ku' == 'CHUO KU' == 'Chuou')."""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    s = re.sub(r"M(?=[BPM])", "N", s)
    for a, b in (("OU", "O"), ("OO", "O"), ("UU", "U"), ("AA", "A"), ("EE", "E"), ("II", "I")):
        s = s.replace(a, b)
    return s


def looks_romanized(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    latin = sum(unicodedata.normalize("NFKD", c)[0].isascii() for c in letters)
    return bool(letters) and latin / len(letters) > 0.8


class _RomajiIndex:
    def __init__(self) -> None:
        import json
        from .data.gazetteer import resolve_data_dir
        from pathlib import Path
        reg = get_registry()
        self.prefectures: Dict[str, str] = {}
        for p in reg.list_all_prefectures():
            self.prefectures[romaji_key(p.romaji)] = p.code
        self.prefectures[romaji_key("Hokkaidō")] = "01"
        readings: Dict[str, Dict[str, str]] = {}
        for d in (resolve_data_dir(), Path(__file__).parent / "data"):
            path = d / "municipality_readings.json"
            if path.exists():
                readings = json.loads(path.read_text(encoding="utf-8"))
                break
        # Each municipality is indexed by its full romaji ('SAPPORO SHI CHUO KU'), its last
        # unit ('CHUO KU') and its last unit with the English suffix forms ('CHUO WARD')
        self.munis: Dict[str, Set[str]] = {}
        for lg, r in readings.items():
            words = r.get("romaji", "").split()
            if not words:
                continue
            units = _units(words)
            for i in range(len(units)):
                for form in _suffix_forms(units[i:]):
                    self.munis.setdefault(form, set()).add(lg)
            self.munis.setdefault(romaji_key(" ".join(words)), set()).add(lg)
            muni = reg.get_municipality_by_code(lg)
            last = units[-1]
            if len(units) >= 2 and units[0][-1] == "GUN":
                # 'Menashi-gun' on its own narrows to the towns of that county
                self.munis.setdefault(romaji_key(" ".join(units[0])), set()).add(lg)
            # Bare names ('Sapporo', 'Minato'); Tokyo's special wards call themselves 'X City' in English
            self.munis.setdefault(romaji_key(last[0]), set()).add(lg)
            if muni is not None and muni.entity_type == "special_ward":
                self.munis.setdefault(romaji_key(last[0] + "SHI"), set()).add(lg)
            if muni is not None and muni.entity_type == "administrative_ward" and len(units) >= 2:
                # 'Osaka City' or 'Osaka' next to 'Kita Ward' narrows the ward to the right city
                for form in [romaji_key(units[0][0])] + _suffix_forms(units[:1]):
                    self.munis.setdefault(form, set()).add(lg)
        self.registry = reg
        self._towns: Dict[str, Dict[str, str]] = {}

    def town_entries(self, lg: str) -> Dict[str, str]:
        cached = self._towns.get(lg)
        if cached is not None:
            return cached
        out: Dict[str, str] = {}
        self._towns[lg] = out
        for entry in get_gazetteer().towns_in(lg).values():
            if entry.romaji:
                out.setdefault(romaji_key(entry.romaji), entry.name)
                out.setdefault(romaji_key(entry.romaji.replace("-", " ")), entry.name)
        return out


def _units(words: List[str]) -> List[List[str]]:
    """['SAPPORO','SHI','CHUO','KU'] -> [['SAPPORO','SHI'], ['CHUO','KU']]"""
    units: List[List[str]] = []
    for w in words:
        if w in ("SHI", "KU", "GUN", "MACHI", "CHO", "MURA", "SON") and units:
            units[-1].append(w)
        else:
            units.append([w])
    return units


def _suffix_forms(units: List[List[str]]) -> List[str]:
    """Keys for a run of units, including with the town/village suffix variants (CHO/MACHI, SON/MURA)."""
    forms = [""]
    for unit in units:
        name, suffix = unit[0], (unit[1] if len(unit) > 1 else "")
        alts = _TOWN_SUFFIX_EQUIV.get(suffix, {suffix})
        forms = [f + romaji_key(name + s) for f in forms for s in alts]
    return forms


_INDEX: Optional[_RomajiIndex] = None


def _index() -> _RomajiIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = _RomajiIndex()
    return _INDEX


def _segment_keys(segment: str) -> List[str]:
    words = [w for w in re.split(r"[\s\-]+", segment) if w]
    upper = [w.upper() for w in words]
    mapped = []
    for w in upper:
        if w in _SUFFIX_WORDS:
            if _SUFFIX_WORDS[w]:
                mapped.append(_SUFFIX_WORDS[w])
        else:
            mapped.append(w)
    keys = [romaji_key(" ".join(mapped))]
    if mapped and mapped[-1] in _TOWN_SUFFIX_EQUIV:
        for alt in _TOWN_SUFFIX_EQUIV[mapped[-1]]:
            keys.append(romaji_key(" ".join(mapped[:-1] + [alt])))
    return keys


def romaji_to_japanese(text: str) -> Optional[Tuple[str, List[str]]]:
    """Rewrites a romanized address in Japanese; returns (japanese, notes) or None if unrecognized."""
    if not looks_romanized(text):
        return None
    idx = _index()
    work = unicodedata.normalize("NFKC", text)
    notes: List[str] = []

    postal = None
    m = _POSTAL.search(work)
    if m:
        postal = f"{m.group(1)}-{m.group(2)}"
        work = work[:m.start()] + " " + work[m.end():]
    work = re.sub(r"\bJAPAN\b", " ", work, flags=re.IGNORECASE)

    grid = _JO.search(work)
    grid_text = None
    if grid:
        ns = "北" if grid.group(1).upper() == "KITA" else "南"
        ew = "東" if grid.group(3).upper() == "HIGASHI" else "西"
        grid_text = f"{ns}{grid.group(2)}条{ew}"
        work = work[:grid.start()] + " " + work[grid.end():]

    numbers: List[int] = []
    explicit_chome = bool(_CHOME_WORD.search(work))
    nm = _NUMBERS.search(work)
    town_segment_marker = "\x00"
    if nm:
        numbers = [int(g) for g in nm.groups() if g]
        # The segment holding the house numbers names the town ('4-17-3 Minami'), even when that
        # town shares its name with a ward or city (南区, 中央区, 高知)
        work = work[:nm.start()] + town_segment_marker + work[nm.end():]

    segments = [s.strip() for s in re.split(r"[,/、]", work) if s.strip()]
    if len(segments) == 1:
        segments = _split_words(segments[0].replace(town_segment_marker, " "), idx)
    town_segments = {i for i, s in enumerate(segments) if town_segment_marker in s}
    segments = [s.replace(town_segment_marker, " ").strip() for s in segments]
    pref_code: Optional[str] = None
    muni_lgs: Optional[Set[str]] = None
    explicit_muni = False
    leftovers: List[str] = []
    for i, seg in enumerate(segments):
        if i in town_segments and seg:
            leftovers.append(seg)
            continue
        if not seg:
            continue
        keys = _segment_keys(seg)
        if pref_code is None and any(k in idx.prefectures for k in keys):
            pref_code = next(idx.prefectures[k] for k in keys if k in idx.prefectures)
            continue
        found = set().union(*(idx.munis.get(k, set()) for k in keys))
        if found:
            words = re.split(r"[\s\-]+", seg.upper())
            if words and words[-1] in _SUFFIX_WORDS and _SUFFIX_WORDS[words[-1]]:
                explicit_muni = True
            muni_lgs = found if muni_lgs is None else (muni_lgs & found or muni_lgs | found)
            continue
        leftovers.append(seg)

    if muni_lgs is None:
        return None
    if pref_code:
        muni_lgs = {lg for lg in muni_lgs if lg[:2] == pref_code} or muni_lgs

    # Town: try each leftover segment within the remaining municipalities
    town_name = grid_text
    town_lgs = set(muni_lgs)
    building: List[str] = []
    for seg in leftovers:
        hits = {}
        for lg in muni_lgs:
            names = idx.town_entries(lg)
            for k in _segment_keys(seg):
                if k in names:
                    hits[lg] = names[k]
        if hits and town_name is None:
            town_lgs = set(hits)
            names_found = set(hits.values())
            town_name = names_found.pop() if len(names_found) == 1 else None
            if town_name is None:
                notes.append(f"romaji town '{seg}' matches several spellings")
        else:
            building.append(seg)
    if len(town_lgs) < len(muni_lgs):
        muni_lgs = town_lgs
    if town_name is None and not explicit_muni:
        # A bare word that happens to romanize like a city ('USA' -> 宇佐市) is not enough
        return None

    # Prefer the most specific municipality record when a city and its wards both matched
    records = [r for r in (idx.registry.get_municipality_by_code(lg) for lg in sorted(muni_lgs)) if r]
    if len(records) > 1:
        wards = [r for r in records if r.entity_type == "administrative_ward"]
        if wards and len(wards) == 1:
            records = wards
    if len(records) != 1:
        # Several municipalities share this romanization: write the shared name and let the engine report it
        name = _common_name(records)
        if name is None:
            return None
        head = name
    else:
        r = records[0]
        head = r.prefecture_name + (r.county or "") + r.name

    num = ""
    if numbers:
        rest = "-".join(str(n) for n in numbers[1:])
        num = f"{numbers[0]}丁目{rest}" if explicit_chome else "-".join(str(n) for n in numbers)
    japanese = f"{'〒' + postal + ' ' if postal else ''}{head}{town_name or ''}{num}"
    if building:
        japanese += " " + " ".join(building)
    notes.insert(0, f"romaji input read as '{japanese}'")
    return japanese, notes


def _split_words(text: str, idx: "_RomajiIndex") -> List[str]:
    """Splits a comma-less address ('Shibakoen Minato-ku Tokyo') into the longest known units."""
    words = text.split()
    out: List[str] = []
    pending: List[str] = []
    i = 0
    while i < len(words):
        for n in range(min(3, len(words) - i), 0, -1):
            chunk = " ".join(words[i:i + n])
            keys = _segment_keys(chunk)
            if any(k in idx.prefectures or k in idx.munis for k in keys):
                if pending:
                    out.append(" ".join(pending))
                    pending = []
                out.append(chunk)
                i += n
                break
        else:
            pending.append(words[i])
            i += 1
    if pending:
        out.append(" ".join(pending))
    return out


def _common_name(records: List[MunicipalityRecord]) -> Optional[str]:
    names = {r.name for r in records}
    return names.pop() if len(names) == 1 else None
