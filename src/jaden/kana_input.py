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
_KANA_HEAD = re.compile(r"^(?P<postal>\s*(?:〒\s*)?\d{3}\s*-?\s*\d{4}\s+)?(?P<head>[ぁ-ゖァ-ヺー・\s]{4,}?)(?=[\d\s]*\d|$)")
_INDEX: Optional[Tuple[List[Tuple[str, str]], Dict[str, List[Any]]]] = None


def _katakana(text: str) -> str:
    """NFKC, no spaces, hiragana as katakana: the same length as kana_key(text), small kana kept."""
    s = unicodedata.normalize("NFKC", text).replace(" ", "").replace("・", "")
    return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def _index() -> Tuple[List[Tuple[str, str]], Dict[str, List[Any]]]:
    """(prefecture reading, name) pairs and municipality records by reading (with and without the county)."""
    global _INDEX
    if _INDEX is None:
        from .data.loader import get_registry
        from .lookup import _muni_kana
        registry = get_registry()
        prefs = sorted(((kana_key(p.kana), p.name) for p in registry.list_all_prefectures() if p.kana),
                       key=lambda x: -len(x[0]))
        munis: Dict[str, List[Any]] = {}
        for m in registry.list_municipalities():
            reading = kana_key(_muni_kana(m))
            if not reading:
                continue
            munis.setdefault(reading, []).append(m)
            if m.county and "グン" in reading[:-2]:
                munis.setdefault(reading[reading.index("グン") + 2:], []).append(m)   # county left out
        _INDEX = (prefs, munis)
    return _INDEX


def looks_kana(text: str) -> bool:
    return bool(text) and _KANA_HEAD.match(unicodedata.normalize("NFKC", text)) is not None


def kana_to_japanese(text: str, read: Callable[[str], Any]) -> Optional[Tuple[str, List[str]]]:
    """The address with its prefecture and municipality in kanji, and a note; None when the kana does not
    start with a municipality (or a prefecture and a municipality). ``read`` normalizes a candidate, to
    choose between municipalities that share a reading."""
    text = unicodedata.normalize("NFKC", text)
    m = _KANA_HEAD.match(text)
    if m is None:
        return None
    postal, head = m.group("postal") or "", m.group("head")
    rest_text = text[m.end("head"):]
    kata = _katakana(head)
    key = kana_key(head)
    prefs, munis = _index()

    pref_name, start = "", 0
    for reading, name in prefs:
        if key.startswith(reading):
            pref_name, start = name, len(reading)
            break
    # The longest municipality reading the rest starts with
    found: List[Any] = []
    length = 0
    for end in range(len(key), start, -1):
        cands = munis.get(key[start:end], [])
        if pref_name:
            cands = [c for c in cands if c.prefecture_name == pref_name]
        if cands:
            found, length = cands, end - start
            break
    if not found:
        return None
    town = kata[start + length:]

    def written(c: Any) -> str:
        return f"{postal}{c.prefecture_name}{c.county or ''}{c.name}{town}{rest_text}"

    options = list({written(c): c for c in found})
    if len(options) > 1:
        verified = [o for o in options if read(o).components.town_verified]
        if len(verified) == 1:
            options = verified
        elif len({(c.county or "") + c.name for c in found}) == 1 and not pref_name:
            # Same name in several prefectures (府中市): leave the choice to the usual ambiguity handling
            c = found[0]
            options = [f"{postal}{c.county or ''}{c.name}{town}{rest_text}"]
        else:
            return None
    chosen = options[0]
    kanji = chosen[len(postal):len(chosen) - len(town) - len(rest_text)]
    return chosen, [f"read from kana: {kata[:start + length]} -> {kanji}"]
