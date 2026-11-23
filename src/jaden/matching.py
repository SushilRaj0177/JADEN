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


def _fold_building(name: Optional[str]) -> Optional[str]:
    if not name:
        return None
    s = unicodedata.normalize("NFKC", name).lower()
    s = re.sub(r"[\s・\-‐－()（）]", "", s).replace("ビルディング", "ビル").replace("ヶ", "ケ")
    return s or None


_NUMBER_WORD = re.compile(r"[0-9]+|[A-Za-z](?=棟|号館|館)|[東西南北](?=棟|館)")
_KANJI_DIGITS = str.maketrans("〇一二三四五六七八九", "0123456789")


def _numbers_in(folded: str) -> Tuple[str, ...]:
    """The numbers and wing letters that tell buildings apart: '第2ビルA棟' -> ('2', 'a')."""
    s = re.sub(r"(?<=第)[〇一二三四五六七八九十]+", lambda m: m.group(0).translate(_KANJI_DIGITS), folded)
    return tuple(_NUMBER_WORD.findall(s))


def building_similarity(a: Optional[str], b: Optional[str]) -> Tuple[Optional[float], str]:
    """How alike two building names are (0-1), and the reason. None when they cannot be compared
    (one is missing, or one is in Latin letters and the other in Japanese)."""
    fa, fb = _fold_building(a), _fold_building(b)
    if not fa or not fb:
        return None, ""
    if fa == fb:
        return 1.0, "same building name"
    na, nb = _numbers_in(fa), _numbers_in(fb)
    if na and nb and na != nb:
        return 0.0, f"different numbers or wings in the building name ({a} / {b}): separate buildings"
    latin_a, latin_b = bool(re.fullmatch(r"[a-z0-9.&']+", fa)), bool(re.fullmatch(r"[a-z0-9.&']+", fb))
    if latin_a != latin_b:
        return None, "building names in different scripts; not compared"
    short, long_ = sorted((fa, fb), key=len)
    if len(short) >= 3 and short in long_:
        if na != nb:
            return 0.8, f"one building name adds a number or wing ({a} / {b})"
        return 0.9, "one building name is a shortened form of the other"
    ratio = difflib.SequenceMatcher(None, fa, fb).ratio()
    if len(fa) == len(fb) and sum(x != y for x, y in zip(fa, fb)) == 1:
        return round(max(ratio, 0.85), 2), "building names one character apart (likely a typo)"
    return round(ratio, 2), f"building names {round(ratio * 100)}% alike"


_WING = re.compile(r"(?:^|[^A-Za-z])([A-Za-z]|\d{1,2}|[東西南北])号?棟$")


def _unit_part(unit: Optional[str], floor: Optional[str], building: Optional[str] = None) -> Optional[str]:
    if unit:
        # A wing at the end of the building ('B棟', '1号棟') is part of which flat it is
        wing = _WING.search(unicodedata.normalize("NFKC", building or "").upper().strip())
        prefix = f"{wing.group(1)}棟" if wing else ""
        # The room as written, without its labels: '302号室', '#302', '-302' -> 302; 'A-302' -> A302;
        # 'A棟101' -> A棟101 (letters and wings tell flats apart); '2-302' stays 2-302
        u = unicodedata.normalize("NFKC", unit).upper().strip()
        u = re.sub(r"\s+|号室|室|号(?=棟)|号$", "", u)
        u = re.sub(r"^(?:#|ROOM|RM|APT|APARTMENT|UNIT)\.?", "", u).lstrip("-")
        u = re.sub(r"(?<=[A-Z])-|-(?=[A-Z])", "", u)
        if u:
            return prefix + u
        m = _UNIT_DIGITS.search(unicodedata.normalize("NFKC", unit))
        return prefix + (m.group(1).upper() if m else unit)
    if floor:
        m = _FLOOR.match(unicodedata.normalize("NFKC", floor))
        if m:
            return f"{'B' if m.group(1) else ''}{int(m.group(2))}F"
        return floor
    return None


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
        if va is None and vb is None:
            continue
        if va is None or vb is None:
            missing.append(name)
            break
        if va != vb:
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
        if similarity == 0.0 and level in ("house", "unit"):
            # 第1ビル and 第2ビル on one lot are two buildings: the same lot, not the same address
            notes.append("the building names number different buildings")
            return result("possibly_same", level, None, missing, notes)
    if missing == ["unit"]:
        notes.append("only one address has a room number")
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
                    max_group: int = 200) -> List[DuplicatePair]:
    """Pairs of addresses that are probably the same place, best first, each with a score and reasons.

    Only addresses on the same block (same match key at the 'block' level) are compared, so this
    scales to large files. The score starts from compare()'s verdict (same 1.0, same building 0.6,
    possibly the same 0.5) and is lowered when the building names disagree.
    """
    resolved = [_resolve(a) for a in addresses]
    by_block: Dict[str, List[int]] = {}
    for i, res in enumerate(resolved):
        key = match_key(res, "block")
        if key is not None:
            by_block.setdefault(key, []).append(i)
    pairs: List[DuplicatePair] = []
    for members in by_block.values():
        members = members[:max_group]
        for x, i in enumerate(members):
            for j in members[x + 1:]:
                cmp = compare(resolved[i], resolved[j])
                score = _VERDICT_SCORE.get(cmp.verdict, 0.0)
                reasons = [f"agree down to the {cmp.level}" if cmp.verdict != "same" or cmp.missing
                           else f"same address (agree down to the {cmp.level})"]
                if cmp.conflict:
                    reasons.append(f"differ at the {cmp.conflict}")
                if cmp.missing:
                    reasons.append("only one gives the " + ", ".join(cmp.missing))
                if cmp.building_similarity is not None:
                    score *= 0.5 + 0.5 * cmp.building_similarity
                if cmp.building_reason:
                    reasons.append(cmp.building_reason)
                score = round(score, 3)
                if score >= min_score:
                    pairs.append(DuplicatePair(i, j, score, cmp.verdict, tuple(reasons)))
    pairs.sort(key=lambda p: (-p.score, p.i, p.j))
    return pairs
