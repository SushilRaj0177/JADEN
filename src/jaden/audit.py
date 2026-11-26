"""Audit records that carry both an address and a municipality code: do the two agree?

Public registers (corporations, care offices, medical and welfare facilities) store each record's address as
text and its municipality as a code, maintained separately. ``check_record`` reads the address on its own,
compares it with the code, and says how they relate:

==========================  ==========================================================================
verdict                     meaning
==========================  ==========================================================================
consistent                  the address names the code's municipality (or its designated city / ward)
consistent_former_name      the address uses a former municipality name whose area is now the code's
code_retired                the code no longer exists; the address names one of its successors
conflict                    the address names another municipality
district_not_in_claimed     the address names no municipality, and its district does not exist in the
                            code's municipality (it does exist elsewhere)
undetermined                the address names no municipality; its district exists in the code's
                            municipality and in others, so the text cannot confirm or refute the code
unreadable                  the address does not resolve to any municipality or candidate list
code_invalid                the code is neither a current nor a retired municipality code
==========================  ==========================================================================

``municipality_written`` tells whether the address writes its municipality or JADEN inferred it from a district
that exists in only one place; a conflict of the first kind is stronger evidence. ``suggested_code`` gives the municipality the address points to when the verdict is ``conflict`` or (with a
single candidate) ``district_not_in_claimed``. The check is only as good as the reading of the address: a
``conflict`` is a disagreement to look at, not proof that the register is wrong.
"""

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Tuple

__all__ = ["AuditResult", "check_record", "VERDICTS"]

VERDICTS = ("consistent", "consistent_former_name", "code_retired", "conflict", "district_not_in_claimed",
            "undetermined", "unreadable", "code_invalid")

_CANDIDATE_CODE = re.compile(r"\((\d{6})\)")


@dataclass(frozen=True, slots=True)
class AuditResult:
    address: str
    claimed_code: str                          # six digits ('' when none was given)
    verdict: str                               # one of VERDICTS
    code_status: str                           # 'current', 'retired', 'invalid', 'missing'
    claimed_current: Tuple[str, ...] = ()      # the current codes the claimed code stands for
    resolved_code: Optional[str] = None        # the municipality the address alone names
    candidates: Tuple[str, ...] = ()           # the municipalities its district exists in, when ambiguous
    suggested_code: Optional[str] = None
    former_name: Optional[str] = None          # a former municipality name written in the address
    claimed_name_in_address: bool = False      # the address also writes the claimed municipality's name
    municipality_written: bool = False         # the address writes its municipality (not inferred from the district)
    detail: str = ""
    notes: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _same_place(a: str, b: str) -> bool:
    """Equal codes, or a designated city and one of its wards."""
    if a == b:
        return True
    from .data.loader import get_registry
    reg = get_registry()
    ra, rb = reg.get_municipality_by_code(a), reg.get_municipality_by_code(b)
    if ra is None or rb is None or ra.prefecture_code != rb.prefecture_code:
        return False
    city_a = ra.entity_type == "designated_city"
    city_b = rb.entity_type == "designated_city"
    return (city_a and bool(rb.ward) and rb.city == ra.city) or (city_b and bool(ra.ward) and ra.city == rb.city)


def _names(code: str) -> Tuple[str, ...]:
    from .data.loader import get_registry
    rec = get_registry().get_municipality_by_code(code)
    if rec is None:
        return ()
    names = [rec.name]
    if rec.ward:
        names.append(rec.ward)
    return tuple(n for n in names if len(n) >= 2)


def check_record(address: str, code: Optional[str] = None) -> AuditResult:
    """Compare an address with the municipality code a record carries.

    Args:
        address: the address as stored, with or without prefecture and municipality.
        code: the record's municipality code, five or six digits (全国地方公共団体コード).
    """
    from .data.loader import get_registry
    from .engine import get_engine
    from .history import _six, code_change
    registry = get_registry()
    claimed = _six(code) if code else ""
    claimed_now: Tuple[str, ...]
    if not claimed:
        status, claimed_now = "missing", ()
    elif registry.get_municipality_by_code(claimed) is not None:
        status, claimed_now = "current", (claimed,)
    else:
        change = code_change(claimed)
        status, claimed_now = ("retired", change.successors) if change else ("invalid", ())

    engine = get_engine()
    res = engine.normalize(address)
    val = engine.validate(address, normalized=res) if res.confidence_score > 0 else None
    former = res.components.former_municipality
    written_muni = bool(res.components.lg_code) and (not res.components.municipality_inferred or bool(former))
    notes = tuple(res.notes)

    def result(verdict: str, **kw: Any) -> AuditResult:
        return AuditResult(address=address, claimed_code=claimed, verdict=verdict, code_status=status,
                           claimed_current=tuple(claimed_now), former_name=former, notes=notes,
                           municipality_written=written_muni, **kw)

    if status == "invalid":
        return result("code_invalid", detail=f"{claimed} is neither a current nor a retired municipality code")
    if val is None or val.status in ("MALFORMED", "UNSUPPORTED"):
        return result("unreadable", detail=val.message if val else "the address could not be read")

    def agrees(lg: str) -> bool:
        return any(_same_place(lg, c) for c in claimed_now)

    if val.status == "ACCEPTED" and val.lg_code:
        resolved = val.lg_code
        if not claimed_now:
            return result("undetermined", resolved_code=resolved, detail="no code to compare with")
        if agrees(resolved):
            if status == "retired":
                return result("code_retired", resolved_code=resolved,
                              detail=f"{claimed} no longer exists; the address names its successor {resolved}")
            if former:
                return result("consistent_former_name", resolved_code=resolved,
                              detail=f"the address uses the former name {former}")
            return result("consistent", resolved_code=resolved)
        written = any(n in address for c in claimed_now for n in _names(c))
        how = "names" if written_muni else "has a district that exists only in"
        return result("conflict", resolved_code=resolved, suggested_code=resolved, claimed_name_in_address=written,
                      detail=(f"the address {how} {resolved}" + (" and also writes the claimed municipality" if written else "")))

    candidates = tuple(dict.fromkeys(m.group(1) for c in val.ambiguous_candidates for m in _CANDIDATE_CODE.finditer(c)))
    if not candidates:
        return result("unreadable", detail=val.message)
    if not claimed_now:
        return result("undetermined", candidates=candidates, detail="no code to compare with")
    if any(agrees(c) for c in candidates):
        return result("undetermined", candidates=candidates,
                      detail=f"the district exists in the claimed municipality and in {len(candidates) - 1} other(s)")
    return result("district_not_in_claimed", candidates=candidates,
                  suggested_code=candidates[0] if len(candidates) == 1 else None,
                  detail=f"the district does not exist in the claimed municipality; it exists in {len(candidates)} other(s)")
