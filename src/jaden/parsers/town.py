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

import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Sequence, Set

from ..core.townkey import is_kana, is_numeral, kana_key, one_edit_apart, spelling_key, town_key
from ..data.gazetteer import Gazetteer, TownEntry, TownMatch, TownRecord, PostalRecord
from ..data.loader import MunicipalityRecord

# Prefix matches shorter than this are too weak to resolve anything ('芝' inside '芝公園')
_MIN_PREFIX_CHARS = 2


# Single characters used as lot-series prefixes after a town name ('熊坂町ハ31', '畑寺町丙238')
_LOT_SERIES = set("甲乙丙丁戊己庚辛壬癸イロハニホヘトチリヌルヲワカヨタレソツネナラムウヰノオクヤマケフコエテアサキユメミシヱヒモセス")


def koaza_remainder(rest: str) -> bool:
    """True when text left after a town name is a 字 / 小字 or a lot-series prefix, not a different town."""
    # Tsuruga's '谷25号1番1', Katsuyama's '片瀬第15号': a numbered 号 district below the town is like a 字
    return (rest.startswith(("字", "小字")) or (len(rest) == 1 and rest in _LOT_SERIES)
            or bool(re.fullmatch(r"第?\d+号", rest)))


# Words that end a facility name, never a 字 ('ニセコ高等学校', '国府小学校')
_FACILITY_END = re.compile(r"(学校|高校|大学|病院|医院|センター|駅|ビル|会館|館|園|寺|神社|教会|工場|事務所|内)$")


def unmarked_koaza(match: TownMatch, rest: str) -> bool:
    """True when ``rest`` after a registered 大字 reads as a 字 written without 字 ('吉良町中野' + '郷中',
    '勿来町' + '窪田万谷'): the 大字 is at least three characters long, the rest is two to six
    characters of name, and a block number follows it in the address."""
    records = match.entry.records
    return (match.consumed >= 3 and bool(records) and records[0].kind in ("1", "0")
            and bool(re.fullmatch(r"[^\d\s\-()（）]{2,6}", rest)) and not _FACILITY_END.search(rest))


def lot_series_follows(rest: str) -> bool:
    """True when ``rest`` is a lot-series character followed by its number ('甲407-1')."""
    return len(rest) >= 2 and rest[0] in _LOT_SERIES and rest[1].isdigit()


def town_variants(town_text: str, first_number: Optional[int]) -> List[Tuple[str, str]]:
    """Registered spellings that real addresses often shorten.

    '伊勢宮' -> '伊勢宮町'; 'つつじが丘南' + 1 -> 'つつじが丘南1番町'; '本町' + 6 -> '本町6の' (本町六の一丁目).
    Returns (registered text, kind) pairs; kind 'machi' keeps the numbers, the others consume the first one.
    """
    if not town_text:
        return []
    out = [(town_text + "町", "machi")]
    if first_number is not None:
        # '北条町1-2-31' is 北条町一丁 2番31号 in Sakai, where towns are registered as 'N丁'
        out += [(f"{town_text}{first_number}番町", "banchou"), (f"{town_text}{first_number}の", "no"),
                (f"{town_text}{first_number}丁", "banchou")]
    return out


# Old kanji forms rarely typed by accident (not 舘, 嶋, 﨑, which are in everyday registered names)
_OLD_FORMS = frozenset("溪澤濱邊邉齋齊萬櫻龍與國壽鹽瀧藏廣曾惠眞淺條會舊實繩驛峯臺彌塲麴栁德豐榮靜寶鐵圓學禮增莊來兒黑"
                       "橫巖當藝龜澁攝氣穗鄕內淸靑步狹敎賴瀨禪彈縣聲樂藥應燈鷄嶽礪蘆鷗驒竈")

# Katakana typed for the kanji they look like
_KANA_FOR_KANJI = str.maketrans({"ニ": "二", "ロ": "口", "カ": "力", "エ": "工", "ハ": "八", "タ": "夕", "ト": "卜"})


def _respelt_town(gaz: Gazetteer, lg_code: str, town_text: str) -> Optional[Tuple[TownEntry, int]]:
    """A registered town the written one stands for when nothing matched it as written.

    (entry, characters of ``town_text`` it covers), tried in this order:
      'ニの' + number            the town ニ: の joins it to the lot number
      '市ヶ谷加賀町', '桜ケ丘町'   registered without the ケ: 市谷加賀町, 桜丘町
      '花岡字姥沢'               花岡町 before its 字
      '小舟町', '本塩町'          registered with the area name in front: 日本橋小舟町, 四谷本塩町
    """
    towns = gaz.towns_in(lg_code)
    if not towns:
        return None
    if len(town_text) >= 2 and town_text[-1] in "のノ":
        entry = towns.get(town_key(town_text[:-1]))
        if entry is not None:
            return entry, len(town_text)
    cut = town_text.find("字", 1)
    head = town_text[:cut] if cut > 0 else town_text
    covered = len(head)
    key = town_key(head)
    lookalike = head.translate(_KANA_FOR_KANJI)
    if lookalike != head:
        entry = towns.get(town_key(lookalike))      # 'ニ宮' typed for 二宮
        if entry is not None:
            return entry, covered
    if "ケ" in key:
        entry = towns.get(key.replace("ケ", ""))
        if entry is not None:
            return entry, covered
    elif len(key) >= 2:
        # '武蔵丘' for 武蔵ケ丘: the registered name has a ケ the written one leaves out
        with_ke = {k for k in (key[:i] + "ケ" + key[i:] for i in range(1, len(key))) if k in towns}
        if len(with_ke) == 1:
            return towns[with_ke.pop()], covered
    if cut > 0 and len(head) >= 2:
        entry = towns.get(town_key(head + "町"))
        if entry is not None:
            return entry, covered
    if cut < 0 and len(key) >= 3 and key.endswith("町"):
        # The registered name ends with the written one, and what stands before it is an area name
        # that starts other towns of the municipality too (日本橋, 四谷, 神田). Only for 町 names: an
        # old grid name ('字西一條十丁目' in 帯広市) must not become 大正本町西一条
        ending = [(k, e) for k, e in towns.items() if k.endswith(key) and len(k) > len(key)]
        if len(ending) == 1:
            area = ending[0][0][:-len(key)]
            if len(area) >= 2 and sum(1 for k in towns if k.startswith(area)) >= 3:
                return ending[0][1], covered
    return None


@dataclass(frozen=True, slots=True)
class TownCheck:
    """Outcome of matching the town text inside one candidate municipality."""
    municipality: MunicipalityRecord
    match: Optional[TownMatch]
    chome_ok: Optional[bool]          # None when no 丁目 was given or no town matched
    postal_ok: Optional[bool]         # None when no postal code was given
    variant: Optional[str] = None     # set when only a town_variants() spelling matched
    chome_unlisted: bool = False      # the 丁目 is not in the registry but may well exist

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
    variant: Optional[str] = None                       # 'machi', 'banchou' or 'no' (see town_variants)
    chome_unlisted: bool = False                        # 丁目 absent from the registry, yet plausible
    postal_code: Optional[str] = None
    postal_consistent: Optional[bool] = None
    postal_municipalities: Tuple[str, ...] = ()
    town_registered_elsewhere: Tuple[str, ...] = ()     # same-named municipalities elsewhere that have the town
    notes: Tuple[str, ...] = field(default_factory=tuple)


# How far past the registered 丁目 a written one may lie and still be taken as real. New 丁目 extend
# the sequence (鹿児島市吉野 1–2丁目 gained 3丁目), and a town the registry does not divide may use
# 丁目 as 字 names (岡崎市伝馬通5丁目, 伊達市保原町7丁目). Beyond that the number is an error.
_CHOME_BEYOND_LAST = 2
_CHOME_AS_AZA_MAX = 20


def chome_state(chomes: Sequence[int], chome: int) -> Tuple[Optional[bool], bool]:
    """(registered?, unlisted but plausible?) of a written 丁目 in a town whose 丁目 the registry lists.

    (True, False): registered. (False, False): cannot exist. (None, True): not listed, plausible.
    """
    if chome in chomes:
        return True, False
    if chome < 1:
        return False, False
    if not chomes:
        return (None, True) if chome <= _CHOME_AS_AZA_MAX else (False, False)
    return (None, True) if chome <= max(chomes) + _CHOME_BEYOND_LAST else (False, False)


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
           postal: Sequence[PostalRecord], chome_explicit: bool, first_number: Optional[int],
           strong_prefix_ok: bool = True, respell_ok: bool = True) -> TownCheck:
    match = gaz.match_town(muni.lg_code, town_text) if town_text else None
    if (match is not None and not match.exact and match.consumed < _MIN_PREFIX_CHARS
            and (town_text.startswith(("大字", "小字")) or not koaza_remainder(town_text[match.consumed:]))):
        # One character is too little to go on, unless a 字 or a lot series follows it ('平字三町目',
        # '巻甲'). The 大 of '大字…' is the marker, not the town 大
        match = None
    if (match is not None and not match.exact and not strong_prefix_ok and not koaza_remainder(town_text[match.consumed:])
            and not (first_number is not None and unmarked_koaza(match, town_text[match.consumed:]))):
        # Among many candidates a partial match ('ニセコ高等学校' starting with 字ニセコ) proves nothing,
        # unless it is a long 大字 with a 字 after it and a block number ('加納町向井山9番1')
        match = None
    chome_ok: Optional[bool] = None
    unlisted = False
    if match is not None and match.exact and chome is not None:
        # Only a whole-name match can say a 丁目 is missing; '花川' does not speak for '花川北'.
        # A bare 'N-N-N' in a town without 丁目 is a lot number, so it cannot be wrong either.
        # In a town that is only partly divided into 丁目 ('御望971-1-2'), a bare number may be a lot
        if match.entry.chomes_known and (chome_explicit or all(r.chome is not None for r in match.entry.records)):
            chome_ok, unlisted = chome_state(match.entry.chomes, chome)
    if (match is None or not match.exact) and is_kana(town_text):
        # The town typed by its reading ('しばこうえん'): Japan Post's kana names exactly one town here
        hits = gaz.towns_by_kana(muni.lg_code).get(kana_key(town_text), [])
        if len(hits) == 1:
            hit = hits[0]
            kana_match = TownMatch(muni.lg_code, hit, len(town_text), exact=True)
            kana_chome: Optional[bool] = None
            kana_unlisted = False
            if chome is not None and hit.chomes_known and (
                    chome_explicit or all(r.chome is not None for r in hit.records)):
                kana_chome, kana_unlisted = chome_state(hit.chomes, chome)
            return TownCheck(muni, kana_match, kana_chome, _postal_ok(postal, muni.lg_code, kana_match), "kana",
                             kana_unlisted)
    postal_only = match is not None and match.entry.source == "postal"
    if match is None or not match.exact or chome_ok is False or unlisted or postal_only:
        towns = gaz.towns_in(muni.lg_code)
        variants = town_variants(town_text, first_number)
        if unlisted and town_text.endswith("町") and len(town_text) > 2:
            # '二日市町4丁目' where 二日市町 has no 丁目 and 二日市 has a 4丁目
            variants = [(town_text[:-1], "machi")] + variants
        for text, kind in variants:
            entry = towns.get(town_key(text))
            if entry is None or (kind == "machi" and chome is not None and entry.has_chome and chome not in entry.chomes):
                continue
            if (chome_ok is False or unlisted) and not (kind == "machi" and chome in entry.chomes):
                # '浜田99-1-1': 浜田 is divided into 丁目 and has no 99丁目; reading it as a lot of
                # 浜田町 would hide the error rather than explain it
                continue
            variant_match = TownMatch(muni.lg_code, entry, len(town_text), exact=True)
            variant_chome = True if kind == "machi" and chome is not None and chome in entry.chomes else None
            return TownCheck(muni, variant_match, variant_chome, _postal_ok(postal, muni.lg_code, variant_match), kind)
    if match is None and town_text and respell_ok:
        respelt = _respelt_town(gaz, muni.lg_code, town_text)
        if respelt is not None:
            entry, consumed = respelt
            other = TownMatch(muni.lg_code, entry, consumed, exact=consumed == len(town_text))
            other_chome: Optional[bool] = None
            other_unlisted = False
            if other.exact and chome is not None and entry.chomes_known and (
                    chome_explicit or all(r.chome is not None for r in entry.records)):
                other_chome, other_unlisted = chome_state(entry.chomes, chome)
            return TownCheck(muni, other, other_chome, _postal_ok(postal, muni.lg_code, other), "machi", other_unlisted)
    district = _NUMBERED_DISTRICT.search(town_text) if match is None else None
    if district and district.start() > 0:
        # '三島110号2番地': the town before a numbered 号 district is checked with every rule (here 三島 is
        # registered as 三島町); the district stays as written below it
        base = _check(gaz, muni, town_text[:district.start()], None, postal, False, None, strong_prefix_ok, respell_ok)
        if base.match is not None:
            below = TownMatch(muni.lg_code, base.match.entry, base.match.consumed, exact=False)
            return TownCheck(muni, below, None, _postal_ok(postal, muni.lg_code, below), base.variant)
    return TownCheck(muni, match, chome_ok, _postal_ok(postal, muni.lg_code, match), None, unlisted)


_NUMBERED_DISTRICT = re.compile(r"第?\d+号$")


def resolve_town(
    gaz: Gazetteer,
    candidates: Sequence[MunicipalityRecord],
    town_text: str,
    chome: Optional[int],
    postal_code: Optional[str] = None,
    chome_explicit: bool = True,
    first_number: Optional[int] = None,
) -> TownResolution:
    """Checks the town against each candidate municipality and narrows the candidates."""
    if not gaz.available or not candidates:
        return TownResolution(postal_code=postal_code)

    postal = gaz.postal_records(postal_code) if postal_code else []
    postal_lgs = tuple(sorted({p.lg_code for p in postal}))
    notes: List[str] = []
    if postal_code and not postal:
        notes.append(f"postal code {postal_code} is not in the Japan Post list")

    # Respelling a town is safe within one place: one municipality, or the wards of one city
    one_place = len({(c.prefecture_code, c.city) for c in candidates}) == 1
    checks = [_check(gaz, m, town_text, chome, postal, chome_explicit, first_number, len(candidates) == 1, one_place)
              for m in candidates]

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
        # A municipality where the written 丁目 is registered beats one where it would be a new one
        listed = [c for c in fitting if not c.chome_unlisted]
        if listed and len(listed) < len(fitting):
            fitting = listed
        # A longer registered name beats a shorter one ('吉良町中野' + 郷中 over '吉良町' + 中野郷中)
        if len(fitting) > 1 and all(c.match is not None and not c.match.exact for c in fitting):
            longest = max(c.match.consumed for c in fitting)  # type: ignore[union-attr]
            fitting = [c for c in fitting if c.match.consumed == longest]  # type: ignore[union-attr]
        # An old kanji form written on purpose picks the town registered with it: '檀溪通' is 昭和区,
        # while the everyday '檀渓通' may be 昭和区's 檀溪通 or 瑞穂区's 檀渓通
        if len(fitting) > 1 and any(ch in _OLD_FORMS for ch in town_text):
            def spelt(c: TownCheck) -> bool:
                names = {c.match.entry.name} | {r.name for r in c.match.entry.records} if c.match else set()
                return any(town_text.startswith(n) or town_text.startswith(n[2:] if n.startswith("大字") else n[1:])
                           for n in names if n)
            verbatim = [c for c in fitting if spelt(c)]
            if len(verbatim) == 1:
                fitting = verbatim
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
    misplaced: Tuple[str, ...] = ()
    if town_text and gaz.has_municipality(chosen.municipality.lg_code):
        town_verified = match is not None
        if match is None:
            everywhere = {lg for lg, m in gaz.municipalities_with_town(town_text) if m.exact}
            elsewhere = sorted(lg for lg in everywhere if lg[:2] == chosen.municipality.lg_code[:2])
            hint = f"; a town of that name exists in {len(elsewhere)} other municipality(ies) of this prefecture" if elsewhere else ""
            if len(elsewhere) == 1:
                hint += f" ({elsewhere[0]})"
            notes.append(f"town '{town_text}' is not registered in {chosen.municipality.name}{hint}")
            # '静岡県中央区日本橋兜町': the town belongs to a municipality of the same name elsewhere
            # (東京都中央区), so the written prefecture contradicts the rest of the address
            short = chosen.municipality.ward or chosen.municipality.name
            from ..data.loader import get_registry
            reg = get_registry()
            same_name = [r for r in (reg.get_municipality_by_code(lg) for lg in sorted(everywhere)) if r is not None
                         and r.lg_code != chosen.municipality.lg_code and (r.ward or r.name) == short]
            if same_name:
                misplaced = tuple(r.lg_code for r in same_name)
                places = ", ".join(f"{r.prefecture_name}{r.name}" for r in same_name[:3])
                notes.append(f"'{town_text}' is registered in {places}, a different {short}")
    if match is not None:
        record = match.entry.record_for(chome)
        if chosen.chome_ok is False or chosen.chome_unlisted:
            chomes = match.entry.chomes
            verdict = "does not exist" if chosen.chome_ok is False else "is not in the registry (it may be newer than the data)"
            if chomes:
                contiguous = list(chomes) == list(range(chomes[0], chomes[-1] + 1))
                listed_text = f"{chomes[0]}–{chomes[-1]}" if contiguous else ", ".join(map(str, chomes))
                notes.append(f"{match.entry.name} has only {listed_text}丁目; {chome}丁目 {verdict}")
            elif chosen.chome_ok is False:
                notes.append(f"{match.entry.name} is not divided into 丁目; {chome}丁目 does not exist")
            else:
                notes.append(f"{match.entry.name} is not divided into 丁目 in the registry; {chome}丁目 is not listed "
                             "(it may be a 字 name or newer than the data)")
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
        variant=chosen.variant,
        chome_unlisted=chosen.chome_unlisted,
        postal_code=postal_code,
        postal_consistent=chosen.postal_ok,
        postal_municipalities=postal_lgs,
        town_registered_elsewhere=misplaced,
        notes=tuple(notes),
    )


def near_towns(gaz: Gazetteer, lg_code: str, town_text: str) -> List[str]:
    """Registered town names one edit away from ``town_text`` in one municipality (likely typos).

    A number changed into another number is never a typo to correct: '北九条西' is not a
    misspelt '北八条西'.
    """
    key = spelling_key(town_text)
    if len(key) < 2:
        return []
    out: List[str] = []
    for form, name in _spelling_forms(gaz, lg_code).get(len(key), ()) + \
            _spelling_forms(gaz, lg_code).get(len(key) - 1, ()) + _spelling_forms(gaz, lg_code).get(len(key) + 1, ()):
        if not one_edit_apart(key, form):
            continue
        if len(key) == len(form):
            diff = [(a, b) for a, b in zip(key, form) if a != b]
            if all(is_numeral(a) and is_numeral(b) for a, b in diff):
                continue
        if name not in out:
            out.append(name)
    return out


_SPELLING_FORMS: "dict[tuple[int, str], dict[int, tuple[tuple[str, str], ...]]]" = {}


def _spelling_forms(gaz: Gazetteer, lg_code: str) -> "dict[int, tuple[tuple[str, str], ...]]":
    """(spelling, registered name) of every town of a municipality, grouped by length (cached).

    A town is also written with 町 after its registered name ('石井町' for 大字石井), and a typo of that
    form must count too, or '石崎町' would look like it can only mean 石松町."""
    cache_key = (id(gaz), lg_code)
    found = _SPELLING_FORMS.get(cache_key)
    if found is None:
        by_len: "dict[int, list[tuple[str, str]]]" = {}
        for towns in (gaz.towns_in(lg_code), gaz.postal_towns_in(lg_code)):
            for entry in towns.values():
                other = spelling_key(entry.name)
                for form in (other, other + "町") if not other.endswith("町") else (other,):
                    by_len.setdefault(len(form), []).append((form, entry.name))
        found = {n: tuple(v) for n, v in by_len.items()}
        if len(_SPELLING_FORMS) > 4096:
            _SPELLING_FORMS.clear()
        _SPELLING_FORMS[cache_key] = found
    return found


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
