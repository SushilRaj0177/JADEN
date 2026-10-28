"""JADEN: Town-level resolution against the national gazetteer.

Given the municipalities the administrative parser could not rule out, the
town text left after the block FSM, and an optional postal code, decides:

- which candidate municipality actually contains the town (resolving
  '港区芝公園' to Tokyo, '中央区銀座' to Tokyo, '府中市宮西町' to Tokyo);
- whether the town and its 丁目 exist (catching '芝公園9丁目');
- whether the postal code agrees with the address;
- the registered spelling, reading, romanization, MLIT town ID and
  representative point of the town.

It never guesses between equally plausible candidates: if more than one
municipality still fits, the result stays ambiguous with a narrower list.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Sequence, Set

from ..core.townkey import town_key
from ..data.gazetteer import Gazetteer, TownMatch, TownRecord, PostalRecord
from ..data.loader import MunicipalityRecord

# Prefix matches shorter than this are too weak to resolve anything ('芝' inside '芝公園')
_MIN_PREFIX_CHARS = 2


@dataclass(frozen=True, slots=True)
class TownCheck:
    """Outcome of matching the town text inside one candidate municipality."""
    municipality: MunicipalityRecord
    match: Optional[TownMatch]
    chome_ok: Optional[bool]          # None when no 丁目 was given or no town matched
    postal_ok: Optional[bool]         # None when no postal code was given

    @property
    def town_found(self) -> bool:
        return self.match is not None

    @property
    def fits(self) -> bool:
        return self.town_found and self.chome_ok is not False and self.postal_ok is not False


@dataclass(frozen=True, slots=True)
class TownResolution:
    """What the gazetteer says about an address."""
    municipality: Optional[MunicipalityRecord] = None   # set when exactly one candidate fits
    resolved_from_candidates: bool = False              # True when this narrowed an ambiguity
    remaining_candidates: Tuple[MunicipalityRecord, ...] = ()
    match: Optional[TownMatch] = None
    town_verified: Optional[bool] = None                # None: nothing to check / no data
    chome_verified: Optional[bool] = None
    record: Optional[TownRecord] = None                 # the exact 丁目 / town row, if unique
    postal_code: Optional[str] = None
    postal_consistent: Optional[bool] = None
    postal_municipalities: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = field(default_factory=tuple)


def _postal_ok(postal: Sequence[PostalRecord], lg_code: str, match: Optional[TownMatch]) -> Optional[bool]:
    """False only when the postal code belongs to a different municipality."""
    if not postal:
        return None
    return any(p.lg_code == lg_code for p in postal)


def _postal_town_agrees(postal: Sequence[PostalRecord], lg_code: str, match: Optional[TownMatch]) -> bool:
    in_muni = [p for p in postal if p.lg_code == lg_code]
    if match is None or not in_muni or any(p.kind == "municipality" for p in in_muni):
        return True
    key = town_key(match.entry.name)
    return any(p.town and (key.startswith(town_key(p.town)) or town_key(p.town).startswith(key)) for p in in_muni)


def _postal_place(p: PostalRecord) -> str:
    from ..data.loader import get_registry
    muni = get_registry().get_municipality_by_code(p.lg_code)
    name = f"{muni.prefecture_name}{muni.name}" if muni else p.lg_code
    return name + p.town


def _check(gaz: Gazetteer, muni: MunicipalityRecord, town_text: str, chome: Optional[int],
           postal: Sequence[PostalRecord]) -> TownCheck:
    match = gaz.match_town(muni.lg_code, town_text) if town_text else None
    if match is not None and not match.exact and match.consumed < _MIN_PREFIX_CHARS:
        match = None
    chome_ok: Optional[bool] = None
    if match is not None and chome is not None:
        chome_ok = chome in match.entry.chomes
    return TownCheck(muni, match, chome_ok, _postal_ok(postal, muni.lg_code, match))


def resolve_town(
    gaz: Gazetteer,
    candidates: Sequence[MunicipalityRecord],
    town_text: str,
    chome: Optional[int],
    postal_code: Optional[str] = None,
) -> TownResolution:
    """Checks the town against each candidate municipality and narrows the candidates."""
    if not gaz.available or not candidates:
        return TownResolution(postal_code=postal_code)

    postal = gaz.postal_records(postal_code) if postal_code else []
    postal_lgs = tuple(sorted({p.lg_code for p in postal}))
    notes: List[str] = []
    if postal_code and not postal:
        notes.append(f"postal code {postal_code} is not in the Japan Post list")

    checks = [_check(gaz, m, town_text, chome, postal) for m in candidates]

    if len(checks) == 1:
        chosen: Optional[TownCheck] = checks[0]
        resolved = False
        remaining: Tuple[MunicipalityRecord, ...] = ()
    else:
        fitting = [c for c in checks if c.fits]
        if not fitting and postal_lgs:
            # The postal code alone can settle municipality-level ambiguity ('〒105-0011 港区...')
            fitting = [c for c in checks if c.postal_ok]
        # A whole-string match beats a match on only the first part of the town text
        exact = [c for c in fitting if c.match is not None and c.match.exact]
        if len(exact) == 1 and len(fitting) > 1:
            fitting = exact
        if len(fitting) == 1:
            chosen, resolved, remaining = fitting[0], True, ()
            by = "postal code" if not fitting[0].town_found else f"town '{fitting[0].match.entry.name}'"  # type: ignore[union-attr]
            notes.append(f"resolved {len(candidates)} candidate municipalities to {fitting[0].municipality.prefecture_name}"
                         f"{fitting[0].municipality.name} by {by}")
        else:
            chosen, resolved = None, False
            remaining = tuple(c.municipality for c in fitting) if fitting else tuple(candidates)

    if chosen is None:
        return TownResolution(remaining_candidates=remaining, postal_code=postal_code,
                              postal_municipalities=postal_lgs, notes=tuple(notes))

    match = chosen.match
    town_verified: Optional[bool] = None
    record: Optional[TownRecord] = None
    if town_text and gaz.has_municipality(chosen.municipality.lg_code):
        town_verified = match is not None
        if match is None:
            elsewhere = sorted({lg for lg, m in gaz.municipalities_with_town(town_text)
                                if m.exact and lg[:2] == chosen.municipality.lg_code[:2]})
            hint = f"; a town of that name exists in {len(elsewhere)} other municipality(ies) of this prefecture" if elsewhere else ""
            notes.append(f"town '{town_text}' is not registered in {chosen.municipality.name}{hint}")
    if match is not None:
        record = match.entry.record_for(chome)
        if chosen.chome_ok is False:
            chomes = match.entry.chomes
            span = f"{chomes[0]}–{chomes[-1]}丁目" if chomes else "no 丁目"
            notes.append(f"{match.entry.name} has only {span}; {chome}丁目 does not exist")
        elif record is None and len(match.entry.records) > 1 and chome is None and not match.entry.has_chome:
            notes.append(f"'{match.entry.name}' occurs {len(match.entry.records)} times in {chosen.municipality.name}")
    if chosen.postal_ok is False:
        where = ", ".join(_postal_place(p) for p in postal[:3])
        notes.append(f"postal code {postal_code} belongs to {where}, not to {chosen.municipality.name}")
    elif chosen.postal_ok and not _postal_town_agrees(postal, chosen.municipality.lg_code, match):
        towns = "/".join(sorted({p.town for p in postal if p.town}))
        notes.append(f"postal code {postal_code} is registered for {towns or 'another town'}, not {match.entry.name if match else town_text}")

    return TownResolution(
        municipality=chosen.municipality,
        resolved_from_candidates=resolved,
        remaining_candidates=remaining,
        match=match,
        town_verified=town_verified,
        chome_verified=chosen.chome_ok,
        record=record,
        postal_code=postal_code,
        postal_consistent=chosen.postal_ok,
        postal_municipalities=postal_lgs,
        notes=tuple(notes),
    )


def expand_candidates(registry, municipality: Optional[MunicipalityRecord],
                      candidates: Sequence[MunicipalityRecord], prefecture_code: Optional[str]) -> List[MunicipalityRecord]:
    """Municipalities whose town lists should be searched.

    Designated cities keep their towns under their wards, so a bare '京都市' or an
    ambiguous candidate list containing designated cities expands into wards.
    """
    base: List[MunicipalityRecord]
    if municipality is not None:
        base = [municipality]
    elif candidates:
        base = list(candidates)
    elif prefecture_code:
        base = [m for m in registry.list_municipalities(prefecture_code) if m.entity_type != "designated_city"]
    else:
        return []
    out: List[MunicipalityRecord] = []
    seen: Set[str] = set()
    for m in base:
        for x in (registry.wards_of(m) or [m]):
            if x.lg_code not in seen:
                seen.add(x.lg_code)
                out.append(x)
    return out
