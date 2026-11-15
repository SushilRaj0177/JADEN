"""JADEN: Lookup services for forms and apps.

    lookup_postal('105-0011')        postal code -> the addresses it covers (form auto-fill)
    suggest('東京都港区芝')            partial input -> completions (autocomplete)
    reverse_geocode(35.6586, 139.7454)   coordinate -> nearest registered town / 丁目 / block

All three work offline on the bundled MLIT and Japan Post data.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from .core.sanitizer import sanitize_address_text
from .core.townkey import is_kana, kana_key, town_key
from .data.gazetteer import Gazetteer, PostalRecord, TownEntry, get_gazetteer
from .data.loader import MunicipalityRecord, get_registry
from .readings import _municipality_readings, _words

_POSTAL_INPUT = re.compile(r"^〒?\s*(\d{3})\s*-?\s*(\d{0,4})$")
_TRAILING_DIGITS = re.compile(r"^(?P<base>.*?\D)(?P<digits>\d+)(?:丁目?)?$")


@dataclass(frozen=True, slots=True)
class PostalAddress:
    """One address area a postal code covers."""
    postal_code: str             # 'NNN-NNNN'
    lg_code: str
    prefecture: str
    municipality: str            # '港区', '札幌市中央区', '西多摩郡日の出町'
    town: str                    # '' when the code covers the whole municipality
    building: Optional[str]      # for codes assigned to one large building
    kind: str                    # 'town', 'building' or 'municipality'
    address: str                 # prefecture + municipality + town: what a form should prefill
    kana: str
    romaji: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Suggestion:
    """One completion of a partly typed address."""
    text: str                    # the address so far, to put back into the input
    kind: str                    # 'prefecture', 'municipality', 'town', 'chome' or 'postal'
    lg_code: Optional[str] = None
    postal_code: Optional[str] = None
    kana: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ReverseResult:
    """The registered place nearest to a coordinate."""
    address: str                 # '東京都港区芝公園4丁目' (+ 'N番' with block data)
    level: str                   # 'block', 'chome' or 'town'
    lg_code: str
    prefecture: str
    municipality: str
    town: str
    chome: Optional[int]
    block: Optional[int]
    machiaza_id: Optional[str]
    postal_code: Optional[str]
    latitude: float              # the matched point, not the query
    longitude: float
    distance_m: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _muni_label(m: MunicipalityRecord) -> str:
    return (m.county or "") + m.name


def _format_postal(code: str) -> str:
    return f"{code[:3]}-{code[3:]}"


def _muni_kana(m: MunicipalityRecord) -> str:
    return _municipality_readings().get(m.lg_code, {}).get("kana") or unicodedata.normalize("NFKC", m.kana or "")


def _ward_kana(m: MunicipalityRecord) -> str:
    """Reading of the ward alone ('ミナトク' for 大阪市港区), '' for anything that is not a ward."""
    if not m.ward or m.ward == m.name:
        return ""
    full = kana_key(_muni_kana(m))
    for city in get_registry().find_municipalities(m.city, m.prefecture_code):
        city_kana = kana_key(unicodedata.normalize("NFKC", city.kana or ""))
        if city_kana and full.startswith(city_kana):
            return full[len(city_kana):]
    return ""


def _postal_address(gaz: Gazetteer, rec: PostalRecord) -> Optional[PostalAddress]:
    registry = get_registry()
    muni = registry.get_municipality_by_code(rec.lg_code)
    if muni is None:
        return None
    pref = registry.get_prefecture_by_code(muni.prefecture_code)
    town, building = rec.town, None
    if rec.kind == "building" and town:
        # 'town + building name' is stored joined; the registered town at its start separates them
        match = gaz.match_town(rec.lg_code, town)
        if match is not None and match.consumed < len(town) and match.entry.records:
            town, building = match.entry.name, rec.town[match.consumed:]
    readings = _municipality_readings().get(rec.lg_code, {})
    kana = (unicodedata.normalize("NFKC", pref.kana) if pref else "") + _muni_kana(muni) + rec.kana
    romaji_parts = ([" ".join(_words(rec.romaji))] if rec.romaji else []) \
        + list(reversed(_words(readings.get("romaji", "")))) + ([pref.romaji] if pref else [])
    label = _muni_label(muni)
    return PostalAddress(
        postal_code=_format_postal(rec.postal_code), lg_code=rec.lg_code, prefecture=muni.prefecture_name,
        municipality=label, town=town, building=building, kind=rec.kind,
        address=f"{muni.prefecture_name}{label}{town}", kana=kana, romaji=", ".join(p for p in romaji_parts if p),
    )


def lookup_postal(postal_code: str) -> List[PostalAddress]:
    """Addresses covered by a postal code ('105-0011', '1050011', '〒105-0011', full-width digits).

    Most codes cover one town; some cover several towns or municipalities, and codes of large
    buildings name the building. Returns [] for an unknown or malformed code.
    """
    digits = re.sub(r"[^\d]", "", unicodedata.normalize("NFKC", postal_code or ""))
    if len(digits) != 7:
        return []
    gaz = get_gazetteer()
    out = [_postal_address(gaz, rec) for rec in gaz.postal_records(digits)]
    return [p for p in out if p is not None]


# ------------------------------------------------------------------ suggest
def _town_suggestions(gaz: Gazetteer, muni: MunicipalityRecord, rest: str) -> List[Tuple[int, Suggestion]]:
    """Towns (and 丁目) of one municipality completing ``rest``; ranked (lower first)."""
    prefix_text = f"{muni.prefecture_name}{_muni_label(muni)}"
    out: List[Tuple[int, Suggestion]] = []
    entries: Dict[str, TownEntry] = {**gaz.postal_towns_in(muni.lg_code), **gaz.towns_in(muni.lg_code)}

    def add(entry: TownEntry, rank: int) -> None:
        codes = gaz.postal_codes_for(muni.lg_code, entry.name)
        out.append((rank, Suggestion(prefix_text + entry.name, "town", muni.lg_code,
                                     _format_postal(codes[0]) if len(codes) == 1 else None, entry.kana or None)))

    def add_chomes(entry: TownEntry, digits: str, base_rank: int) -> None:
        codes = gaz.postal_codes_for(muni.lg_code, entry.name)
        for n in entry.chomes:
            if str(n).startswith(digits):
                out.append((base_rank + (0 if str(n) == digits else 1) + n, Suggestion(
                    f"{prefix_text}{entry.name}{n}丁目", "chome", muni.lg_code,
                    _format_postal(codes[0]) if len(codes) == 1 else None, entry.kana or None)))

    key = town_key(rest)
    exact = entries.get(key) if rest else None
    longer = [(k, e) for k, e in entries.items() if k.startswith(key) and e is not exact]
    trailing = _TRAILING_DIGITS.match(rest)
    if trailing and exact is None:
        base_entry = entries.get(town_key(trailing.group("base")))
        if base_entry is not None and base_entry.has_chome:
            add_chomes(base_entry, trailing.group("digits"), 0)
    if is_kana(rest) and exact is None:
        reading = kana_key(rest)
        for k, hits in gaz.towns_by_kana(muni.lg_code).items():
            if k.startswith(reading):
                for entry in hits:
                    add(entry, 2 + len(k) - len(reading))
    if exact is not None:
        # '芝' is a town and also starts 芝浦, 芝公園, 芝大門: towns first, then the 丁目 of the exact one
        if longer or not exact.has_chome:
            add(exact, 0)
        if exact.has_chome:
            add_chomes(exact, "", 100 if longer else 1)
    for k, entry in longer:
        add(entry, 2 + len(k) - len(key))
    return out


def suggest(text: str, limit: int = 10) -> List[Suggestion]:
    """Completions for a partly typed address or postal code.

        suggest('東京都港区芝')    -> 東京都港区芝, 東京都港区芝浦, 東京都港区芝公園, 東京都港区芝大門
        suggest('東京都港区しば')  -> the same towns, found by their reading
        suggest('東京都港区芝公園') -> 東京都港区芝公園1丁目 ... 4丁目
        suggest('東京都み')        -> 東京都港区, 東京都三鷹市, ...
        suggest('105-00')         -> 105-0000 東京都港区, 105-0001 東京都港区虎ノ門, ...
    """
    from .engine import get_engine

    raw = unicodedata.normalize("NFKC", text or "").strip()
    if not raw:
        return []
    gaz = get_gazetteer()
    registry = get_registry()

    postal = _POSTAL_INPUT.match(raw)
    if postal:
        out = []
        for rec in gaz.postal_prefix(postal.group(1) + postal.group(2), limit=limit * 3):
            pa = _postal_address(gaz, rec)
            if pa is not None:
                out.append(Suggestion(pa.address + (pa.building or ""), "postal", pa.lg_code, pa.postal_code, pa.kana))
        return out[:limit]

    cleaned = sanitize_address_text(raw).replace(" ", "")
    admin = get_engine().admin_parser.parse(cleaned)
    rest = admin.remaining_text.replace(" ", "")
    ranked: List[Tuple[int, Suggestion]] = []

    def municipality_suggestion(m: MunicipalityRecord) -> Suggestion:
        return Suggestion(f"{m.prefecture_name}{_muni_label(m)}", "municipality", m.lg_code, None, _muni_kana(m) or None)

    def municipalities_matching(pool: List[MunicipalityRecord], part: str) -> None:
        reading = kana_key(part) if is_kana(part) else None
        for m in pool:
            names = [m.name, _muni_label(m)] + ([m.ward] if m.ward else [])
            if any(n.startswith(part) for n in names):
                ranked.append((len(m.name) - len(part), municipality_suggestion(m)))
            elif reading:
                kana = kana_key(_muni_kana(m))
                county_kana = kana_key(unicodedata.normalize("NFKC", m.kana or ""))
                if kana.startswith(reading) or county_kana.startswith(reading) or _ward_kana(m).startswith(reading):
                    ranked.append((len(kana) - len(reading), municipality_suggestion(m)))

    if admin.municipality is not None and not admin.is_contradictory:
        muni = admin.municipality
        wards = registry.wards_of(muni)
        if wards:
            municipalities_matching(wards, muni.city + rest if rest else muni.city)
            if rest:
                for w in wards:
                    ranked += _town_suggestions(gaz, w, rest)
        else:
            ranked += _town_suggestions(gaz, muni, rest)
    elif admin.is_ambiguous and admin.candidate_records:
        for cand in admin.candidate_records:
            for m in (registry.wards_of(cand) or [cand]):
                if rest:
                    ranked += _town_suggestions(gaz, m, rest)
                else:
                    ranked.append((0, municipality_suggestion(m)))
    elif admin.prefecture is not None and not admin.is_contradictory:
        pool = registry.list_municipalities(admin.prefecture.code)
        if rest:
            municipalities_matching(pool, rest)
            if not ranked:
                for lg, name in gaz.town_prefix(town_key(rest), admin.prefecture.code, limit=limit * 3):
                    owner = registry.get_municipality_by_code(lg)
                    if owner is not None:
                        ranked.append((len(name), Suggestion(
                            f"{owner.prefecture_name}{_muni_label(owner)}{name}", "town", lg)))
        else:
            for m in pool:
                if m.entity_type != "administrative_ward":
                    ranked.append((0, municipality_suggestion(m)))
    else:
        reading = kana_key(cleaned) if is_kana(cleaned) else None
        for p in registry.list_all_prefectures():
            if p.name.startswith(cleaned) or (reading and kana_key(p.kana).startswith(reading)):
                ranked.append((-1, Suggestion(p.name, "prefecture", None, None, unicodedata.normalize("NFKC", p.kana))))
        municipalities_matching(registry.list_municipalities(), cleaned)
        if len(cleaned) >= 2:
            found = gaz.town_prefix(town_key(cleaned), limit=limit * 3)
            if not found and reading:
                found = gaz.town_kana_prefix(reading, limit=limit * 3)
            for lg, name in found:
                owner = registry.get_municipality_by_code(lg)
                if owner is not None:
                    ranked.append((50 + len(name), Suggestion(
                        f"{owner.prefecture_name}{_muni_label(owner)}{name}", "town", lg)))

    ranked.sort(key=lambda item: (item[0], item[1].text))
    out_list: List[Suggestion] = []
    seen = set()
    for _, s in ranked:
        if s.text not in seen:
            seen.add(s.text)
            out_list.append(s)
            if len(out_list) >= limit:
                break
    return out_list


# ---------------------------------------------------------- reverse geocode
def reverse_geocode(latitude: float, longitude: float, limit: int = 1, max_km: float = 30.0) -> List[ReverseResult]:
    """The registered town / 丁目 (or block, with block data installed) nearest to a coordinate.

    This is the nearest representative point, not a boundary test: close to a boundary the
    neighbouring town can be nearer, so ``distance_m`` is returned for the caller to judge.
    Returns [] when nothing is registered within ``max_km`` (open sea, outside Japan).
    """
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("latitude must be within -90..90 and longitude within -180..180")
    gaz = get_gazetteer()
    registry = get_registry()
    results: List[ReverseResult] = []
    for distance, rec in gaz.nearest_towns(latitude, longitude, limit=max(limit, 4), max_km=max_km):
        muni = registry.get_municipality_by_code(rec.lg_code)
        if muni is None:
            continue
        codes = gaz.postal_codes_for(rec.lg_code, rec.name)
        label = _muni_label(muni)
        results.append(ReverseResult(
            address=f"{muni.prefecture_name}{label}{rec.name}" + (f"{rec.chome}丁目" if rec.chome else ""),
            level="chome" if rec.chome else "town", lg_code=rec.lg_code, prefecture=muni.prefecture_name,
            municipality=label, town=rec.name, chome=rec.chome, block=None, machiaza_id=rec.machiaza_id,
            postal_code=_format_postal(codes[0]) if len(codes) == 1 else None,
            latitude=rec.latitude, longitude=rec.longitude, distance_m=round(distance, 1),
        ))

    # With block data, the nearest block among the municipalities just found is more exact
    import math
    blocks: List[ReverseResult] = []
    cos_lat = math.cos(math.radians(latitude))
    for lg in dict.fromkeys(r.lg_code for r in results):
        if not gaz.blocks_available(lg[:2]):
            continue
        muni = registry.get_municipality_by_code(lg)
        towns = gaz.towns_in(lg)
        best: Optional[Tuple[float, Tuple[str, int, int], Any]] = None
        for key, point in gaz.block_points_in(lg).items():
            d = math.hypot((point.latitude - latitude) * 111_320, (point.longitude - longitude) * 111_320 * cos_lat)
            if best is None or d < best[0]:
                best = (d, key, point)
        if best is None or muni is None:
            continue
        d, (tkey, chome, block), point = best
        entry = towns.get(tkey)
        name = entry.name if entry is not None else tkey
        rec_for = entry.record_for(chome or None) if entry is not None else None
        codes = gaz.postal_codes_for(lg, name)
        label = _muni_label(muni)
        blocks.append(ReverseResult(
            address=f"{muni.prefecture_name}{label}{name}" + (f"{chome}丁目" if chome else "")
                    + (f"{block}番" if point.jukyo_hyoji else f"{block}番地"),
            level="block", lg_code=lg, prefecture=muni.prefecture_name, municipality=label, town=name,
            chome=chome or None, block=block, machiaza_id=rec_for.machiaza_id if rec_for else None,
            postal_code=_format_postal(codes[0]) if len(codes) == 1 else None,
            latitude=point.latitude, longitude=point.longitude, distance_m=round(d, 1),
        ))
    if blocks:
        blocks.sort(key=lambda r: r.distance_m)
        if blocks[0].distance_m <= results[0].distance_m:
            results = blocks[:1] + [r for r in results if r.level != "block"]
    return results[:limit]
