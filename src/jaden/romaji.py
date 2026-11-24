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
_LATIN_MUNICIPALITY: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[,\s])[A-Za-z]+-(?:shi|ku|machi|cho|mura|son|gun)(?=\s*(?:,|$))", re.IGNORECASE)
# The first part when the block numbers and town follow it ('Grand Maison 302, 4-2-8 Shibakoen, …')
_LEADING_BUILDING: Final[re.Pattern[str]] = re.compile(
    r"^\s*(?P<head>[^,]+?)\s*,\s*"
    r"(?=(?:\d+(?:\s*-\s*(?:\d+|chome\b))*|(?:Kita|Minami)\s*\d+[^,]*?)(?:\s+[^,]*)?,\s*[A-Za-z])", re.IGNORECASE)
_UNIT_PART: Final[re.Pattern[str]] = re.compile(
    r"(?:^|(?<=[,\s]))(?:#\s*|(?:Room|Rm|Apt|Apartment|Unit|No)\.?\s*#?\s*)(?P<room>(?:\d{1,2}-)?\d{1,5}[A-Za-z]?)(?=\s*(?:,|$))",
    re.IGNORECASE)
_KANJI_LOT: Final[re.Pattern[str]] = re.compile(r"^[甲乙丙丁戊己庚辛壬癸右左]\d+(?:-\d+)*$")
_CHOME_WORD: Final[re.Pattern[str]] = re.compile(r"(\d+)\s*-?\s*chome", re.IGNORECASE)
_JO: Final[re.Pattern[str]] = re.compile(
    r"\b(KITA|MINAMI)\s*(\d+)\s*-?\s*JO\s*(HIGASHI|NISHI)\b(?:\s*(\d+)\s*-?\s*CHOME\b)?", re.IGNORECASE)
# '1-1 Hongo 7-chome': the 丁目 written after the town, the block numbers before it
_CHOME_AFTER_TOWN: Final[re.Pattern[str]] = re.compile(r"(?<=[A-Za-z])\s+(\d+)\s*-?\s*chome\b", re.IGNORECASE)
_LEAD_NUMBERS: Final[re.Pattern[str]] = re.compile(r"^\s*(\d+(?:\s*-\s*\d+)*)\s*,?\s*(?=[A-Za-z])")
# Municipality words written in one part with no comma: 'Sakae ku Yokohama shi'
_MUNI_GROUP: Final[re.Pattern[str]] = re.compile(
    r"[A-Za-z][A-Za-z']*(?:[\s\-]+[A-Za-z][A-Za-z']*)*?[\s\-]+(?:shi|ku|gun|machi|cho|mura|son)\b", re.IGNORECASE)


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
    # A building name in Japanese before the English address ('グランドメゾン芝公園 #302, 4-2-8 Shibakoen,
    # Minato-ku, Tokyo', JADEN's own English line) does not make it Japanese
    lead = _LEADING_BUILDING.match(unicodedata.normalize("NFKC", text))
    if lead:
        text = text[lead.end():] if len(text) > lead.end() else text
    letters = [c for c in text if c.isalpha()]
    latin = sum(unicodedata.normalize("NFKD", c)[0].isascii() for c in letters)
    if not letters:
        return False
    # A romanized municipality ('Saga-shi', 'Minato-ku') marks an English line even when a town the
    # registry cannot romanize is written in Japanese inside it ('1 本庄町, Saga-shi, Saga')
    if _LATIN_MUNICIPALITY.search(text):
        return latin / len(letters) > 0.5
    return latin / len(letters) > 0.8


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
        self._towns: Dict[str, Dict[str, Tuple[str, ...]]] = {}

    def town_entries(self, lg: str) -> Dict[str, Tuple[str, ...]]:
        """Town names by romaji key. Two towns of one municipality can be spelled alike (大林 / 小林 are
        both 'Obayashi' once long vowels fold), so a key holds every name it can stand for."""
        cached = self._towns.get(lg)
        if cached is not None:
            return cached
        out: Dict[str, Tuple[str, ...]] = {}
        gaz = get_gazetteer()
        for entry in [*gaz.towns_in(lg).values(), *gaz.postal_towns_in(lg).values()]:   # Japan Post's own towns too
            if entry.romaji:
                for key in (romaji_key(entry.romaji), romaji_key(entry.romaji.replace("-", " "))):
                    if entry.name not in out.get(key, ()):
                        out[key] = out.get(key, ()) + (entry.name,)
        # Published only once complete: another thread must never see a half-filled table
        self._towns[lg] = out
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
    # English order ends with the postal code; an earlier NNN-NNNN is a lot ('321-1221 Higashiakada, …')
    found = list(_POSTAL.finditer(work))
    m = found[-1] if found else None
    if m and not work[:m.start()].strip(" ,") and work[m.end():].strip(" ,"):
        m = None                       # numbers first, then the town: a lot, not a postal code
    if m:
        postal = f"{m.group(1)}-{m.group(2)}"
        work = work[:m.start()] + " " + work[m.end():]
    work = re.sub(r"\bJAPAN\b", " ", work, flags=re.IGNORECASE)
    # A room written as its own part ('#101, 4-2-8 Shibakoen, …', 'Apt 101', 'Room 101'): the English
    # order puts it first; it is kept for the end, so its number is not read as the block
    unit = None
    head_building: Optional[str] = None
    lead = _LEADING_BUILDING.match(work)
    if lead:
        # English order puts the building and room first: 'グランドメゾン芝公園 #302, 4-2-8 Shibakoen, …'
        # The building, floor and room stay as written for the Japanese reading to split, so 'RJ3', 'ハイツ 2'
        # and '5号棟101' read the same as in Japanese; only a labelled room ('#302', 'Room 302') is marked
        head = lead.group("head").strip()

        def _room(m: "re.Match[str]") -> str:
            wing = re.fullmatch(r"(\d{1,2})-(\d{2,4}[A-Za-z]?)", m.group(1))
            return f"{wing.group(1)}棟 {wing.group(2)}号室" if wing else f"{m.group(1)}号室"
        head = re.sub(r"(?:#|\b(?:Room|Rm|Apt|Apartment|Unit)\.?\s*#?)\s*(\d{1,5}(?:-\d{1,4})*[A-Za-z]?)(?=\s|$)",
                      _room, head, flags=re.IGNORECASE)
        lone = re.fullmatch(r"(\d{1,5}[A-Za-z]?|\d{1,2}-\d{2,4})", head)   # as the Japanese reading takes a lone room
        if lone:
            head = _room(lone)                          # a room written alone: '302, 4-2-8 Shibakoen'
        head_building = head or None
        work = work[lead.end():]
    labelled = None if unit else _UNIT_PART.search(work)
    if labelled:
        unit = labelled.group("room")
        work = work[:labelled.start()] + " , " + work[labelled.end():]

    # A note in brackets ('(札幌区北三条西3丁目1番地), Chuo-ku, …': an old address) holds no numbers of this address
    bracketed = re.findall(r"\([^()]*\)", work)
    work = re.sub(r"\([^()]*\)", " ", work)

    grid = _JO.search(work)
    grid_text = None
    if grid:
        ns = "北" if grid.group(1).upper() == "KITA" else "南"
        ew = "東" if grid.group(3).upper() == "HIGASHI" else "西"
        grid_text = f"{ns}{grid.group(2)}条{ew}"
        if grid.group(4):
            grid_text += f"{grid.group(4)}丁目"     # 'Kita 1-jo Nishi 2-chome': the numbers left are 番-号
        work = work[:grid.start()] + " " + work[grid.end():]
    else:
        after = _CHOME_AFTER_TOWN.search(work)
        lead_numbers = _LEAD_NUMBERS.match(work)
        if after and lead_numbers and lead_numbers.end() <= after.start():
            lead_text = re.sub(r"\s+", "", lead_numbers.group(1))
            work = (f"{after.group(1)}-chome-{lead_text} "
                    f"{work[lead_numbers.end():after.start()]}{work[after.end():]}")

    numbers: List[int] = []
    explicit_chome = bool(_CHOME_WORD.search(work))
    town_segment_marker = "\x00"
    lot_written = re.search(r"(?<!\d)\d+番地(?:の?\d+)?", work)   # '1番地68 Seiryocho': a lot, not 1丁目68
    if lot_written:
        work = work[:lot_written.start()] + town_segment_marker + work[lot_written.end():]
    nm = None if lot_written else _NUMBERS.search(work)
    if nm:
        numbers = [int(g) for g in nm.groups() if g]
        # The segment holding the house numbers names the town ('4-17-3 Minami'), even when that
        # town shares its name with a ward or city (南区, 中央区, 高知)
        work = work[:nm.start()] + town_segment_marker + work[nm.end():]

    segments = [s.strip() for s in re.split(r"[,/、]", work) if s.strip()]
    if len(segments) == 1:
        segments = _split_words(segments[0].replace(town_segment_marker, " "), idx)
    split_segments: List[str] = []
    for seg in segments:
        groups = _MUNI_GROUP.findall(seg)
        if len(groups) >= 2 and "".join(groups).replace(" ", "") == seg.replace(" ", "") \
                and all(set().union(*(idx.munis.get(k, set()) for k in _segment_keys(g.strip()))) for g in groups):
            split_segments.extend(g.strip() for g in groups)   # 'Sakae ku Yokohama shi' is two parts
        else:
            split_segments.append(seg)
    segments = split_segments
    town_segments = {i for i, s in enumerate(segments) if town_segment_marker in s}
    deferred: Optional[int] = None
    for i in sorted(town_segments):
        if not segments[i].replace(town_segment_marker, "").strip() and i + 1 < len(segments):
            deferred = i + 1          # '1-1, Chuo, Konosu shi': the part after the numbers is the town
    segments = [s.replace(town_segment_marker, " ").strip() for s in segments]
    pref_code: Optional[str] = None
    muni_lgs: Optional[Set[str]] = None
    explicit_muni = False
    leftovers: List[str] = []
    numbered_segments: Set[str] = set()
    def _take(i: int, seg: str, deferred_pass: bool = False) -> None:
        nonlocal pref_code, muni_lgs, explicit_muni
        if i in town_segments and seg:
            leftovers.append(seg)
            numbered_segments.add(seg)
            return
        if not seg:
            return
        if i == deferred and not deferred_pass:
            return
        keys = _segment_keys(seg)
        if pref_code is None and any(k in idx.prefectures for k in keys):
            pref_code = next(idx.prefectures[k] for k in keys if k in idx.prefectures)
            return
        found = set().union(*(idx.munis.get(k, set()) for k in keys))
        if found:
            words = re.split(r"[\s\-]+", seg.upper())
            if words and words[-1] in _SUFFIX_WORDS and _SUFFIX_WORDS[words[-1]]:
                explicit_muni = True
            muni_lgs = found if muni_lgs is None else (muni_lgs & found or muni_lgs | found)
            return
        leftovers.append(seg)

    for i, seg in enumerate(segments):
        _take(i, seg)
    if deferred is not None:
        seg = segments[deferred]
        last = re.split(r"[\s\-]+", seg.upper())[-1]
        names_place = (any(k in idx.prefectures for k in _segment_keys(seg))
                       or last in {"SHI", "KU", "GUN", "MURA", "SON", "CITY", "WARD", "VILLAGE", "COUNTY", "DISTRICT"})
        inside = set().union(*(idx.munis.get(k, set()) for k in _segment_keys(seg)))
        both = inside & (muni_lgs or set())
        is_town = any(k in idx.town_entries(lg) for lg in both for k in _segment_keys(seg))   # 'Setagaya, Setagaya ku'
        if both and not is_town:
            # A municipality within the ones already named: '2277-1, Hiji-machi, Hayami-gun', '1-1, Chuo-ku, Sapporo-shi'
            muni_lgs = both
            explicit_muni = True
        elif muni_lgs is None or (names_place and not is_town):
            _take(deferred, segments[deferred], deferred_pass=True)   # no other part names the municipality
        elif segments[deferred]:
            leftovers.insert(0, segments[deferred])
            numbered_segments.add(segments[deferred])
    if muni_lgs is None:
        return None
    if pref_code:
        muni_lgs = {lg for lg in muni_lgs if lg[:2] == pref_code} or muni_lgs

    # Town: try each leftover segment within the remaining municipalities
    town_name = grid_text
    town_lgs = set(muni_lgs)
    building: List[str] = []
    unmatched_town: Optional[str] = None
    lot_tail = ""
    lot_mark = ""
    for seg in leftovers:
        # A 字 or a town without a reading is written in Japanese inside the English line
        # ('44-29 Samemachi 字大作平', '3-8-4 常磐町'): it is kept as written after the town
        split = re.match(r"^(?P<latin>(?:\d+-)?[A-Za-z][A-Za-z.'\s\-]*?)\s*(?P<rest>[^\sA-Za-z]*[^\x00-\x7f].*)?$", seg)
        latin_seg = split.group("latin").strip() if split else ("" if re.search(r"[^\x00-\x7f]", seg) else seg)
        japanese_part = (split.group("rest") or "").strip() if split else ""
        hits: Dict[str, Tuple[str, ...]] = {}
        for lg in muni_lgs:
            names = idx.town_entries(lg)
            for k in (_segment_keys(latin_seg) if latin_seg else []):
                if k in names:
                    hits[lg] = names[k]
        if hits and postal:
            # Two towns spelled alike (大林 / 小林): the postal code tells which one is meant
            from .data.gazetteer import get_gazetteer
            gaz, digits = get_gazetteer(), postal.replace("-", "")
            by_postal = {lg: tuple(n for n in names_ if digits in (gaz.postal_codes_of_town(lg, n) or ()))
                         for lg, names_ in hits.items()}
            if any(by_postal.values()):
                hits = {lg: names_ for lg, names_ in by_postal.items() if names_}
        if hits and town_name is None:
            town_lgs = set(hits)
            names_found = {n for names_ in hits.values() for n in names_}
            written = next((n for n in sorted(names_found, key=len, reverse=True) if japanese_part.startswith(n)), None)
            if written:
                # 'Shimizucho 清水町': two towns spelled alike, the Japanese name written after says which
                names_found, japanese_part = {written}, japanese_part[len(written):].strip()
                town_lgs = {lg for lg, names_ in hits.items() if written in names_}
            town_name = names_found.pop() if len(names_found) == 1 else None
            if town_name is None:
                notes.append(f"romaji town '{seg}' matches several spellings: "
                             f"{', '.join(sorted({n for v in hits.values() for n in v}))}")
            elif japanese_part and _KANJI_LOT.match(japanese_part) and numbers:
                lot_tail = japanese_part     # '1-chome Aioicho 乙394': the lot comes after the 丁目
            elif japanese_part and re.search(r"(?:上る|下る|上ル|下ル|東入る?|西入る?|東入ル|西入ル)(?:\d+丁目)?$", japanese_part):
                town_name = japanese_part + town_name   # Kyoto's street clause goes before the town
            elif japanese_part:
                town_name += japanese_part   # '8地割', '字大作平', '上野' written after the town
                if re.search(r"\d+(?:号|地割|街区)", japanese_part):
                    lot_mark = "番地"           # '山泉73号 905', '仁王第3地割 65': the number after a locator is a lot
        elif town_name is None and unmatched_town is None and seg in numbered_segments:
            # The words written with the numbers name the town, even one the registry does not hold:
            # it stays in the town's place, not after the numbers as if it were a building
            unmatched_town = seg
            notes.append(f"romaji town '{seg}' is not in the registry")
            if re.search(r"\d+(?:号|地割|街区)", seg):
                lot_mark = "番地"
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
    if lot_written:
        num = lot_written.group(0)
    elif numbers and lot_tail:
        num = f"{numbers[0]}丁目{lot_tail}" if explicit_chome else "-".join(str(n) for n in numbers) + lot_tail
    elif lot_tail:
        num = lot_tail
    elif numbers:
        rest = "-".join(str(n) for n in numbers[1:])
        num = f"{numbers[0]}丁目{rest}" if explicit_chome else "-".join(str(n) for n in numbers)
    if num and lot_mark and not explicit_chome:
        num += lot_mark
    town_text = town_name or (unmatched_town + ("" if re.search(r"[^\x00-\x7f]", unmatched_town) else " ")
                              if unmatched_town else "")
    japanese = f"{'〒' + postal + ' ' if postal else ''}{head}{town_text}{num}"
    if head_building:
        building.insert(0, head_building)
    if building:
        japanese += " " + " ".join(building)
    if bracketed:
        japanese += " " + " ".join(bracketed)
    if unit:
        japanese += f" {unit}号室"
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
