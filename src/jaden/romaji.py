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
from typing import Any, Dict, List, Optional, Tuple, Set, Final

from .data.gazetteer import get_gazetteer
from .data.loader import get_registry, MunicipalityRecord

_SUFFIX_WORDS: Final[Dict[str, str]] = {
    "CITY": "SHI", "SHI": "SHI", "SI": "SHI", "WARD": "KU", "KU": "KU", "TOWN": "MACHI", "MACHI": "MACHI", "CHO": "CHO",
    "CHOU": "CHO", "TYO": "CHO", "TYOU": "CHO",
    "VILLAGE": "MURA", "MURA": "MURA", "SON": "SON", "DISTRICT": "GUN", "COUNTY": "GUN", "GUN": "GUN",
    "PREFECTURE": "", "PREF": "", "KEN": "", "FU": "", "TO": "",
}
_TOWN_SUFFIX_EQUIV: Final[Dict[str, Set[str]]] = {"MACHI": {"MACHI", "CHO"}, "CHO": {"MACHI", "CHO"},
                                                  "MURA": {"MURA", "SON"}, "SON": {"MURA", "SON"}}
# Japanese script (kana, kanji, full-width): Latin letters with macrons ('Chūō') are not Japanese
_JA: Final[str] = "[\u3000-\u30ff\u3400-\u9fff\uf900-\ufaff\uff00-\uffef\U00020000-\U0003ffff]"
_POSTAL: Final[re.Pattern[str]] = re.compile(r"(?<!\d)(\d{3})-?(\d{4})(?!\d)")
_LATIN_MUNICIPALITY: Final[re.Pattern[str]] = re.compile(
    r"(?:^|[,\s])[A-Za-z]+(?:-|\s+)(?:shi|si|ku|machi|cho|tyo|mura|son|gun|city|ward|town|village)(?=[\s,]|$)",
    re.IGNORECASE)


def romaji_key(text: str) -> str:
    """Folds a romanized name to a comparison key ('Chūō-ku' == 'CHUO KU' == 'Chuou')."""
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c)).upper()
    s = re.sub(r"[^A-Z0-9]", "", s)
    s = re.sub(r"M(?=[BPM])", "N", s)
    s = re.sub(r"OH(?=[^AEIOU]|$)", "O", s)          # 'Ohyama', 'Ohno': Hepburn's long o
    # Hepburn folded to Kunrei, so 'Hamamatu', 'Tyuo', 'Sinzyuku', 'Kisaradu' meet 'Hamamatsu', 'Chuo', …
    for a, b in (("TSU", "TU"), ("SHI", "SI"), ("CHI", "TI"), ("FU", "HU"), ("SH", "SY"), ("CH", "TY"),
                 ("JI", "ZI"), ("J", "ZY"), ("DU", "ZU"), ("DI", "ZI")):
        s = s.replace(a, b)
    for a, b in (("OU", "O"), ("OO", "O"), ("UU", "U"), ("AA", "A"), ("EE", "E"), ("II", "I")):
        s = s.replace(a, b)
    return s


def looks_romanized(text: str) -> bool:
    # A building name in Japanese before the English address ('グランドメゾン芝公園 #302, 4-2-8 Shibakoen,
    # Minato-ku, Tokyo', JADEN's own English line) does not make it Japanese
    parts = re.split(r"[,、]", unicodedata.normalize("NFKC", text))
    while len(parts) > 1 and re.match(r"\s*" + _JA, parts[0]):
        parts = parts[1:]
    while len(parts) > 1 and re.match(r"\s*" + _JA, parts[-1]):
        parts = parts[:-1]                    # … and one written last ('…, Chiba, ソレイユの丘佐倉')
    text = ",".join(parts)
    # Also without commas: 'パシフィックスクエア代々木 3F 3-1-11 Yoyogi Shibuya-ku Tokyo'
    rest = re.sub(rf"^(?:\s*\S*{_JA}\S*)+", "", text)
    if re.search(r"[A-Za-z]", rest):
        text = rest
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
        self._pref_lgs: Dict[str, List[str]] = {}

    def registry_lgs(self, pref: str) -> List[str]:
        """Every municipality code of a prefecture."""
        cached = self._pref_lgs.get(pref)
        if cached is None:
            cached = sorted({lg for lgs in self.munis.values() for lg in lgs if lg[:2] == pref})
            self._pref_lgs[pref] = cached
        return cached

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


_SERIES = "甲乙丙丁戊己庚辛壬癸イロハニホヘトチリヌルヲワカヨタレソツネナラム右左"
_END = r"(?=[\s,]|$)"
# Pieces of the part below the municipality, tried in this order at each position
_T_GRID: Final[re.Pattern[str]] = re.compile(
    r"(KITA|MINAMI)\s*(\d+)\s*(?:-?\s*(?:JO|ZYO)\s*-?\s*(HIGASHI|HIGASI|NISHI|NISI)(?:\s*(\d+)\s*-?\s*(?:CHOME|TYOME))?"
    r"|(HIGASHI|HIGASI|NISHI|NISI)\s*(\d+)(?:\s*-?\s*(?:CHOME|TYOME))?)" + _END, re.IGNORECASE)   # also 'Kita 8 Nishi 5'
_T_ROOM: Final[re.Pattern[str]] = re.compile(
    r"(?:#|(?:Room|Rm\.?|Apt\.?|Apartment|Unit|Suite)\s*#?)\s*(\d{1,5}(?:-\d{1,4})*[A-Za-z]?|[A-Za-z](?:-?\d{1,4})?)" + _END,
    re.IGNORECASE)
_T_FLOOR: Final[re.Pattern[str]] = re.compile(
    r"(?:(B)?(\d{1,2})\s*F|F(\d{1,2})(?=[\s,]|$)|(\d{1,2})(?:st|nd|rd|th)\s*(?:Fl\.?|Floor)|(?:Floor|Fl\.?)\s*(\d{1,2}))" + _END,
    re.IGNORECASE)
_T_CHOME: Final[re.Pattern[str]] = re.compile(
    r"(\d+)\s*-?\s*(?:chome|choume|tyome|tyoume)(?:\s*-\s*(?=\d)|" + _END + ")", re.IGNORECASE)
# '2-ban 15-go', '2ban 8go', '2 ban 8 go', '4-chome-2-ban-8-go'; a spaced 'go' only after a 番 ('18 Go' is 郷)
_T_BANGO: Final[re.Pattern[str]] = re.compile(
    r"(\d+)(?:\s*-\s*|)(banchi|ban|go)(?:\s*-\s*(?=\d)|" + _END + r")|(\d+)\s+(banchi|ban)" + _END, re.IGNORECASE)
_T_GO_SPACED: Final[re.Pattern[str]] = re.compile(r"(\d+)\s+(go)" + _END, re.IGNORECASE)
_T_LOT: Final[re.Pattern[str]] = re.compile(r"\d+番地(?:の?\d+)?" + _END)
_T_NUMBERS: Final[re.Pattern[str]] = re.compile(rf"\d+(?:\s*-\s*\d+)*(?:-[{_SERIES}])?" + _END)
_T_WORD: Final[re.Pattern[str]] = re.compile(r"[A-Za-z0-9\u00c0-\u024f][A-Za-z0-9\u00c0-\u024f.'&\-]*" + _END)
_ROOM_LIKE: Final[re.Pattern[str]] = re.compile(r"\d{1,5}[A-Za-z]?|[A-Za-z]-?\d{1,4}|\d{1,2}-\d{2,4}|\d{1,2}-[A-Za-z]")
_KYOTO_CLAUSE: Final[re.Pattern[str]] = re.compile(r"(?:上る|下る|上ル|下ル|東入る?|西入る?|東入ル|西入ル)(?:\d+丁目)?$")


def _tokens(seg: str) -> List[Tuple[str, Any]]:
    """The pieces of one part of the address below the municipality, in written order."""
    out: List[Tuple[str, Any]] = []
    i = 0
    while i < len(seg):
        if seg[i].isspace():
            i += 1
            continue
        after_ban = bool(out) and out[-1][0] == "bango" and "ban" in out[-1][1].group(0).lower()
        patterns = (("grid", _T_GRID), ("room", _T_ROOM), ("floor", _T_FLOOR), ("chome", _T_CHOME),
                    ("bango", _T_BANGO), ("bango", _T_GO_SPACED if after_ban else None), ("lot", _T_LOT),
                    ("numbers", _T_NUMBERS), ("word", _T_WORD))
        for kind, pattern in patterns:
            m = pattern.match(seg, i) if pattern is not None else None
            if m:
                out.append((kind, m))
                i = m.end()
                break
        else:
            word = re.match(r"\S+", seg[i:])
            if word and not re.search(_JA, word.group(0)):
                out.append(("word", _WordMatch(word.group(0))))     # '-C', 'c/o': kept with the building
                i += word.end()
                continue
            # Japanese words (a 字, a Kyoto clause, a building) up to a word in Latin letters or a lot ('424番地')
            end = i
            for w in re.finditer(r"\S+", seg[i:]):
                if not re.search(_JA, w.group(0)) or _T_LOT.fullmatch(w.group(0)):
                    break
                end = i + w.end()
            out.append(("japanese", seg[i:end].strip()))
            i = end
    return out


# A word in a building's name: long katakana, Latin letters, building words. Words of kanji alone are 字 and town
# names ('日置荘北町', '二階堂', '岩館') unless they end like an office, shop or institution ('浦川整骨院')
_BUILDING_LIKE: Final[re.Pattern[str]] = re.compile(
    r"[ァ-ヺー]{4}|[ぁ-ゖ]ー|ビル|マンション|ハウス|ハイツ|コーポ|アパート|センター|ホーム|[A-Za-z]{3}|\d+(?:F|階)$")
_KANJI_BUILDING: Final[re.Pattern[str]] = re.compile(
    r"(?:院|事務所|営業所|出張所|工場|店|店舗|会館|会社|支社|本社|局|塾|教室|署|学校|病院|薬局|寮|団地|役所|庁舎|支所|"
    r"行政局|館|荘)$")


def _is_building_word(word: str) -> bool:
    if re.fullmatch(r"[\u3400-\u9fff々〆ヶ\d]+", word):
        return bool(_KANJI_BUILDING.search(word))
    return bool(_BUILDING_LIKE.search(word))


def _split_building(japanese: str, first_is_town: bool = False) -> Tuple[str, str]:
    """('興戸御垣内 たけのこハウス') -> ('興戸御垣内', 'たけのこハウス'): Japanese written after the town is the 字 or
    town name first, then possibly a building, which a reading of the town must not swallow. With
    ``first_is_town`` the first word is the town itself ('日置荘北町三丁', a town with no romaji)."""
    words = japanese.split()
    keep: List[str] = []
    for n, w in enumerate(words):
        if (n == 0 and first_is_town) or w.startswith(("字", "大字")) or not _is_building_word(w):
            keep.append(w)
            continue
        break
    return " ".join(keep), " ".join(words[len(keep):])


class _WordMatch:
    """A Latin word the patterns do not know, shaped like a match of _T_WORD."""
    def __init__(self, text: str) -> None:
        self._text = text

    def group(self, n: int = 0) -> str:
        return self._text


def _floor_text(m: "re.Match[str]") -> str:
    if m.group(2):
        return f"{'B' if m.group(1) else ''}{m.group(2)}F"
    return f"{m.group(3) or m.group(4) or m.group(5)}F"


def _room_text(room: str) -> str:
    wing = re.fullmatch(r"(\d{1,2})-(\d{2,4}[A-Za-z]?)", room)
    return f"{wing.group(1)}棟 {wing.group(2)}号室" if wing else f"{room}号室"


def _peel(units: List[str], idx: "_RomajiIndex", from_right: bool, pref: Optional[str]
          ) -> Tuple[Optional[str], Optional[Set[str]], bool, List[str]]:
    """Takes the prefecture and municipality words off one end of the parts. Returns the prefecture code,
    the municipality codes, whether a municipality suffix was written, and the parts left (in order)."""
    parts = list(units)
    muni: Optional[Set[str]] = None
    explicit = False
    skipped = False
    while parts:
        seg = parts[-1] if from_right else parts[0]
        words = seg.split()
        taken = 0
        while taken < len(words):
            rest = words[:len(words) - taken] if from_right else words[taken:]
            edge = rest[-1] if from_right else rest[0]
            sizes = list(range(min(4, len(rest)), 0, -1))
            if re.search(r"-(?:shi|si|ku|gun|machi|cho|tyo|mura|son)$", edge, re.IGNORECASE):
                sizes = [1] + sizes[:-1]      # 'Izumi Kita Akita-shi': 秋田市 and the town 泉北, not 北秋田市
            elif edge.upper() in ("SHI", "SI", "KU", "GUN", "MACHI", "CHO", "TYO", "MURA", "SON") and len(rest) >= 2:
                sizes = [2] + [n for n in sizes if n != 2]   # 'Izumi Kita Akita shi' likewise
            for n in sizes:
                chunk_words = rest[-n:] if from_right else rest[:n]
                chunk = " ".join(chunk_words)
                if re.search(r"\d", chunk) or re.search(_JA, chunk):
                    continue          # numbers and Japanese ('字千歳森') are never the municipality
                keys = _segment_keys(chunk)
                if pref is None and muni is None and any(k in idx.prefectures for k in keys):
                    pref = next(idx.prefectures[k] for k in keys if k in idx.prefectures)
                    break
                found = set().union(*(idx.munis.get(k, set()) for k in keys))
                if pref is not None:
                    found = {lg for lg in found if lg[:2] == pref}
                if not found:
                    continue
                last = re.split(r"[\s\-]+", chunk.upper())[-1]
                suffix = bool(_SUFFIX_WORDS.get(last))
                if muni is not None and not suffix and len(chunk_words) < len(words):
                    continue   # 'Hiyoshicho Hioki, Hioki-shi': a bare name beside other words is the town's
                if muni is not None:
                    inside = muni & found
                    town = any(k in idx.town_entries(lg) for lg in inside for k in keys)
                    if not inside or (town and not suffix):
                        continue   # 'Kita' before 'Kawagoe-shi', 'Setagaya' before 'Setagaya-ku': the town
                    found = inside
                muni, explicit = found, explicit or suffix
                break
            else:
                if (pref is not None and muni is None and not skipped and len(rest) >= 2
                        and re.search(r"(?:jima|shima)$", edge, re.IGNORECASE)):
                    skipped = True        # 'Miyake-mura Miyakejima Tokyo': the island names no municipality
                    taken += 1
                    continue
                break
            taken += n
        if taken == len(words):
            parts = parts[:-1] if from_right else parts[1:]
            continue
        if taken:
            left = words[:len(words) - taken] if from_right else words[taken:]
            if from_right:
                parts[-1] = " ".join(left)
            else:
                parts[0] = " ".join(left)
        break
    return pref, muni, explicit, parts


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
    if m and work[m.end():].strip(" ,") and not re.fullmatch(r"[\s,]*japan[\s,.]*", work[m.end():], re.IGNORECASE) \
            and not re.search(r"〒\s*$", work[:m.start()]):
        m = None                       # text after it: a lot ('Aikoku 191-5711, Kushiro-shi'), not the postal code
    if m:
        postal = f"{m.group(1)}-{m.group(2)}"
        work = re.sub(r"〒\s*$", "", work[:m.start()]) + " " + work[m.end():]
    work = re.sub(r"\bJAPAN\b", " ", work, flags=re.IGNORECASE)
    # A note in brackets ('(札幌区北三条西3丁目1番地), Chuo-ku, …': an old address) holds no numbers of this address
    bracketed = re.findall(r"\([^()]*\)", work)
    work = re.sub(r"\([^()]*\)", " ", work)
    work = re.sub(r"(?<=\d)\.(?=[A-Za-z])", ", ", work)                          # '2-6-1.Tsukahara'
    work = re.sub(r"(?:(?<=[A-Za-z][A-Za-z])|(?<=\.))(?=\d{1,2}F\b)", " ", work)    # 'Bldg.18F' (not 'B2F')
    work = re.sub(r"\b(\d{1,2}F)\s*-\s*(\d{1,4}[A-Za-z]?)\b", r"\1 #\2", work)        # '4F-18': floor, room
    work = re.sub(r"(?<=[A-Za-z]{3})(?=\d+(?:-\d+)+(?=[\s,]|$))|(?<=[a-z]{3})(?=\d{3,}(?=[\s,]|$))", " ", work)
    # ('Nagaoka340-1', 'seki126'; a name stays whole: 'Belle2', 'PLAT100')
    work = re.sub(r"\bDAI\s*(\d+)\s*-?\s*GO\b", r"第\1号", work, flags=re.IGNORECASE)   # 'DAI 6GO 1-1': 第6号 then the lot
    work = re.sub(r"(?<=\d)-(?=[A-Za-z]{3})(?!jo|zyo|sen|chome|tyome|ban|go\b)", " ", work, flags=re.IGNORECASE)   # '71-Saiwai cho'
    work = re.sub(r"\b(?:oo|oh|o|ō)?aza\b[\s\-]*", "", work, flags=re.IGNORECASE)   # 'Oaza', 'Aza-', 'Ōaza': 大字, 字
    # The comma of 'マンションNO,2' belongs to the name
    work = re.sub(r"(?<=N[Oo]),(?=\d)", "\x01", work)
    segments = [s.strip().replace("\x01", ",") for s in re.split(r"[,、]", work) if s.strip()]

    # A building written last in Japanese ('…, Setagaya-ku, Tokyo, アーバニティちとふな 1F') is set aside first
    trailing: List[str] = []
    while len(segments) > 1 and re.match(_JA, segments[-1]) and not re.search(r"[A-Za-z]{3}", segments[-1]):
        trailing.insert(0, segments.pop())
    # … and any part written after the prefecture ('…, Higashiosaka-shi, Osaka, A')
    pref_at = [i for i, seg in enumerate(segments) if any(k in idx.prefectures for k in _segment_keys(seg))]
    if pref_at and pref_at[-1] >= 1 and pref_at[-1] < len(segments) - 1:
        after = segments[pref_at[-1] + 1:]
        if not any(set().union(*(idx.munis.get(k, set()) for k in _segment_keys(seg))) for seg in after) \
                and not any(re.search(r"\d+\s*-\s*\d+", seg) for seg in after):
            trailing = after + trailing
            segments = segments[:pref_at[-1] + 1]

    # Prefecture and municipality: at the end in English order, at the start in Japanese order
    pref, muni_lgs, explicit_muni, locality = _peel(segments, idx, True, None)
    left_read = _peel(segments, idx, False, None)

    def strength(read: Tuple[Optional[str], Optional[Set[str]], bool, List[str]]) -> Tuple[int, int, int]:
        return (read[1] is not None, read[2], read[0] is not None)
    if muni_lgs is None or strength(left_read) > strength((pref, muni_lgs, explicit_muni, locality)):
        # Japanese order ('Chiba, Yachiyo-shi, 55-1 Shimada'): the end holds the town, not a municipality
        if left_read[1] is not None:
            pref, muni_lgs, explicit_muni, locality = left_read
        elif muni_lgs is None and pref is not None:
            pref2, muni2, explicit2, locality2 = _peel(locality, idx, False, pref)
            if muni2 is not None:
                pref, muni_lgs, explicit_muni, locality = pref2, muni2, explicit2, locality2
    if muni_lgs is None:
        # Written in the middle ('1-1, Tokyo, Minato-ku, Shibakoen')
        rest: List[str] = []
        for seg in locality:
            p2, m2, e2, left = _peel([seg], idx, True, pref)
            if m2 is None and muni_lgs is None:
                p2, m2, e2, left = _peel([seg], idx, False, pref)   # 'Akita shi Minamidori Tsukiji'
            if m2 is not None and muni_lgs is None:
                pref, muni_lgs, explicit_muni = p2, m2, e2
                rest.extend(left)
            elif p2 is not None and pref is None and not left:
                pref = p2
            else:
                rest.append(seg)
        locality = rest
    if muni_lgs is None and pref is not None:
        # '1-2-9, Imojima, Gifu': the prefecture's word also names its city (岐阜市), the town says so
        same = {lg for k in [romaji_key(next((p.romaji for p in idx.registry.list_all_prefectures()
                                                if p.code == pref), ""))] for lg in idx.munis.get(k, set())
                if lg[:2] == pref}
        if same and any(romaji_key(seg.split()[-1]) in idx.town_entries(lg) for seg in locality if seg.split()
                        for lg in same):
            muni_lgs = same
    if muni_lgs is None and pref is not None:
        # '5-1 Nihonbashi Kabuto-cho, Tokyo': no municipality, but one municipality of the prefecture has the town
        words = [w for seg in locality for w in seg.split() if re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w)]
        owners: Set[str] = set()
        for size in range(min(3, len(words)), 0, -1):
            for a in range(0, len(words) - size + 1):
                keys = _segment_keys(" ".join(words[a:a + size]))
                owners |= {lg for lg in idx.registry_lgs(pref) for k in keys if k in idx.town_entries(lg)}
            if owners:
                break
        if len(owners) == 1:
            muni_lgs = owners
    if muni_lgs is None:
        return None

    # The parts below the municipality: a building written first in Japanese stays as written for the
    # Japanese reading to split ('グランドメゾン芝公園 #302', '5号棟101 #102', 'RJ3')
    head: List[str] = []
    while len(locality) > 1 and re.match(_JA, locality[0]):
        head.append(re.sub(_T_ROOM.pattern, lambda r: _room_text(r.group(1)), locality[0], flags=re.IGNORECASE))
        locality = locality[1:]
    pieces = [(i, kind, value) for i, seg in enumerate(locality) for kind, value in _tokens(seg)]

    grid_text: Optional[str] = None
    chome: Optional[str] = None
    bango: Dict[str, str] = {}
    lots: List[Tuple[int, str]] = []
    floor: Optional[str] = None
    rooms: List[str] = []
    number_pieces: List[Tuple[int, int, List[str]]] = []     # (position, part, numbers)
    runs: List[Tuple[int, int, List[str]]] = []              # (position, part, Latin words)
    japanese: Dict[int, Tuple[int, str]] = {}               # position -> (part, text)
    for pos, (i, kind, value) in enumerate(pieces):
        if kind == "grid":
            ns = "北" if value.group(1).upper() == "KITA" else "南"
            ew = "東" if (value.group(3) or value.group(5)).upper().startswith("HIGAS") else "西"
            grid_text = f"{ns}{value.group(2)}条{ew}"
            chome = value.group(4) or value.group(6) or chome
        elif kind == "room":
            rooms.append(value.group(1))
        elif kind == "floor":
            floor = _floor_text(value)
        elif kind == "chome":
            chome = value.group(1)
        elif kind == "bango":
            number, word = (value.group(1), value.group(2)) if value.group(1) else (value.group(3), value.group(4))
            bango[word.lower()] = number
        elif kind == "lot":
            lots.append((i, value.group(0)))
        elif kind == "numbers":
            number_pieces.append((pos, i, [p for p in re.split(r"\s*-\s*", value.group(0)) if p]))
        elif kind == "word":
            if runs and runs[-1][1] == i and runs[-1][0] == pos - 1:
                runs[-1] = (pos, i, runs[-1][2] + [value.group(0)])
            else:
                runs.append((pos, i, [value.group(0)]))
        else:
            japanese[pos] = (i, value)

    # The town: the longest run of words (or two parts, 'Yoshida, Yoshida-cho') registered in the municipality
    def town_hits(words: List[str]) -> Dict[str, Tuple[str, ...]]:
        out: Dict[str, Tuple[str, ...]] = {}
        keys = _segment_keys(" ".join(words))
        for extra in ("", "CHO", "MACHI"):          # 'Shimokurata' for 下倉田町: the 町 left out
            for lg in muni_lgs or ():
                names = idx.town_entries(lg)
                for k in keys:
                    if k + extra in names:
                        out[lg] = names[k + extra]
            if out:
                break
        return out

    number_parts = {i for _, i, n in number_pieces if len(n) > 1} | {i for i, k, _ in pieces if k in ("chome", "bango", "lot")}
    best: Optional[Tuple[Tuple[int, int, int], int, Tuple[int, int], Dict[str, Tuple[str, ...]]]] = None
    for r, (pos, i, words) in enumerate(runs):
        windows = [(a, b) for size in range(len(words), 0, -1) for a in range(0, len(words) - size + 1)
                   for b in (a + size,)]
        for a, b in windows:
            hits = town_hits(words[a:b])
            if hits:
                score = (1 if i in number_parts else 0, 1 if b - a == len(words) else 0, b - a)
                if best is None or score > best[0]:
                    best = (score, r, (a, b), hits)
                break
    # A town written over two parts: 'Yoshida, Yoshida-cho' (吉田町吉田), '88, Nishitanaka, Hakusan' (西田中白山)
    joined: Optional[Tuple[int, int, Dict[str, Tuple[str, ...]]]] = None
    for r in range(len(runs) - 1):
        (_, i1, w1), (_, i2, w2) = runs[r], runs[r + 1]
        if i2 == i1 + 1:
            hits = town_hits(w2 + w1) or town_hits(w1 + w2)
            if hits:
                joined = (r, r + 1, hits)
                break
    if joined is not None and best is not None and best[0][2] >= len(runs[joined[0]][2]) + len(runs[joined[1]][2]):
        joined = None

    town_name: Optional[str] = grid_text
    town_part: Optional[int] = None
    town_lgs = set(muni_lgs)
    building: List[Tuple[float, str]] = [(-1.0, h) for h in head]      # (position, text), kept in written order
    used_runs: Set[int] = set()
    hits = {}
    if best is not None and joined is None:
        _, r, (a, b), hits = best
        town_part = runs[r][1]
        used_runs.add(r)
        words = runs[r][2]
        extra = words[:a] + words[b:]
        if extra:
            building.append((runs[r][0], " ".join(extra)))   # 'Shibakoen Tokyo Tower': the town, then a building
    if joined is not None:
        r1, r2, hits = joined
        used_runs |= {r1, r2}
        town_part = runs[r2][1]
    town_end = None
    if best is not None and joined is None:
        town_end = runs[best[1]][0]
    elif joined is not None:
        town_end = runs[joined[1]][0]
    japanese_part = ""
    if town_end is not None and town_end + 1 in japanese and japanese[town_end + 1][0] == town_part:
        japanese_part = japanese.pop(town_end + 1)[1]   # written right after the town, in its part
    lot_tail = ""
    lot_mark = ""
    if hits and postal:
        # Two towns spelled alike (大林 / 小林): the postal code tells which one is meant
        digits = postal.replace("-", "")
        gaz = get_gazetteer()
        by_postal = {lg: tuple(n for n in names_ if digits in (gaz.postal_codes_of_town(lg, n) or ()))
                     for lg, names_ in hits.items()}
        if any(by_postal.values()):
            hits = {lg: names_ for lg, names_ in by_postal.items() if names_}
    if hits and grid_text is None:
        town_lgs = set(hits)
        names_found = {n for names_ in hits.values() for n in names_}
        written = next((n for n in sorted(names_found, key=len, reverse=True)
                        if japanese_part.startswith(n) and not n.startswith("字")), None)
        if written:
            # 'Shimizucho 清水町': two towns spelled alike, the Japanese name written after says which
            names_found, japanese_part = {written}, japanese_part[len(written):].strip()
            town_lgs = {lg for lg, names_ in hits.items() if written in names_}
        town_name = names_found.pop() if len(names_found) == 1 else None
        if town_name is None:
            notes.append(f"romaji town '{' '.join(runs[min(used_runs)][2])}' matches several spellings: "
                         f"{', '.join(sorted({n for v in hits.values() for n in v}))}")
    if town_name is not None and japanese_part:
        if re.fullmatch(rf"[{_SERIES}]\d+(?:-\d+)*", japanese_part):
            lot_tail = japanese_part           # '1-chome Aioicho 乙394': the lot comes after the 丁目
        elif _KYOTO_CLAUSE.search(japanese_part):
            town_name = japanese_part + town_name   # Kyoto's street clause goes before the town
        else:
            japanese_part, extra_building = _split_building(japanese_part)
            if extra_building:
                building.append((town_end + 1.5 if town_end is not None else 999.0, extra_building))
            town_name += japanese_part         # '8地割', '字大作平', '上野' written after the town
            if re.search(r"\d+(?:号|地割|街区)", japanese_part):
                lot_mark = "番地"               # '山泉73号 905', '仁王第3地割 65': the number after a locator is a lot
        japanese_part = ""

    # The block numbers: those written with the town, else the nearest to it
    main: Optional[Tuple[int, int, List[str]]] = None
    if number_pieces:
        anchor = town_part if town_part is not None else max(
            (i for _, i, _ in number_pieces), default=0)
        pool = [p for p in number_pieces if len(p[2]) > 1] or number_pieces   # '1412-61 My Castle 102'
        main = min(pool, key=lambda p: (abs(p[1] - anchor), p[1] > anchor, p[0]))
    unmatched_town: Optional[str] = None
    if town_name is None and town_part is None:
        # The words written with the numbers name the town, even one the registry does not hold
        home = main[1] if main is not None else None
        own = [r for r, (_, i, _) in enumerate(runs) if i == home]
        if own:
            unmatched_town = " ".join(runs[own[0]][2])
            used_runs.add(own[0])
        in_home: List[int] = [at for at, (i, _) in sorted(japanese.items()) if i == home]
        later: List[int] = [at for at in in_home if main is None or at > main[0]]
        jp_home: Optional[int] = later[0] if later else (in_home[-1] if in_home else None)   # after the numbers first
        if jp_home is not None and (main is None or jp_home > main[0] or not unmatched_town):
            jp, extra_building = _split_building(japanese.pop(jp_home)[1], first_is_town=not unmatched_town)
            if extra_building:
                building.append((jp_home + 0.5, extra_building))   # '54 興戸御垣内 たけのこハウス 2F'
            unmatched_town = f"{unmatched_town} {jp}" if unmatched_town else jp
        if unmatched_town:
            notes.append(f"romaji town '{unmatched_town}' is not in the registry")
            if re.search(r"\d+(?:号|地割|街区)", unmatched_town):
                lot_mark = "番地"
    alone = {i for i in range(len(locality)) if sum(1 for j, _, _ in pieces if j == i) == 1}
    for r, (last, i, words) in enumerate(runs):
        if r in used_runs:
            continue
        if len(words) == 1 and not rooms and _ROOM_LIKE.fullmatch(words[0]) and (i in alone or i == town_part):
            rooms.append(words[0])            # '1B, 4-2-8 Shibakoen', '4-2-8 Shibakoen 3B'
        else:
            building.append((last - len(words) + 1, " ".join(words)))
    for pos, (_, part) in sorted(japanese.items()):
        building.append((pos, part))
    if japanese_part:
        building.append((town_end + 1 if town_end is not None else 999.0, japanese_part))

    parts: List[str] = main[2] if main is not None else []
    for p in number_pieces:
        if p is main:
            continue
        text_ = "-".join(p[2])
        if not rooms and p[1] in alone and _ROOM_LIKE.fullmatch(text_):
            rooms.append(text_)               # '302, 4-2-8 Shibakoen': a room on its own
        else:
            building.append((p[0], text_))    # '12 メゾン阪南': a number with a name is part of the name
    lot: Optional[str] = None
    for i, text_ in lots:
        if lot is None and (i == town_part or main is None or i == main[1]):
            lot = text_
        else:
            building.append((min(pos for pos, (j, k, _) in enumerate(pieces) if j == i and k == "lot"), text_))
    explicit_chome = chome is not None
    if town_name is not None and chome is None and grid_text is None and len(parts) == 4 and len(town_lgs) == 1:
        # '8-3-12-23, Kiyota': Sapporo's 清田8条 takes the first number as its 条
        lg = next(iter(town_lgs))
        jo = f"{town_name}{parts[0]}条"
        hit = get_gazetteer().match_town(lg, jo)
        if hit is not None and hit.consumed >= len(jo):
            town_name, parts = jo, parts[1:]
    if chome is None and grid_text is None and len(parts) == 4:
        rooms.append(parts.pop())             # '4-2-8-101': the fourth number is the room
    elif explicit_chome and len(parts) >= 3 and parts[2].isdigit():
        rooms.append(parts.pop(2))            # '2-14-10-502' after a 丁目 written apart: 番, 号, room
    if lot is not None:
        num = lot
    elif bango:
        num = (f"{chome}丁目" if chome else "") + (f"{bango['banchi']}番地" if "banchi" in bango else "") \
            + (f"{bango['ban']}番" if "ban" in bango else "") + (f"{bango['go']}号" if "go" in bango else "")
        if parts:
            num += "-".join(parts)
    elif explicit_chome:
        num = f"{chome}丁目" + "-".join(parts) + lot_tail
    else:
        num = "-".join(parts) + lot_tail
    if num and lot_mark and not explicit_chome:
        num += lot_mark

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
        admin = name
    else:
        rec = records[0]
        admin = rec.prefecture_name + (rec.county or "") + rec.name

    town_text = town_name or (unmatched_town + ("" if re.search(_JA, unmatched_town) else " ")
                              if unmatched_town else "")
    out = f"{'〒' + postal + ' ' if postal else ''}{admin}{town_text}{num}"
    trailing = [re.sub(_T_ROOM.pattern, lambda r: _room_text(r.group(1)), t, flags=re.IGNORECASE) for t in trailing]
    tail = [t for _, t in sorted(building, key=lambda b: b[0])] + trailing + ([floor] if floor else []) + [_room_text(r) for r in rooms[:1]] + rooms[1:] + bracketed
    if tail:
        out += " " + " ".join(tail)
    notes.insert(0, f"romaji input read as '{out}'")
    return out, notes


def _common_name(records: List[MunicipalityRecord]) -> Optional[str]:
    names = {r.name for r in records}
    return names.pop() if len(names) == 1 else None
