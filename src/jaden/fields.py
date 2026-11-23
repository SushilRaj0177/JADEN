"""Structured input: an address typed into separate form fields, checked field by field.

    >>> r = jaden.check_fields(postal_code="105-0011", prefecture="東京都", city="港区", line1="芝公園4-2-8",
    ...                        line2="グランドメゾン芝公園302")
    >>> r.status, r.fields["line1"], r.issues
    ('ACCEPTED', '芝公園4丁目2番8号', [])

The fields are joined and read as one address (so a field that repeats another, or a town typed into
the city field, does no harm), then each field is checked against what was read: a prefecture or
city that does not match, a postal code of the wrong shape or for another place (with the right
one), and so on. ``fields`` gives the address back split into the same five fields, corrected.
"""

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from .core.text import as_text

FIELD_NAMES = ("postal_code", "prefecture", "city", "line1", "line2")


@dataclass(frozen=True)
class FieldIssue:
    field: str              # which input field
    code: str               # POSTAL_CODE_FORMAT, POSTAL_CODE_MISMATCH, PREFECTURE_MISMATCH, CITY_MISMATCH, FILLED_IN
    message: str
    message_ja: str
    suggestion: Optional[str] = None   # the value the field should hold, when known


@dataclass
class FieldResult:
    status: str
    valid: bool
    reason: str
    message: str
    message_ja: str
    canonical: str
    lg_code: Optional[str]
    input: Dict[str, str]
    fields: Dict[str, str]                       # the address split into the same fields, corrected
    issues: List[FieldIssue] = field(default_factory=list)

    @property
    def errors(self) -> List[FieldIssue]:
        return [i for i in self.issues if i.code != "FILLED_IN"]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean(value: Any) -> str:
    return unicodedata.normalize("NFKC", as_text(value)).strip()


def _postal_digits(value: str) -> str:
    return re.sub(r"[\s〒\-‐―−ー]", "", value)


def _split_fields(res: Any) -> Dict[str, str]:
    """The canonical address split into postal code, prefecture, city, line 1 (town and numbers) and
    line 2 (building, floor, room)."""
    from .formatting import _admin_part, _secondary
    c = res.components
    tail = _secondary(res)
    base = res.canonical[: len(res.canonical) - len(tail)].rstrip() if tail and res.canonical.endswith(tail) \
        else res.canonical
    admin = _admin_part(res)
    pref = c.prefecture or ""
    if res.confidence_score <= 0 or not c.lg_code or not admin or not base.startswith(admin):
        return {k: "" for k in FIELD_NAMES}      # not read as one place: nothing to split
    return {
        "postal_code": c.postal_code or "",
        "prefecture": pref,
        "city": admin[len(pref):] if admin.startswith(pref) else admin,
        "line1": base[len(admin):],
        "line2": tail,
    }


def check_fields(prefecture: Any = "", city: Any = "", line1: Any = "", line2: Any = "", postal_code: Any = "",
                 strict: bool = False) -> FieldResult:
    """Reads an address given as separate fields and checks each field against the others."""
    from .engine import get_engine
    given = {"postal_code": _clean(postal_code), "prefecture": _clean(prefecture), "city": _clean(city),
             "line1": _clean(line1), "line2": _clean(line2)}
    issues: List[FieldIssue] = []

    postal = _postal_digits(given["postal_code"])
    postal_ok = bool(re.fullmatch(r"\d{7}", postal))
    if given["postal_code"] and not postal_ok:
        issues.append(FieldIssue("postal_code", "POSTAL_CODE_FORMAT",
                                 f"'{given['postal_code']}' is not a seven-digit postal code.",
                                 f"「{given['postal_code']}」は 7 桁の郵便番号ではありません。"))

    body = given["prefecture"] + given["city"] + given["line1"]
    if given["line2"]:
        body += " " + given["line2"]
    text = (f"〒{postal[:3]}-{postal[3:]} " if postal_ok else "") + body

    engine = get_engine()
    res = engine.normalize(text)
    val = engine.validate(text, strict=strict, normalized=res)
    c = res.components
    out = _split_fields(res)

    if val.reason == "POSTAL_CODE_MISMATCH":
        # The right code: what the address gives without the written one
        without = engine.normalize(body)
        right = without.components.postal_code if without.components.lg_code == c.lg_code else None
        res, val, c = without, engine.validate(body, strict=strict, normalized=without), without.components
        out = _split_fields(res)
        issues.append(FieldIssue(
            "postal_code", "POSTAL_CODE_MISMATCH",
            f"Postal code {given['postal_code']} is not this address's" + (f"; it should be {right}." if right else "."),
            f"郵便番号 {given['postal_code']} はこの住所のものではありません" + (f"（正しくは {right}）。" if right else "。"),
            right))

    if res.confidence_score > 0 and c.prefecture:
        if given["prefecture"] and not (c.prefecture.startswith(given["prefecture"])
                                        or given["prefecture"].startswith(c.prefecture)):
            issues.append(FieldIssue("prefecture", "PREFECTURE_MISMATCH",
                                     f"The prefecture field says {given['prefecture']}; the address is in {c.prefecture}.",
                                     f"都道府県欄は「{given['prefecture']}」ですが、住所は{c.prefecture}です。",
                                     c.prefecture))
        city_field = given["city"]
        for pref_name in (c.prefecture, given["prefecture"]):
            if pref_name and city_field.startswith(pref_name):
                city_field = city_field[len(pref_name):]
        names = [n for n in (c.city, c.ward, c.county) if n]
        if city_field and out["city"] and not any(n in city_field for n in names) and city_field not in out["city"]:
            issues.append(FieldIssue("city", "CITY_MISMATCH",
                                     f"The city field says {given['city']}; the address is in {out['city']}.",
                                     f"市区町村欄は「{given['city']}」ですが、住所は{out['city']}です。",
                                     out["city"]))
        for name in (("prefecture", "city", "postal_code") if val.status == "ACCEPTED" else ()):
            if not given[name] and out[name]:
                issues.append(FieldIssue(name, "FILLED_IN", f"{name} filled in from the address: {out[name]}.",
                                         f"{ {'prefecture': '都道府県', 'city': '市区町村', 'postal_code': '郵便番号'}[name]}"
                                         f"を住所から補いました: {out[name]}", out[name]))

    valid = val.valid and not any(i.code != "FILLED_IN" for i in issues)
    return FieldResult(status=val.status, valid=valid, reason=val.reason, message=val.message,
                       message_ja=val.message_ja, canonical=res.canonical if res.confidence_score > 0 else "",
                       lg_code=val.lg_code, input=given, fields=out, issues=issues)
