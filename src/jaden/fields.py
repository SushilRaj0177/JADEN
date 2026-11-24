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
from typing import Any, Dict, List, Optional, Tuple

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


def _postal_text(value: Any) -> str:
    from .core.text import postal_text
    return unicodedata.normalize("NFKC", postal_text(value)).strip()


_KANA_ONLY = re.compile(r"[ぁ-ゖァ-ヺー・\s]+")


def _reads_as(field_text: str, *readings: str) -> bool:
    """A field typed in kana that reads as one of ``readings`` (katakana)."""
    from .core.townkey import kana_key
    if not field_text or not _KANA_ONLY.fullmatch(field_text):
        return False
    key = kana_key(field_text)
    return any(r and key == kana_key(r) for r in readings)


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


_JAPANESE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


def _admin_in_english(prefecture: str, city: str) -> Tuple[str, str]:
    """Prefecture and city fields written in Japanese, romanized to go with an English street line."""
    from .data.loader import get_registry
    from .readings import _municipality_readings, _words
    registry = get_registry()
    pref = registry.get_prefecture_by_name(prefecture) if _JAPANESE.search(prefecture or "") else None
    if pref is not None:
        prefecture = pref.romaji
    if city and _JAPANESE.search(city):
        found = registry.find_municipalities(city, pref.code if pref else None)
        # '港区' -> 'Minato-ku'; a ward name several cities share ('中央区') is written alone ('Chuo-ku')
        forms = {" ".join(reversed(_words(r))) if len(found) == 1 else _words(r)[-1]
                 for r in (_municipality_readings().get(m.lg_code, {}).get("romaji") for m in found) if r}
        if len(forms) == 1:
            city = forms.pop()
    return prefecture, city


def _admin_in_japanese(prefecture: str, city: str) -> Tuple[str, str]:
    """Prefecture and city fields written in English, in Japanese to go with a Japanese street line."""
    from .romaji import _index, _segment_keys
    idx = _index()
    pref_code = None
    if prefecture and not _JAPANESE.search(prefecture):
        pref_code = next((idx.prefectures[k] for k in _segment_keys(prefecture) if k in idx.prefectures), None)
        if pref_code is not None:
            rec = idx.registry.get_prefecture_by_code(pref_code)
            prefecture = rec.name if rec else prefecture
    if city and not _JAPANESE.search(city):
        lgs = set().union(*(idx.munis.get(k, set()) for k in _segment_keys(city)))
        if pref_code is not None:
            lgs = {lg for lg in lgs if lg[:2] == pref_code}
        records = [r for r in (idx.registry.get_municipality_by_code(lg) for lg in sorted(lgs)) if r]
        wards = [r for r in records if r.entity_type == "administrative_ward"]
        if len(records) > 1 and len(wards) == 1:
            records = wards
        if len(records) == 1:
            city = (records[0].county or "") + records[0].name
        else:
            names = {r.ward or r.name for r in records}
            if len(names) == 1:
                city = names.pop()        # 'Chuo-ku' with no prefecture: 中央区, the town will say which
    return prefecture, city


def check_fields(prefecture: Any = "", city: Any = "", line1: Any = "", line2: Any = "", postal_code: Any = "",
                 strict: bool = False) -> FieldResult:
    """Reads an address given as separate fields and checks each field against the others."""
    from .engine import get_engine
    given = {"postal_code": _postal_text(postal_code), "prefecture": _clean(prefecture), "city": _clean(city),
             "line1": _clean(line1), "line2": _clean(line2)}
    issues: List[FieldIssue] = []

    postal = _postal_digits(given["postal_code"])
    postal_ok = bool(re.fullmatch(r"\d{7}", postal))
    if given["postal_code"] and not postal_ok:
        issues.append(FieldIssue("postal_code", "POSTAL_CODE_FORMAT",
                                 f"'{given['postal_code']}' is not a seven-digit postal code.",
                                 f"「{given['postal_code']}」は 7 桁の郵便番号ではありません。"))

    from .kana_input import admin_fields_to_kanji
    from .romaji import looks_romanized
    pref_text, city_text = admin_fields_to_kanji(given["prefecture"], given["city"])
    # The street line decides the language; prefecture and city fields in the other one are converted
    english = looks_romanized(given["line1"] or " ".join(v for v in (given["city"], given["prefecture"]) if v))
    if english:
        pref_en, city_en = _admin_in_english(given["prefecture"], given["city"])
    else:
        pref_text, city_text = _admin_in_japanese(pref_text, city_text)
    if english:
        # Fields filled in English ('4-2-8 Shibakoen' / 'Minato-ku' / 'Tokyo'): joined in English order
        body = ", ".join(v for v in (given["line2"], given["line1"], city_en, pref_en) if v)
        text = body + (f" {postal[:3]}-{postal[3:]}" if postal_ok else "")
    else:
        body = pref_text + city_text + given["line1"]
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
        from .data.loader import get_registry
        from .lookup import _muni_kana, _ward_kana
        registry = get_registry()
        pref_rec = registry.get_prefecture_by_code(c.prefecture_code) if c.prefecture_code else None
        pref_kana = pref_rec.kana if pref_rec else ""
        muni = registry.get_municipality_by_code(c.lg_code) if c.lg_code else None
        muni_readings = [_muni_kana(muni), _ward_kana(muni)] if muni else []
        if muni and muni.ward:
            city = next(iter(registry.find_municipalities(muni.city, muni.prefecture_code)), None)
            if city is not None:
                muni_readings.append(_muni_kana(city))
        cmp = dict(given)
        if not english:
            for name, text_ in (("prefecture", pref_text), ("city", city_text)):
                if given[name] and not _JAPANESE.search(given[name]) and _JAPANESE.search(text_ or ""):
                    cmp[name] = text_      # 'Tokyo' / 'Minato-ku' beside '芝公園4-2-8': compared as converted
        if english:
            # 'Tokyo' / 'Minato-ku' agree with 東京都 / 港区 when they romanize the same way
            from .romaji import _index, _segment_keys
            idx = _index()
            if any(idx.prefectures.get(k) == c.prefecture_code for k in _segment_keys(given["prefecture"])):
                cmp["prefecture"] = c.prefecture
            if c.lg_code and any(c.lg_code in idx.munis.get(k, ()) for k in _segment_keys(given["city"])):
                cmp["city"] = out["city"] or given["city"]
        if cmp["prefecture"] and not (c.prefecture.startswith(cmp["prefecture"])
                                      or cmp["prefecture"].startswith(c.prefecture)
                                      or _reads_as(cmp["prefecture"], pref_kana)):
            issues.append(FieldIssue("prefecture", "PREFECTURE_MISMATCH",
                                     f"The prefecture field says {given['prefecture']}; the address is in {c.prefecture}.",
                                     f"都道府県欄は「{given['prefecture']}」ですが、住所は{c.prefecture}です。",
                                     c.prefecture))
        city_field = cmp["city"]
        for pref_name in (c.prefecture, cmp["prefecture"]):
            if pref_name and city_field.startswith(pref_name):
                city_field = city_field[len(pref_name):]
        names = [n for n in (c.city, c.ward, c.county) if n]
        city_kana = city_field
        if pref_kana and _KANA_ONLY.fullmatch(city_kana or "x"):
            from .core.townkey import kana_key
            if kana_key(city_kana).startswith(kana_key(pref_kana)):
                city_kana = city_kana[len(pref_kana):]          # 'とうきょうとみなとく'
        if city_field and out["city"] and not any(n in city_field for n in names) and city_field not in out["city"] \
                and not _reads_as(city_kana, *muni_readings):
            issues.append(FieldIssue("city", "CITY_MISMATCH",
                                     f"The city field says {given['city']}; the address is in {out['city']}.",
                                     f"市区町村欄は「{given['city']}」ですが、住所は{out['city']}です。",
                                     out["city"]))
        moved = next((n for n in res.notes if n.startswith("did you mean ") and " is registered in " in n), None)
        if moved and given["city"] and not any(i.field == "city" for i in issues):
            # The town is not registered in the city written, but in one other city of the prefecture
            suggested = re.match(r"did you mean (.+?)\? ", moved)
            other = _split_fields(engine.normalize(suggested.group(1))) if suggested else None
            if other and other["city"]:
                out["postal_code"] = ""         # the written city's code is no answer for a town elsewhere
                issues.append(FieldIssue("city", "CITY_MISMATCH",
                                         f"{c.town} is not in {given['city']}; it is in {other['city']}.",
                                         f"{c.town}は{given['city']}ではなく{other['city']}にあります。", other["city"]))
        for name in (("prefecture", "city", "postal_code") if val.status == "ACCEPTED" else ()):
            if name == "postal_code" and any(i.code == "CITY_MISMATCH" for i in issues):
                continue    # the city's code is no answer when the town is in another city
            if not given[name] and out[name]:
                issues.append(FieldIssue(name, "FILLED_IN", f"{name} filled in from the address: {out[name]}.",
                                         f"{ {'prefecture': '都道府県', 'city': '市区町村', 'postal_code': '郵便番号'}[name]}"
                                         f"を住所から補いました: {out[name]}", out[name]))

    errors = [i for i in issues if i.code != "FILLED_IN"]
    valid = val.valid and not errors
    status, reason, message, message_ja = val.status, val.reason, val.message, val.message_ja
    if errors and val.status == "ACCEPTED":
        # The address exists, but the form contradicts it: report the form's first error, as validate()
        # reports a postal code that does not belong to the address
        first = errors[0]
        status, reason, message, message_ja = "MALFORMED", first.code, first.message, first.message_ja
    return FieldResult(status=status, valid=valid, reason=reason, message=message,
                       message_ja=message_ja, canonical=res.canonical if res.confidence_score > 0 else "",
                       lg_code=val.lg_code, input=given, fields=out, issues=issues)
