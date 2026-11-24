"""JADEN: Address matching and deduplication (名寄せ).

Two records often hold the same address written differently:

    東京都港区芝公園4-2-8 グランドメゾン芝公園302
    港区芝公園４丁目２番８号　グランドメゾン芝公園　３０２号室

``match_key`` reduces an address to a stable key built from what the address
*means* (municipality code, registered town, 丁目, block, house number, room),
so equal keys mean the same place whatever the spelling. ``compare`` explains
how two addresses relate, level by level, and ``find_duplicates`` groups a list.

The levels are not fuzzy: each either agrees, conflicts, or is missing on one side, and the
result says which. Only building names are compared loosely (``building_similarity``), because
they are written freely; ``duplicate_pairs`` lists likely duplicates with a score and the reasons.
"""

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .core.townkey import town_key
from .models.address import NormalizedAddress

LEVELS: Tuple[str, ...] = ("prefecture", "municipality", "town", "chome", "block", "house", "unit")
KEY_LEVELS: Tuple[str, ...] = ("town", "chome", "block", "house", "unit")

_UNIT_DIGITS = re.compile(r"(\d+[A-Za-z]?)")
_FLOOR = re.compile(r"^(地下|B)?\s*(\d+)\s*(?:階|[Ff])?$")
_CANDIDATE_CODE = re.compile(r"\((\d{6})\)\s*$")


@dataclass(frozen=True, slots=True)
class MatchParts:
    """The comparable meaning of one address."""
    prefecture: Optional[str] = None      # JIS prefecture code
    municipality: Optional[str] = None    # LG code
    town: Optional[str] = None            # folded registered town name
    koaza: Optional[str] = None           # 字 below the town, when written; lot numbers often restart per 字
    chome: Optional[str] = None
    block: Optional[str] = None           # 番 / 番地 / first part of a lot number
    house: Optional[str] = None           # 号 / 枝番 / rest of a lot number
    unit: Optional[str] = None            # room number, or the floor when no room is given
    building: Optional[str] = None        # folded building name (reported, never decisive)
    candidates: Tuple[str, ...] = ()      # LG codes still possible when the municipality is ambiguous


@dataclass(frozen=True, slots=True)
class AddressComparison:
    """How two addresses relate."""
    a: str
    b: str
    verdict: str                 # 'same', 'same_building', 'possibly_same', 'different', 'undetermined'
    level: str                   # deepest level on which both agree ('none' ... 'unit')
    conflict: Optional[str]      # first level on which they disagree
    missing: Tuple[str, ...]     # levels only one side has
    canonical_a: str = ""
    canonical_b: str = ""
    notes: Tuple[str, ...] = field(default_factory=tuple)
    building_similarity: Optional[float] = None   # 0-1 when both name a building and they can be compared
    building_reason: str = ""                     # why the building names do or do not match

    @property
    def same(self) -> bool:
        return self.verdict == "same"

    def to_dict(self) -> Dict[str, object]:
        return {"a": self.a, "b": self.b, "verdict": self.verdict, "level": self.level,
                "conflict": self.conflict, "missing": list(self.missing),
                "canonical_a": self.canonical_a, "canonical_b": self.canonical_b, "notes": list(self.notes),
                "building_similarity": self.building_similarity, "building_reason": self.building_reason}


@dataclass(frozen=True, slots=True)
class DuplicatePair:
    """Two rows that are probably the same address, with why."""
    i: int
    j: int
    score: float                 # 0-1
    verdict: str                 # from compare()
    reasons: Tuple[str, ...]

    def to_dict(self) -> Dict[str, object]:
        return {"i": self.i, "j": self.j, "score": self.score, "verdict": self.verdict, "reasons": list(self.reasons)}


_KANJI_NUMERAL = "〇一二三四五六七八九十壱弐参拾"
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
_WING_WORD = r"(?:号棟|棟|号館|番館|館)"


def _kanji_number(text: str) -> str:
    """'二' -> '2', '十二' -> '12', '二十' -> '20' (building numbers stay small)."""
    text = text.translate(str.maketrans("壱弐参拾", "一二三十"))       # the old forms used on buildings
    digits = {c: i for i, c in enumerate("〇一二三四五六七八九")}
    if "十" not in text:
        return "".join(str(digits[c]) for c in text)
    tens, _, ones = text.partition("十")
    return str((digits.get(tens, 1) if tens else 1) * 10 + (digits.get(ones, 0) if ones else 0))


def _canonical_building(name: Optional[str]) -> str:
    """A building name written one way: NFKC, upper case, no spaces or punctuation, and the numbers that
    tell buildings apart in digits ('第一' -> '第1', '二号館' -> '2号館', 'コーポⅡ' -> 'コーポ2')."""
    s = unicodedata.normalize("NFKC", name or "").upper()
    s = re.sub(r"[\s・\-‐－()（）]", "", s).replace("ビルディング", "ビル").replace("ヶ", "ケ")
    s = re.sub(rf"第([{_KANJI_NUMERAL}]+)", lambda m: "第" + _kanji_number(m.group(1)), s)
    s = re.sub(rf"([{_KANJI_NUMERAL}]+)(?={_WING_WORD})", lambda m: _kanji_number(m.group(1)), s)
    s = re.sub(rf"(?<=[^\x00-\x7f])(VIII|VII|IX|IV|VI|III|II|I|V|X)(?=$|{_WING_WORD})",
               lambda m: str(_ROMAN[m.group(1)]), s)
    return s


def _wing_of(canonical: str, explicit: bool = False) -> str:
    """The number, letter or direction that tells buildings of one name apart: 'サンハイツA棟' -> 'A',
    '第2コーポ' -> '2', 'コーポ1' -> '1', 'グリーンハイツ東' -> '東'; '' when there is none.
    ``explicit``: only a wing marked as one ('A棟', '2号館') or glued to the end of the name ('コーポ1'),
    which people write as part of which flat it is; a number inside the name ('第二') goes with the name,
    which is often left out."""
    # A digit or letter glued to the end of the name ('コーポ1', 'サンハイツA') is written the same way:
    # 'コーポ1-201' and 'コーポ1 201号室' are one flat
    patterns = [rf"([A-Z]|\d{{1,3}}|[東西南北])(?:{_WING_WORD})$", r"(?<=[^\x00-\x7f\d第])(\d{1,2}|[A-Z])$"]
    if not explicit:
        patterns += [r"第(\d{1,3})", r"(?<=[^\x00-\x7f\d])(\d{1,3}|[東西南北])$", r"(?<!\d)(\d{1,4})(?!\d)"]
    from .parsers.building import _looks_like_building
    for i, pattern in enumerate(patterns):
        m = re.search(pattern, canonical)
        if m and not (i == 1 and not _looks_like_building(canonical[:m.start()])):
            return m.group(1)      # (a digit glued to text that is not a building name is no wing: '南1-1')
    return ""


def _fold_building(name: Optional[str]) -> Optional[str]:
    return _canonical_building(name).lower() or None


def building_similarity(a: Optional[str], b: Optional[str]) -> Tuple[Optional[float], str]:
    """How alike two building names are (0-1), and the reason. None when they cannot be compared
    (one is missing, or one is in Latin letters and the other in Japanese)."""
    ca, cb = _canonical_building(a), _canonical_building(b)
    if not ca or not cb:
        return None, ""
    if ca == cb:
        return 1.0, "same building name"
    wa, wb = _wing_of(ca), _wing_of(cb)
    if wa and wb and wa != wb:
        return 0.0, f"different numbers or wings in the building name ({a} / {b}): separate buildings"
    da, db = re.findall(r"\d+", ca), re.findall(r"\d+", cb)
    if da and db and da != db:
        return 0.0, f"different numbers in the building name ({a} / {b}): separate buildings"
    latin_a, latin_b = bool(re.fullmatch(r"[A-Z0-9.&']+", ca)), bool(re.fullmatch(r"[A-Z0-9.&']+", cb))
    if latin_a != latin_b:
        return None, "building names in different scripts; not compared"
    if wa != wb:
        base_a = ca[:-len(wa)] if wa and ca.endswith(wa) else ca
        base_b = cb[:-len(wb)] if wb and cb.endswith(wb) else cb
        if base_a == base_b or base_a in cb or base_b in ca:
            return 0.8, f"one building name adds a number or wing ({a} / {b})"
    short, long_ = sorted((ca, cb), key=len)
    if len(short) >= 3 and short in long_:
        return 0.9, "one building name is a shortened form of the other"
    ratio = difflib.SequenceMatcher(None, ca, cb).ratio()
    if len(ca) == len(cb):
        diffs = [(x, y) for x, y in zip(ca, cb) if x != y]
        if len(diffs) == 1 and not any(ch.isdigit() or ch.isascii() for ch in diffs[0]):
            return round(max(ratio, 0.85), 2), "building names one character apart (likely a typo)"
    return round(ratio, 2), f"building names {round(ratio * 100)}% alike"


def _unit_part(unit: Optional[str], floor: Optional[str], building: Optional[str] = None) -> Optional[str]:
    if unit:
        # Which wing the room is in is part of which flat it is: a wing marked in the building name
        # ('サンハイツB棟', '2号館') or written with the room ('1-201', 'A棟302'). A number that is just
        # part of the name ('第2コーポ') is not: the name is often left out, and the key must not change
        wing = _wing_of(_canonical_building(building), explicit=True)
        # The room as written, without its labels: '302号室', '#302', '-302' -> 302; 'A-302', 'A302' and 'A棟302'
        # are room 302 of wing A (A棟302)
        u = unicodedata.normalize("NFKC", unit).upper().strip()
        u = re.sub(r"\s+|号室|ごうしつ|室|号(?=棟)|号$", "", u)
        u = re.sub(r"^(?:#|ROOM|RM|APT|APARTMENT|UNIT)\.?", "", u).lstrip("-")
        written = re.fullmatch(r"([A-Z])-?(\d{2,4})|(\d{1,2})-(\d{2,4})|([A-Z]|\d{1,3}|[東西南北])棟(.+)", u)
        if written:
            unit_wing = written.group(1) or written.group(3) or written.group(5)
            u = written.group(2) or written.group(4) or written.group(6)
            wing = unit_wing if not wing or wing == unit_wing else f"{wing}-{unit_wing}"
        u = re.sub(r"(?<=[A-Z])-|-(?=[A-Z])", "", u)
        if not u:
            m = _UNIT_DIGITS.search(unicodedata.normalize("NFKC", unit))
            u = m.group(1).upper() if m else unit
        return f"{wing}棟{u}" if wing else u
    wing = _wing_of(_canonical_building(building), explicit=True)
    prefix = f"{wing}棟" if wing else ""
    if floor:
        m = _FLOOR.match(unicodedata.normalize("NFKC", floor))
        if m:
            return f"{prefix}{'B' if m.group(1) else ''}{int(m.group(2))}F"
        return prefix + floor
    return prefix or None


def _town_parts(res: NormalizedAddress) -> Tuple[Optional[str], Optional[str]]:
    """(town key, koaza key). The koaza is a 字 written below a registered town."""
    from .data.gazetteer import get_gazetteer
    c = res.components
    grid = c.hokkaido_grid
    if grid is not None and grid.jo is not None:
        return town_key(f"{grid.cardinal_ns}{grid.jo}条{grid.cardinal_ew}"), None
    town = c.town or ""
    if not town:
        return None, None
    gaz = get_gazetteer()
    match = gaz.match_town(c.lg_code, town) if (c.lg_code and gaz.available) else None
    if match is None:
        return town_key(town), None
    base = town_key(match.entry.name)
    rest = town[match.consumed:]
    if not rest or rest == "町":
        return base, None          # '若草町' written for the registered 若草 is the same town
    stripped = rest[2:] if rest.startswith("小字") else (rest[1:] if rest.startswith("字") else rest)
    is_koaza = rest.startswith(("字", "小字")) or bool(match.entry.records and match.entry.records[0].kind == "1")
    if is_koaza:
        return base, town_key(stripped, strip_aza=False)
    return f"{base}/{town_key(stripped, strip_aza=False)}", None


def match_parts(res: NormalizedAddress) -> MatchParts:
    c = res.components
    if res.confidence_score <= 0:
        return MatchParts()
    town, koaza = _town_parts(res)
    if town and c.town_homonyms > 1 and c.kyoto_direction is None:
        town = f"{town}@?"          # which of the towns of this name is not said: compared as possibly the same
    elif town and c.town_homonyms > 1 and c.kyoto_direction is not None:
        # Two Kyoto towns of one name in one ward: the street clause tells them apart
        k = c.kyoto_direction
        streets = "".join(re.sub(r"通り?$", "", x) for x in (k.street_1, k.street_2))
        town = f"{town}@{streets}{k.cardinal}"
    grid = c.hokkaido_grid
    chome = c.chome if c.chome is not None else (grid.chome if grid is not None else None)
    block: Optional[str]
    house: Optional[str]
    if c.lot_number is not None:
        block, _, rest = c.lot_number.partition("-")
        house = rest or None
    else:
        b = c.ban if c.ban is not None else c.banchi
        h = c.go if c.go is not None else c.edaban
        block = str(b) if b is not None else None
        house = str(h) if h is not None else None
    candidates = tuple(m.group(1) for m in (_CANDIDATE_CODE.search(x) for x in c.ambiguous_candidates) if m)
    return MatchParts(
        prefecture=c.prefecture_code,
        municipality=c.lg_code,
        town=town,
        koaza=koaza,
        chome=str(chome) if chome is not None else None,
        block=block,
        house=house,
        unit=_unit_part(c.unit, c.floor, c.building),
        building=_fold_building(c.building),
        candidates=candidates,
    )


def _resolve(address: Union[str, NormalizedAddress]) -> NormalizedAddress:
    if isinstance(address, NormalizedAddress):
        return address
    from .engine import get_engine
    return get_engine().normalize(address)


def match_key(address: Union[str, NormalizedAddress], level: str = "unit") -> Optional[str]:
    """A stable key for joining and deduplicating addresses.

    ``level`` is how precise the key is: 'town', 'chome', 'block', 'house' or 'unit'.
    Returns None when the address is not resolved to one municipality or does not reach
    that level (a 'house' key needs a house or lot number). At level 'unit' an address
    without a room still gets a key, with an empty room part.

        match_key('港区芝公園４丁目２番８号 ３０２号室')  ->  '131032|芝公園|4|2|8|302'
    """
    if level not in KEY_LEVELS:
        raise ValueError(f"level must be one of {', '.join(KEY_LEVELS)}")
    res = _resolve(address)
    p = match_parts(res)
    if p.municipality is None or (p.town is None and p.block is None):
        return None
    # The 字 is part of the key: in much of Japan lot numbers are only unique within a 字
    parts: List[str] = [p.municipality, (p.town or "") + (f"/{p.koaza}" if p.koaza else "")]
    if level == "town":
        return "|".join(parts)
    parts.append(p.chome or "")
    if level == "chome":
        return "|".join(parts) if (p.chome or p.block) else None
    if p.block is None:
        return None
    parts.append(p.block)
    if level == "block":
        return "|".join(parts)
    # A lone 番 identifies a lot in cadastral areas; in 住居表示 areas the 号 is needed as well
    if p.house is None and res.components.ban is not None and res.components.address_regime == "gaiku_hoshiki":
        return None
    parts.append(p.house or "")
    if level == "house":
        return "|".join(parts)
    parts.append(p.unit or "")
    return "|".join(parts)


def compare(a: Union[str, NormalizedAddress], b: Union[str, NormalizedAddress]) -> AddressComparison:
    """Compares two addresses level by level.

    verdict:
      'same'           agree down to the block / lot / house number, and on the room if either has one
      'same_building'  same house number; the rooms differ or only one side has a room
      'possibly_same'  nothing conflicts, but one side stops earlier (no number, or an
                       ambiguous municipality that could be the other's)
      'different'      a level conflicts (``conflict`` names it)
      'undetermined'   at least one side is not a resolvable address
    """
    ra, rb = _resolve(a), _resolve(b)
    pa, pb = match_parts(ra), match_parts(rb)
    raw_a = ra.input_raw
    raw_b = rb.input_raw

    similarity, why = building_similarity(ra.components.building, rb.components.building)

    def result(verdict: str, level: str, conflict: Optional[str], missing: Sequence[str],
               notes: Sequence[str] = ()) -> AddressComparison:
        return AddressComparison(raw_a, raw_b, verdict, level, conflict, tuple(missing),
                                 ra.canonical if ra.confidence_score > 0 else "",
                                 rb.canonical if rb.confidence_score > 0 else "", tuple(notes),
                                 similarity, why)

    def known(p: MatchParts) -> bool:
        return p.municipality is not None or bool(p.candidates)

    if not known(pa) or not known(pb):
        return result("undetermined", "none", None, (), ("at least one input is not a resolvable address",))

    level = "none"
    missing: List[str] = []
    notes: List[str] = []
    for name in LEVELS:
        va, vb = getattr(pa, name), getattr(pb, name)
        if name == "municipality" and (va is None or vb is None):
            ca = {va} if va else set(pa.candidates)
            cb = {vb} if vb else set(pb.candidates)
            if not ca & cb:
                return result("different", level, "municipality", missing)
            missing.append("municipality")
            notes.append("one municipality is ambiguous; the other is among its candidates")
            continue
        if name == "prefecture" and (va is None or vb is None):
            continue
        if name in ("house", "unit") and pa.block is None and pb.block is None:
            break   # a floor or room with no block or lot number ('4丁目 Aビル 2階') places nothing
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            missing.append(name)
            break
        if va != vb and name == "town" and va.split("@")[0] == vb.split("@")[0] and "@?" in (va[-2:], vb[-2:]):
            # One side names which of Kyoto's same-named towns, the other does not
            missing.append("town")
            notes.append("the town has several places of this name; only one address says which")
            break
        if va != vb:
            if name == "unit":
                wa, wb = (_wing_of(_canonical_building(r.components.building), explicit=True) for r in (ra, rb))
                if wa and wb and wa != wb:
                    # 第1ビル and 第2ビル on one lot, or rooms in wings A and B: separate buildings
                    return result("different", level, "building", missing,
                                  ("different buildings on the same lot",))
            return result("different" if name != "unit" else "same_building", level, name, missing,
                          ("different rooms in the same building",) if name == "unit" else ())
        level = name
        if name == "town" and pa.koaza != pb.koaza:
            if pa.koaza and pb.koaza:
                return result("different", "town", "koaza", missing)
            # Only one side wrote the 字. Lot numbers often restart in each 字, so this is not proof
            missing.append("koaza")
            notes.append("only one address names the 字; lot numbers can repeat between 字")

    if pa.building and pb.building and pa.building != pb.building:
        notes.append("building names differ")
        if similarity == 0.0:
            # 第一ビル / 第二ビル: the names number different buildings. The key leaves names out (they are
            # often omitted), so the verdict stands; the note and duplicate_pairs' score carry the doubt
            notes.append(f"the building names number different buildings ({ra.components.building} / "
                         f"{rb.components.building})")
    if missing == ["unit"]:
        present = pa.unit or pb.unit or ""
        notes.append("only one address names the wing" if present.endswith("棟") else "only one address has a room number")
        return result("same_building", level, None, missing, notes)
    if missing:
        return result("possibly_same", level, None, missing, notes)
    # Equal down to a block or lot number is the same place; equal only to the town is not enough to say
    return result("same" if level in ("block", "house", "unit") else "possibly_same", level, None, missing, notes)


def find_duplicates(addresses: Sequence[Union[str, NormalizedAddress]], level: str = "unit") -> List[Optional[int]]:
    """Group number for each address (1, 2, ...), equal for addresses with the same ``match_key``.

    Addresses that cannot be keyed at that level get None. Groups are numbered in order of
    first appearance; a group of one is still a group.
    """
    groups: Dict[str, int] = {}
    out: List[Optional[int]] = []
    for address in addresses:
        key = match_key(address, level)
        if key is None:
            out.append(None)
        else:
            out.append(groups.setdefault(key, len(groups) + 1))
    return out


_VERDICT_SCORE = {"same": 1.0, "same_building": 0.6, "possibly_same": 0.5}


def duplicate_pairs(addresses: Sequence[Union[str, NormalizedAddress]], min_score: float = 0.5,
                    max_comparisons: int = 5_000_000, report: Optional[Dict[str, object]] = None) -> List[DuplicatePair]:
    """Pairs of addresses that are probably the same place, best first, each with a score and reasons.

    Rows are compared only where a duplicate can be: the same room of the same house, or a row that
    leaves out its room (or house number) against the rows that give one. So a building with
    thousands of flats costs little. The score starts from compare()'s verdict (same 1.0, same
    building with a room on one side only 0.6, divided by the number of flats on record there, possibly
    the same 0.5; different rooms 0.1), times the
    building-name similarity when both name a building (a one-character typo keeps 0.9 of it, names
    numbering different buildings such as 第一ビル / 第二ビル keep none). ``report`` (a dict) receives 'comparisons' and
    'truncated' (True when ``max_comparisons`` stopped the search early).
    """
    resolved = [_resolve(a) for a in addresses]
    by_block: Dict[str, List[int]] = {}
    for i, res in enumerate(resolved):
        key = match_key(res, "block")
        if key is not None:
            by_block.setdefault(key, []).append(i)

    to_compare: List[Tuple[int, int]] = []
    seen = set()
    flats_in: Dict[Tuple[int, int], int] = {}     # pair -> how many flats (or houses) the open side could be

    def add(a: int, b: int, flats: int = 1) -> None:
        pair = (a, b) if a < b else (b, a)
        if a != b and pair not in seen:
            seen.add(pair)
            to_compare.append(pair)
            if flats > 1:
                flats_in[pair] = flats

    # Rows written exactly alike are linked to the first of them, not to each other (n rows, n - 1 pairs);
    # every other comparison is between distinct spellings only
    first_of: Dict[str, int] = {}
    rep: List[int] = []
    for i, res in enumerate(resolved):
        rep.append(first_of.setdefault(res.canonical or res.input_raw, i))

    truncated = False
    for members in by_block.values():
        for i in members:
            if rep[i] != i:
                add(rep[i], i)
        reps = [i for i in members if rep[i] == i]
        by_house: Dict[str, List[int]] = {}
        no_house: List[int] = []
        for i in reps:
            house = match_key(resolved[i], "house")
            (by_house.setdefault(house, []) if house else no_house).append(i)
        for house_members in by_house.values():
            by_unit: Dict[str, List[int]] = {}
            no_unit: List[int] = []
            for i in house_members:
                unit = match_parts(resolved[i]).unit
                (by_unit.setdefault(unit, []) if unit else no_unit).append(i)
            for group in list(by_unit.values()) + [no_unit]:
                for x, a in enumerate(group):
                    for b in group[x + 1:]:
                        add(a, b)
            # A row without a room may be any of the k flats on record: each pairing scores 0.6 / k, so
            # with many flats none is proposed (and none needs comparing)
            flats = len(by_unit)
            if no_unit and _VERDICT_SCORE["same_building"] / max(flats, 1) >= min_score:
                for a in no_unit:
                    for b in house_members:
                        if b not in no_unit:
                            add(a, b, flats)
        houses = len(by_house)                      # likewise for a row without a house number
        for x, a in enumerate(no_house):
            for b in no_house[x + 1:]:
                add(a, b)
        if no_house and _VERDICT_SCORE["possibly_same"] / max(houses, 1) >= min_score:
            for a in no_house:
                for b in reps:
                    if b not in no_house:
                        add(a, b, houses)
        if len(to_compare) > max_comparisons:
            truncated = True
            break

    pairs: List[DuplicatePair] = []
    for a, b in to_compare[:max_comparisons]:
        cmp = compare(resolved[a], resolved[b])
        score = _VERDICT_SCORE.get(cmp.verdict, 0.0)
        if cmp.verdict == "same_building" and cmp.conflict == "unit":
            score = 0.1                      # different rooms of one building are different addresses
        elif cmp.verdict in ("same_building", "possibly_same") and (a, b) in flats_in:
            score /= flats_in[(a, b)]
        reasons = [f"agree down to the {cmp.level}" if cmp.verdict != "same" or cmp.missing
                   else f"same address (agree down to the {cmp.level})"]
        if cmp.conflict:
            reasons.append(f"differ at the {cmp.conflict}")
        if cmp.missing:
            reasons.append("only one gives the " + ", ".join(cmp.missing))
        if cmp.building_similarity is not None:
            score *= cmp.building_similarity       # two different building names are two buildings
        if cmp.building_reason:
            reasons.append(cmp.building_reason)
        score = round(score, 3)
        if score >= min_score:
            pairs.append(DuplicatePair(a, b, score, cmp.verdict, tuple(reasons)))
    if report is not None:
        report["comparisons"] = min(len(to_compare), max_comparisons)
        report["truncated"] = truncated
    pairs.sort(key=lambda p: (-p.score, p.i, p.j))
    return pairs
