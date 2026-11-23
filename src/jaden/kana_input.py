"""Addresses typed in kana from the start: 'とうきょうとちよだくかすみがせき1-2-1'.

The prefecture and municipality are read from their katakana readings (Japan Post's data); the town
stays in kana, which the engine already matches by reading. The result is the same address with the
prefecture and municipality in kanji: '東京都千代田区カスミガセキ1-2-1'.
"""

import re
import unicodedata
from typing import Any, Callable, Dict, List, Optional, Tuple

from .core.townkey import kana_key

# The part before the first number: kana (either script), the long-vowel mark, spaces and dots only
_KANA_HEAD = re.compile(r"^(?P<postal>\s*(?:〒\s*)?\d{3}\s*-?\s*\d{4}\s+)?(?P<head>[ぁ-ゖァ-ヺー・\s]{4,}?)"
                        r"(?=[\d\s]*\d|$|(?P<kanji>[\u3400-\u9fff々〆ヶ]))")
_INDEX: Optional[Tuple[List[Tuple[str, str]], Dict[str, List[Tuple[Any, bool]]]]] = None


def _katakana(text: str) -> str:
    """NFKC, no spaces, hiragana as katakana: the same length as kana_key(text), small kana kept."""
    s = unicodedata.normalize("NFKC", text).replace(" ", "").replace("・", "")
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def _index() -> Tuple[List[Tuple[str, str]], Dict[str, List[Tuple[Any, bool]]]]:
    """(prefecture reading, name) pairs, and (municipality record, county written) by reading: a town or
    village is listed with its county reading and without it."""
    global _INDEX
    if _INDEX is None:
        from .data.loader import get_registry
        from .lookup import _muni_kana
        registry = get_registry()
        prefs = sorted(((kana_key(p.kana), p.name) for p in registry.list_all_prefectures() if p.kana),
                       key=lambda x: -len(x[0]))
        munis: Dict[str, List[Tuple[Any, bool]]] = {}
        for m in registry.list_municipalities():
            reading = kana_key(_muni_kana(m))
            if not reading:
                continue
            with_county = bool(m.county) and "グン" in reading[:-2]
            munis.setdefault(reading, []).append((m, with_county))
            if with_county:
                munis.setdefault(reading[reading.index("グン") + 2:], []).append((m, False))   # county left out
        _INDEX = (prefs, munis)
    return _INDEX


def looks_kana(text: str) -> bool:
    return bool(text) and _KANA_HEAD.match(unicodedata.normalize("NFKC", text)) is not None


_SMALL = str.maketrans("ァィゥェォッャュョヮヵヶ", "アイウエオツヤユヨワカケ")
# Number words typed in kana after a number: 2ちょうめ -> 2丁目 (only after a digit, so names are untouched)
_KANA_MARKERS = [(re.compile(r"(?<=\d)(?:ちょうめ|チョウメ)"), "丁目"), (re.compile(r"(?<=\d)(?:ばんち|バンチ)"), "番地"),
                 (re.compile(r"(?<=\d)(?:ばん|バン)(?!ち|チ)"), "番"), (re.compile(r"(?<=\d)(?:ごう|ゴウ)"), "号"),
                 (re.compile(r"(?<=\d)(?:じょう|ジョウ)"), "条"), (re.compile(r"(?<=\d)(?:のう|ノウ)"), "の")]
_HAS_KANA = re.compile(r"[ァ-ヺ]")


def _fold(text: str) -> str:
    """Hiragana as katakana and small kana as large, character by character (same length as the input)."""
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in text).translate(_SMALL)


def _town_by_reading(lg_code: str, rest: str) -> Optional[Tuple[str, int, Tuple[str, ...]]]:
    """(registered town name, characters of ``rest`` it covers, ()) for the longest town of the municipality
    whose reading ``rest`` starts with; readings include their numbers ('キタ10ジヨウニシ' is 北十条西).
    When that reading belongs to several towns there ('ソガワ': 楚川 and 曽川): ('', 0, their names)."""
    from .data.gazetteer import get_gazetteer
    gaz = get_gazetteer()
    if not gaz.available:
        return None
    index = gaz.towns_by_kana(lg_code)
    folded = _fold(rest)
    for length in range(min(len(folded), 40), 0, -1):
        entries = index.get(folded[:length])
        if not entries:
            continue
        if not _boundary_ok(folded, length):
            continue        # the reading would end inside a word or a number
        names = {e.name for e in entries}
        kanji = {n for n in names if not re.fullmatch(r"[ぁ-ゖァ-ヺー]+", n)}
        names = kanji or names          # 'たけくま' listed beside 字武隈 is its reading, not another town
        bare = {re.sub(r"^(?:大字|字)", "", n) for n in names}   # 字武隈 and 武隈 are one town
        if len(bare) == 1:
            return min(names, key=len), length, ()
        return "", 0, tuple(sorted(bare))
    return None


def get_gazetteer_readings(reading: str, except_lg: str) -> List[str]:
    """Municipalities other than ``except_lg`` holding a town read ``reading`` (with or without 町)."""
    from .data.gazetteer import get_gazetteer
    gaz = get_gazetteer()
    if not gaz.available:
        return []
    out: List[str] = []
    for r in {reading, reading[:-3] if reading.endswith("チヨウ") else reading,
              reading[:-2] if reading.endswith("マチ") else reading}:
        out += [lg for lg in gaz.municipalities_with_reading(r) if lg != except_lg and lg not in out]
    return out


def _boundary_ok(folded: str, length: int) -> bool:
    nxt = folded[length:length + 1]
    return not (nxt and ((nxt.isdigit() and folded[length - 1].isdigit()) or nxt in "ーンッ" or
                         (_HAS_KANA.match(nxt) and _HAS_KANA.match(folded[length - 1]))))


def _town_anywhere(rest: str) -> Optional[Tuple[str, int]]:
    """(town name, characters covered) for the longest registered town reading ``rest`` starts with, anywhere
    in Japan, when every town with that reading has the same name (the kanji is then what was meant);
    None when the reading belongs to differently written towns (あさひ: 旭, 朝日, あさひ町)."""
    from .data.gazetteer import get_gazetteer
    gaz = get_gazetteer()
    if not gaz.available:
        return None
    folded = _fold(rest)
    keys, items = gaz._prefix_index("kana")
    import bisect
    for length in range(min(len(folded), 40), 1, -1):
        reading = folded[:length]
        lo, hi = bisect.bisect_left(keys, reading), bisect.bisect_right(keys, reading)
        if lo == hi or not _boundary_ok(folded, length):
            continue
        names = {items[i][1] for i in range(lo, hi)}
        return (next(iter(names)), length) if len(names) == 1 else None
    return None


def kana_to_japanese(text: str, read: Callable[[str], Any]) -> Optional[Tuple[str, List[str]]]:
    """The address with its prefecture, municipality and town in kanji, and a note; None unless the kana
    starts with a municipality (after an optional prefecture) followed by a town registered there (or by
    numbers only). ``read`` normalizes a candidate, to choose between municipalities that share a reading."""
    text = unicodedata.normalize("NFKC", text)
    m = _KANA_HEAD.match(text)
    if m is None:
        return None
    postal, head = m.group("postal") or "", m.group("head")
    kata = _katakana(head)
    rest_all = kata + text[m.end("head"):]          # town, numbers and building, after the municipality
    key = kana_key(head)
    prefs, munis = _index()

    pref_name, start = "", 0
    for reading, name in prefs:
        if key.startswith(reading):
            pref_name, start = name, len(reading)
            break
    # Every municipality reading the text starts with, longest first, each with the town that follows it
    # The kanji is written the way the kana was typed (prefecture and county only when typed), so the
    # engine treats it exactly as it treats the same address typed in kanji
    options: Dict[str, Tuple[Any, str, int]] = {}
    notes_for: Dict[str, str] = {}
    if m.group("kanji") and pref_name and start == len(key):
        # Only the prefecture in kana ('とうきょうと港区…'): the kanji that follows is read as usual
        return f"{postal}{pref_name}{text[m.end('head'):]}", [f"read from kana: {head.strip()} -> {pref_name}"]
    # Kana then a kanji town ('おおさかふおおさかしきたく梅田'): the kana must be exactly the prefecture
    # and municipality, so a name that merely starts like one ('さくら銀行') is never read as an address
    lowest = len(key) - 1 if m.group("kanji") else start
    for end in range(len(key), lowest, -1):
        cands = munis.get(key[start:end], [])
        if pref_name:
            cands = [(c, k) for c, k in cands if c.prefecture_name == pref_name]
        rest = rest_all[end:]
        for c, county_typed in cands:
            if not _HAS_KANA.search(_fold(rest.split(" ")[0] if rest else "")):
                town, used = "", 0                           # numbers only: nothing to verify
                if not pref_name and get_gazetteer_readings(key[start:end], c.lg_code):
                    continue    # 'かみちょう1-2' is 香美町, but also every town read カミチョウ (上町, 神町)
            else:
                hit = _town_by_reading(c.lg_code, rest)
                if hit is None:
                    continue
                town, used, homophones = hit
                if homophones:
                    notes_for[c.lg_code] = (f"the town reading matches {len(homophones)} towns here "
                                            f"({', '.join(homophones)}); it is left in kana")
            tail = rest[used:]
            for pattern, word in _KANA_MARKERS:
                tail = pattern.sub(word, tail)
            written = f"{postal}{pref_name}{c.county if county_typed else ''}{c.name}{town}{tail}"
            options.setdefault(written, (c, town, end))
        if options:
            break                                            # the longest municipality reading that works
    if not options and not pref_name and not m.group("kanji"):
        # No municipality: a town alone, written in kanji when its reading has one spelling in Japan
        anywhere = _town_anywhere(rest_all)
        if anywhere is not None:
            town, used = anywhere
            tail = rest_all[used:]
            for pattern, word in _KANA_MARKERS:
                tail = pattern.sub(word, tail)
            written = f"{postal}{town}{tail}"
            res = read(written)
            if res.components.lg_code and not res.components.is_ambiguous:
                return written, [f"read from kana: {head.strip()} -> {town}"]
            return None     # still several places: the text stays as typed
    if not options:
        return None
    if len(options) > 1:
        verified = [o for o in options if read(o).components.town_verified]
        names = {(c.county or "") + c.name for c, _, _ in options.values()}
        if len(verified) == 1:
            options = {verified[0]: options[verified[0]]}
        elif len(names) == 1:
            pass        # one spelling (with and without its county): the engine's ambiguity handling decides
        else:
            return None
    chosen, (c, town, end) = next(iter(options.items()))
    kanji = chosen[len(postal):]
    kanji = kanji[:kanji.index(c.name, len(pref_name)) + len(c.name)] + town
    notes = [f"read from kana: {head.strip()} -> {kanji}"]
    if c.lg_code in notes_for:
        notes.append(notes_for[c.lg_code])
    return chosen, notes


def admin_fields_to_kanji(prefecture: str, city: str) -> Tuple[str, str]:
    """Form fields typed in kana ('とうきょうと', 'みなとく' or 'とうきょうとみなとく') in kanji; a field
    that is not kana, or whose reading is not one prefecture / one spelling of a municipality, is kept."""
    prefs, munis = _index()
    kana = re.compile(r"[ぁ-ゖァ-ヺー・\s]+")
    pref_name = prefecture
    if prefecture and kana.fullmatch(prefecture):
        pref_name = next((name for reading, name in prefs if kana_key(prefecture) == reading), prefecture)
    if not city or not kana.fullmatch(city):
        return pref_name, city
    key = kana_key(city)
    for reading, name in prefs:
        if key.startswith(reading) and len(key) > len(reading):
            key = key[len(reading):]
            pref_name = pref_name or name
            break
    cands = munis.get(key, [])
    if pref_name:
        cands = [(c, k) for c, k in cands if c.prefecture_name == pref_name] or cands
    spellings = {(c.county if k else "") + c.name for c, k in cands}
    return pref_name, (next(iter(spellings)) if len(spellings) == 1 else city)


def kana_town_in(municipalities: List[Any], text: str) -> Optional[Tuple[str, str]]:
    """The text after a municipality with a town typed in kana written in kanji, when its reading (numbers
    included) names exactly one registered town of those municipalities; with a note. The number words
    after it ('4ちょうめ2ばん8ごう') are written as 丁目, 番 and 号."""
    norm = unicodedata.normalize("NFKC", text)
    hits = []
    for m in municipalities:
        hit = _town_by_reading(m.lg_code, norm)
        if hit is not None and not hit[2]:
            hits.append(hit)
    names = {h[0] for h in hits}
    if len(names) != 1:
        return None
    town, used, _ = hits[0]
    tail = norm[used:]
    for pattern, word in _KANA_MARKERS:
        tail = pattern.sub(word, tail)
    if not any(ch.isdigit() for ch in norm[:used]) and tail == norm[used:]:
        return None      # nothing the engine's own reading of the town would miss ('しばこうえん4-2-8')
    return f"{town}{tail}", f"read the kana town {norm[:used]} as {town}"
