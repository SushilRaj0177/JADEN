"""JADEN: Main normalization engine and pipeline orchestrator.

Orchestrates multi-stage deterministic normalization:
1. Sanitization & Unicode Homogenization (NFKC, context-aware Chōonpu)
2. Block-bounded Kanji Numeral Normalization
3. Administrative Boundary Resolution (Trie-based, O(L)) with Ambiguity Detection
4. Kyoto Intersection Grammar & Hokkaido Cardinal Grid Parsing
5. Chome-Ban-Go & Banchi-Edaban Finite-State Automaton with Oaza/Koaza segmentation
6. Building, Floor, and Unit Disentanglement
7. Canonical String Formatting & Four-Tier Taxonomy Classification
"""

import dataclasses
import re
import time
import unicodedata
from typing import Any, Optional, Dict, List, Tuple, Final

from .models.codes import TaxonomyTier, AddressRegime
from .models.address import AddressComponents, NormalizedAddress
from .models.validation import ValidationResult, ValidationStatus
from .core.sanitizer import sanitize_address_text, _LEADING_LABEL
from .core.kanji_numerals import normalize_kanji_numerals_in_blocks
from .parsers.administrative import AdministrativeParser
from .parsers.kyoto import KyotoParser
from .parsers.hokkaido import HokkaidoParser
from .parsers.fsm import BlockFSM
from .parsers.building import BuildingParser
from .parsers.town import (resolve_town, expand_candidates, town_variants, koaza_remainder, near_towns,
                           unmarked_koaza, lot_series_follows,
                           TownResolution)
from .data.gazetteer import Gazetteer, TownMatch, get_gazetteer
from .core.townkey import fold_same_length, one_edit_apart, spelling_key, town_key
from .data.loader import MunicipalityRecord
from .data.former import get_former_municipalities
from .readings import kana_reading, romaji_address
from .romaji import looks_romanized, romaji_to_japanese

# A postal code written with 〒 anywhere, or bare NNN-NNNN at either end of the input
_POSTAL_MARKED: Final[re.Pattern[str]] = re.compile(r"(?:〒|郵便番号)\s*[:：]?\s*(\d{3})-?(\d{4})")
_POSTAL_BARE_EDGE: Final[re.Pattern[str]] = re.compile(r"(?:^\s*(\d{3})-(\d{4})(?!\d)|(?<![\d-])(\d{3})-(\d{4})\s*$)")
# Whitespace right after a block number, unless a block marker follows ('4 丁目', '2 番')
_AFTER_BLOCK_NUMBER: Final[re.Pattern[str]] = re.compile(
    r"(?:(?<=\d)|(?<=-[イロハニホヘト甲乙丙丁]))\s+(?!\d*\s*(?:丁目|番|号(?!室))|[の\-])")
_BRACKETED: Final[re.Pattern[str]] = re.compile(r"\s*[(（][^)）]*[)）]")
# Spaces between block markers and the next number ('4丁目 2番 8号'), but not before a room ('2番 301号室')
_INNER_BLOCK_SPACE: Final[re.Pattern[str]] = re.compile(r"(?:(?<=丁目)|(?<=番地)|(?<=[番の]))\s+(?=\d)(?!\d+\s*号室)")
# Town text containing a number that is part of the name, not a block number:
# '忠和1条', '芽室南2線', '五十嵐3の町', '古町通6番町', '五福1区'
_NUMBERED_TOWN: Final[re.Pattern[str]] = re.compile(
    r"^\D+\d+(?:(?!\d|丁目|番(?!町|耕地)|号|-|の\d|\s|$)|丁目(?=[^\d\s\-番号の]))")
# Locators that belong to the place even when unregistered: Iwate '8地割', land readjustment
# '8街区', Ishikawa '10部': the number after them is the lot
_STRUCTURAL_TOWN: Final[re.Pattern[str]] = re.compile(r"^(?P<town>\D+?\d+(?:地割|街区|部|区|番耕地|耕地))(?=\d)")
# A lot-series lot after the 丁目 ('相生町1-乙394'): kept as written
_SERIES_LOT: Final[re.Pattern[str]] = re.compile(
    r"^-?(?P<lot>[甲乙丙丁戊己庚辛壬癸イロハニホヘトチリヌルヲワカヨタレソツネナラム]\d+(?:-\d+)?)(?P<rest>.*)$")

# A place with no lot number of its own: the words stand where the number would ('支笏湖温泉番外地')
_UNNUMBERED_LOT: Final[re.Pattern[str]] = re.compile(
    r"^(?P<town>\D*?)(?P<lot>官有地無番地|官有無番地|無番地|番外地)(?P<rest>.*)$")

# Upper bound on municipalities searched for a town written without its municipality
_MAX_GLOBAL_TOWN_CANDIDATES: Final[int] = 500


def _before_koaza(town: str) -> str:
    """The part of a written town before its 字: '常海橋字稲葉' -> '常海橋', '大字南長野字幅下' -> '大字南長野'."""
    start = 2 if town.startswith("大字") else 1
    cut = town.find("字", start)
    return town[:cut] if cut > 0 else town


def extract_postal_code(raw: str) -> Optional[str]:
    """Returns the postal code written in an address as 'NNN-NNNN', if any."""
    text = unicodedata.normalize("NFKC", raw or "").replace("ー", "-").replace("−", "-")
    text = _LEADING_LABEL.sub("", text.strip())
    m = _POSTAL_MARKED.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = _POSTAL_BARE_EDGE.search(text)
    if m:
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        return f"{a}-{b}"
    return None


class AddressNormalizer:
    """Production-grade Japanese address normalization engine."""

    def __init__(self, gazetteer: Optional[Gazetteer] = None, use_gazetteer: bool = True,
                 autocorrect: bool = False) -> None:
        """
        Args:
            gazetteer: Town gazetteer to use (default: the bundled / user-updated one).
            use_gazetteer: False gives the parser-only behaviour of v0.1.
            autocorrect: Replace a misspelt town by the registered one when exactly one registered
                town is one character away. The original spelling is kept in
                ``components.town_corrected_from`` and in the notes. Off by default: without it the
                correction is only offered in ``suggestions``.
        """
        self.admin_parser = AdministrativeParser()
        self.registry = self.admin_parser.registry
        self._gazetteer = gazetteer
        self.use_gazetteer = use_gazetteer
        self.autocorrect = autocorrect

    @property
    def gazetteer(self) -> Optional[Gazetteer]:
        if not self.use_gazetteer:
            return None
        if self._gazetteer is None:
            self._gazetteer = get_gazetteer()
        return self._gazetteer if self._gazetteer.available else None

    def normalize(self, raw_address: str, autocorrect: Optional[bool] = None) -> NormalizedAddress:
        """Normalizes a raw Japanese (or romanized) address into canonical structured form.

        Args:
            raw_address: Raw user-input address string.
            autocorrect: Overrides the engine's ``autocorrect`` setting for this call.
        """
        if self.use_gazetteer and raw_address and looks_romanized(raw_address):
            converted = romaji_to_japanese(raw_address)
            if converted is not None:
                japanese, romaji_notes = converted
                res = self._normalize(japanese, allow_reread=True)
                return dataclasses.replace(res, input_raw=raw_address, notes=tuple(romaji_notes) + res.notes)
        res = self._normalize(raw_address, allow_reread=True)
        if res.components.town_verified is False and res.components.lg_code and not res.components.is_ambiguous:
            res = self._with_corrections(res, self.autocorrect if autocorrect is None else autocorrect)
        return res

    def _with_corrections(self, res: NormalizedAddress, apply: bool) -> NormalizedAddress:
        """Offers (or applies) the registered town a misspelt one most likely stands for."""
        gaz = self.gazetteer
        c = res.components
        muni = self.registry.get_municipality_by_code(c.lg_code) if c.lg_code else None
        written = c.town or ""
        if gaz is None or muni is None or not written or written not in res.input_sanitized:
            return res
        corrected: List[Tuple[str, NormalizedAddress]] = []
        head = written
        # The whole town text first; then only the part before a 字 ('常海橋字稲葉' -> '常海橋')
        for part in dict.fromkeys((written, _before_koaza(written))):
            prefix = "大字" if part.startswith("大字") else ("字" if part.startswith("字") else "")
            for m in (self.registry.wards_of(muni) or [muni]):
                for name in near_towns(gaz, m.lg_code, part):
                    # Keep 大字 / 字 the way the input wrote it, whichever way the registry spells the town
                    bare = name[2:] if name.startswith("大字") else (name[1:] if name.startswith("字") else name)
                    plain = prefix + bare
                    fixed = self._normalize(res.input_sanitized.replace(part, plain, 1), allow_reread=False)
                    if fixed.components.town_verified and fixed.canonical not in [x.canonical for _, x in corrected]:
                        corrected.append((plain, fixed))
            if corrected:
                head = part
                break
        if not corrected:
            return res
        suggestions = tuple(x.canonical for _, x in corrected)
        if apply and len(corrected) == 1 and len(spelling_key(head)) >= 3:
            name, fixed = corrected[0]
            note = f"corrected town '{head}' to the registered '{name}' (one character differs)"
            return dataclasses.replace(
                fixed, input_raw=res.input_raw, input_sanitized=res.input_sanitized,
                components=dataclasses.replace(fixed.components, town_corrected_from=head),
                notes=(note,) + fixed.notes)
        names = "、".join(name for name, _ in corrected[:5])
        return dataclasses.replace(
            res, suggestions=suggestions,
            notes=res.notes + (f"did you mean {names}? '{head}' is one character away",))

    def _normalize(self, raw_address: str, allow_reread: bool) -> NormalizedAddress:
        """Normalizes a raw Japanese address string into canonical structured form.

        Args:
            raw_address: Raw user-input address string.

        Returns:
            NormalizedAddress containing structured components, canonical string,
            confidence score, taxonomy tier classifications, and parse latency.
        """
        start_time_ns = time.perf_counter_ns()

        if not raw_address or not raw_address.strip():
            return NormalizedAddress(
                input_raw=raw_address or "",
                input_sanitized="",
                canonical="",
                components=AddressComponents(),
                tier_map={},
                confidence_score=0.0,
                latency_microseconds=0.0,
            )

        # Stage 1: Sanitization & Unicode homogenization
        postal_code = extract_postal_code(raw_address)
        sanitized = sanitize_address_text(raw_address)
        if postal_code:
            # Postal codes written after the address or mid-string are not address text
            sanitized = _POSTAL_MARKED.sub(" ", sanitized)
            sanitized = re.sub(rf"(?<![\d-]){postal_code}\s*$", "", sanitized)
            sanitized = re.sub(r"\s+", " ", sanitized).strip()

        # Stage 2: Context-bounded Kanji numeral conversion
        working_text = normalize_kanji_numerals_in_blocks(sanitized)

        tier_map: Dict[str, str] = {}
        confidence = 1.0
        notes: List[str] = []

        # Stage 3: Administrative Boundary Resolution
        admin_res = self.admin_parser.parse(working_text)
        pref_rec = admin_res.prefecture
        muni_rec = admin_res.municipality
        post_admin_text = admin_res.remaining_text
        is_pref_inferred = admin_res.is_prefecture_inferred
        is_ambiguous = admin_res.is_ambiguous
        ambiguous_candidates = admin_res.ambiguous_candidates
        candidate_records: Tuple[MunicipalityRecord, ...] = admin_res.candidate_records
        matched_raw_name = admin_res.matched_raw_name
        is_contradictory = admin_res.is_contradictory
        municipality_inferred = False
        if (self.gazetteer is not None and not is_ambiguous and not is_contradictory
                and (pref_rec is not None or muni_rec is None)):
            # '大阪府東大阪岩田町…' (市 left out), '静岡県浜松市中央小池町…' (区 left out),
            # '鳥取県烏取市古海…', '熊本市通央区…' (one character wrong): read as the registered name
            # when the town after it is registered there and nothing else reads the text
            repaired_admin = self._repair_municipality(pref_rec, muni_rec, post_admin_text)
            if repaired_admin is not None:
                muni_rec, post_admin_text, why = repaired_admin
                notes.append(why)
                confidence *= 0.9
                if pref_rec is None:
                    pref_rec = self.registry.get_prefecture_by_code(muni_rec.prefecture_code)
                    is_pref_inferred = True
        elif self.gazetteer is not None and is_contradictory and pref_rec is not None:
            # '大分県長島町3-11-13': 長島町 is a municipality of 鹿児島県, and a town of 佐伯市 in 大分県
            local = self._town_of_prefecture(pref_rec, post_admin_text)
            if local is not None:
                muni_rec = local
                is_contradictory = False
                notes.append(f"'{matched_raw_name}' read as a town of {local.name}: the municipality of that name "
                             f"is in another prefecture")
                confidence *= 0.9

        pref_code = pref_rec.code if pref_rec else None
        pref_name = pref_rec.name if pref_rec else None
        lg_code = muni_rec.lg_code if muni_rec else None
        city_name = muni_rec.city if muni_rec else None
        ward_name = muni_rec.ward if muni_rec else None
        county_name = muni_rec.county if muni_rec else None

        if is_contradictory:
            confidence = 0.0
        elif pref_name and is_ambiguous:
            # Prefecture known, but municipal jurisdiction is ambiguous (e.g. '神奈川県南区', '大阪府北区')
            if is_pref_inferred:
                tier_map["prefecture"] = TaxonomyTier.TIER_3_HEURISTIC.value
            else:
                tier_map["prefecture"] = TaxonomyTier.TIER_1_STATUTORY.value
            ward_name = matched_raw_name
            city_name = None
            tier_map["ward"] = TaxonomyTier.TIER_3_HEURISTIC.value
            confidence *= 0.50
        elif pref_name:
            if is_pref_inferred:
                tier_map["prefecture"] = TaxonomyTier.TIER_3_HEURISTIC.value
                confidence *= 0.85
            else:
                tier_map["prefecture"] = TaxonomyTier.TIER_1_STATUTORY.value
        elif is_ambiguous:
            city_name = matched_raw_name
            tier_map["prefecture"] = TaxonomyTier.TIER_3_HEURISTIC.value
            tier_map["municipality"] = TaxonomyTier.TIER_3_HEURISTIC.value
            confidence *= 0.50
        else:
            confidence *= 0.60

        if muni_rec:
            tier_map["municipality"] = TaxonomyTier.TIER_1_STATUTORY.value
            tier_map["lg_code"] = TaxonomyTier.TIER_1_STATUTORY.value
        elif not is_ambiguous:
            confidence *= 0.70

        # Former municipality names ('浦和市', '清水市', '浜松市中区'): the candidates are the current
        # municipalities its area belongs to, and the town decides among them further down
        former_name: Optional[str] = None
        if self.gazetteer is not None and not is_contradictory and not is_ambiguous:
            former = None
            base_len = 0
            if muni_rec is None:
                former = get_former_municipalities().match(post_admin_text, pref_rec.code if pref_rec else None)
                if (former and pref_rec is None and post_admin_text[former[1] - 1] in "町村"
                        and not any(f.county and post_admin_text.startswith(f.county) for f in former[0])):
                    # Without a prefecture, '笠原町…' is as likely a town name as the old town 笠原町
                    former = None
            elif muni_rec.entity_type == "designated_city" and post_admin_text:
                # A ward that no longer exists ('浜松市中区')
                base_len = len(muni_rec.city)
                former = get_former_municipalities().match(muni_rec.city + post_admin_text, muni_rec.prefecture_code)
                if former and former[1] <= base_len:
                    former = None
            if former:
                found, consumed = former
                lgs: List[str] = []
                for f in found:
                    lgs += [lg for lg in f.successors if lg not in lgs]
                records = [r for r in (self.registry.get_municipality_by_code(lg) for lg in lgs) if r is not None]
                if records:
                    former_name = found[0].name
                    post_admin_text = post_admin_text[consumed - base_len:].lstrip()
                    # An absorbed town often lives on as a town name ('土岐郡笠原町2950' -> 多治見市笠原町2950)
                    pool = [x for r in records for x in (self.registry.wards_of(r) or [r])]
                    gaz_ = self.gazetteer

                    def _town_len(text: str) -> int:
                        best = 0
                        for r in pool:
                            m = gaz_.match_town(r.lg_code, text) if gaz_ else None
                            if m is not None and m.entry.records:
                                best = max(best, m.consumed)
                        return best
                    short = former_name if former_name[-1] in "町村" else ""
                    if short and _town_len(short + post_admin_text) > len(short) - 1 >= _town_len(post_admin_text):
                        post_admin_text = short + post_admin_text
                    names = "、".join(f"{r.prefecture_name}{r.name}" for r in records[:6])
                    notes.append(f"{former_name} no longer exists; its area is now part of {names}")
                    prefs = {r.prefecture_code for r in records}
                    if pref_rec is None and len(prefs) == 1:
                        pref_rec = self.registry.get_prefecture_by_code(prefs.pop())
                        is_pref_inferred = True
                    pref_code = pref_rec.code if pref_rec else None
                    pref_name = pref_rec.name if pref_rec else None
                    municipality_inferred = True
                    tier_map["municipality"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                    if len(records) == 1:
                        muni_rec = records[0]
                        lg_code, city_name = muni_rec.lg_code, muni_rec.city
                        ward_name, county_name = muni_rec.ward, muni_rec.county
                        tier_map["lg_code"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                        confidence = 0.85 if is_pref_inferred else 0.90
                    else:
                        muni_rec, lg_code, county_name, ward_name = None, None, None, None
                        city_name = former_name
                        is_ambiguous = True
                        candidate_records = tuple(records)
                        ambiguous_candidates = tuple(f"{r.prefecture_name}{r.name} ({r.lg_code})" for r in records)
                        confidence = 0.50

        # A space after a block number ends the address part: '潮見188 703号室', '北11条西7 ハイツ'
        extra_tail = ""
        # Parenthesized notes ('(…キャンパス内)', '（旧〇〇）') are never part of the locator
        notes_in_brackets = _BRACKETED.findall(post_admin_text)
        if notes_in_brackets:
            post_admin_text = re.sub(r"\s+", " ", _BRACKETED.sub(" ", post_admin_text)).strip()
        post_admin_text = _INNER_BLOCK_SPACE.sub("", post_admin_text)
        split = _AFTER_BLOCK_NUMBER.search(post_admin_text)
        if split:
            post_admin_text, extra_tail = post_admin_text[:split.start()], post_admin_text[split.end():]

        # Stage 4: Conventional Systems (Kyoto & Hokkaido)
        kyoto_clause = None
        hokkaido_clause = None
        text_after_conventions = post_admin_text

        # 4a. Kyoto Street-Intersection Parser
        is_kyoto_candidate = (
            (pref_rec and pref_rec.code == "26" and (city_name and "京都" in city_name))
            or ("通" in post_admin_text and any(d in post_admin_text for d in ["上る", "上ル", "下る", "下ル", "東入", "西入"]))
        )
        if is_kyoto_candidate:
            kyoto_clause, text_after_conventions = KyotoParser.parse(text_after_conventions)
            if kyoto_clause:
                tier_map["kyoto_direction"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                if not pref_name:
                    pref_name = "京都府"
                    pref_code = "26"
                    is_pref_inferred = True
                    city_name = city_name or "京都市"
                    is_ambiguous = False
                    ambiguous_candidates = ()
                    candidate_records = ()
                    tier_map["prefecture"] = TaxonomyTier.TIER_2_CONVENTIONAL.value

        # 4b. Hokkaido Jo-Chome Grid Parser
        is_hokkaido_candidate = (
            (pref_rec and pref_rec.code == "01")
            or (pref_rec is None and "条" in text_after_conventions and "丁目" in text_after_conventions and any(d in text_after_conventions for d in ["北", "南"]))
        )
        hokkaido_known = (
            (pref_rec is not None and pref_rec.code == "01")
            or any(c.prefecture_code == "01" for c in candidate_records)
        )
        if is_hokkaido_candidate or hokkaido_known:
            hokkaido_clause, text_after_conventions = HokkaidoParser.parse(
                text_after_conventions, allow_shorthand=hokkaido_known)
            if hokkaido_clause:
                tier_map["hokkaido_grid"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                if is_ambiguous and matched_raw_name == "中央区" and self.gazetteer is None:
                    # Without the gazetteer: Sapporo is the only city in Japan with Jo-Chome cardinal grid + 中央区
                    muni_rec = self.registry.get_municipality_by_code("011011")
                    city_name = "札幌市"
                    ward_name = "中央区"
                    lg_code = "011011"
                    pref_name = "北海道"
                    pref_code = "01"
                    is_pref_inferred = True
                    is_ambiguous = False
                    ambiguous_candidates = ()
                    candidate_records = ()
                    tier_map["prefecture"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                    confidence = 0.85
                elif not pref_name and not is_ambiguous:
                    pref_rec = self.registry.get_prefecture_by_code("01")   # search Hokkaido's towns
                    pref_name = "北海道"
                    pref_code = "01"
                    is_pref_inferred = True
                    tier_map["prefecture"] = TaxonomyTier.TIER_2_CONVENTIONAL.value

        nothing_recognized = (
            pref_name is None and city_name is None and not is_ambiguous
            and kyoto_clause is None and hokkaido_clause is None
        )

        unnumbered_lot: Optional[str] = None
        no_number = _UNNUMBERED_LOT.match(text_after_conventions)
        if no_number and no_number.group("town"):
            unnumbered_lot = no_number.group("lot")
            text_after_conventions = no_number.group("town")
            extra_tail = f"{no_number.group('rest')} {extra_tail}".strip()

        # Stage 5: Chome-Ban-Go / Banchi-Edaban Block FSM
        has_chome_from_hokkaido = (hokkaido_clause is not None and hokkaido_clause.chome is not None)
        # Numbered town names ('忠和1条', '芽室南2線', '西野9条') look like block numbers to the FSM;
        # a registered town matching the start of the text decides where the town ends.
        fixed_town = self._registered_town_prefix(text_after_conventions, muni_rec, candidate_records,
                                                  pref_rec if muni_rec is None else None)
        if fixed_town:
            block_dict, _, tail_text = BlockFSM.parse(
                text_after_conventions[len(fixed_town):], has_chome_already=has_chome_from_hokkaido)
            town_name = fixed_town
            written_aza = fixed_town.startswith(("大字", "字")) and block_dict["chome"] is None
            if (_STRUCTURAL_TOWN.match(text_after_conventions) or written_aza) and block_dict["ban"] is not None:
                # After 地割 / 街区 / 部 / 区 the numbers are lot numbers
                block_dict.update(banchi=block_dict["ban"], edaban=block_dict["go"], ban=None, go=None,
                                  address_regime=AddressRegime.CHIBAN.value)
        else:
            block_dict, town_name, tail_text = BlockFSM.parse(
                text_after_conventions,
                has_chome_already=has_chome_from_hokkaido
            )
        if extra_tail:
            tail_text = f"{tail_text} {extra_tail}".strip()

        chome_val = block_dict["chome"] or (hokkaido_clause.chome if hokkaido_clause else None)
        ban_val = block_dict["ban"]
        go_val = block_dict["go"]
        banchi_val = block_dict["banchi"]
        edaban_val = block_dict["edaban"]
        oaza_val = block_dict["oaza"]
        koaza_val = block_dict["koaza"]
        regime_val = block_dict["address_regime"]

        # Stage 5b: Town-level verification against the national gazetteer
        gaz = self.gazetteer
        town_res: Optional[TownResolution] = None
        if hokkaido_clause is not None and hokkaido_clause.jo is not None:
            town_text = f"{hokkaido_clause.cardinal_ns}{hokkaido_clause.jo}条{hokkaido_clause.cardinal_ew}"
        else:
            town_text = town_name
        has_numbers = any(v is not None for v in (chome_val, ban_val, banchi_val)) or unnumbered_lot is not None
        first_number = next((v for v in (chome_val, ban_val, banchi_val) if v is not None), None)

        skip_town_resolution = False
        if (gaz is not None and allow_reread and muni_rec is not None and not is_ambiguous and not is_contradictory
                and kyoto_clause is None and hokkaido_clause is None and former_name is None):
            alt = self._town_reading(gaz, working_text, post_admin_text, pref_rec, is_pref_inferred, muni_rec, town_text)
            if alt is not None:
                kind, munis, surface = alt
                if kind == "town":
                    # '松川町沼袋...' is the town 松川町沼袋 in 福島市, not the municipality 松川町 (Nagano)
                    target = munis[0]
                    prefix = f"〒{postal_code} " if postal_code else ""
                    reread = self._normalize(f"{prefix}{target.prefecture_name}{target.name}{surface}{post_admin_text}",
                                             allow_reread=False)
                    note = (f"'{surface}' read as part of the town name in {target.prefecture_name}{target.name}: "
                            f"the rest of the address is not registered in the municipality {surface}")
                    return dataclasses.replace(
                        reread,
                        input_raw=raw_address,
                        input_sanitized=sanitized,
                        components=dataclasses.replace(reread.components, municipality_inferred=True,
                                                       prefecture_inferred=is_pref_inferred),
                        confidence_score=min(reread.confidence_score, 0.85),
                        notes=(note,) + reread.notes,
                    )
                # Both readings are possible: the municipality 栄町, or a town called 栄町 in another city
                notes.append(f"'{surface}' is a municipality and also a town name in {len(munis) - 1} other place(s)")
                candidate_records = tuple(munis)
                ambiguous_candidates = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in munis)
                is_ambiguous = True
                muni_rec = None
                lg_code = county_name = ward_name = None
                city_name = surface
                if is_pref_inferred:
                    pref_rec, pref_name, pref_code = None, None, None
                    tier_map.pop("prefecture", None)
                tier_map["municipality"] = TaxonomyTier.TIER_3_HEURISTIC.value
                tier_map.pop("lg_code", None)
                confidence = 0.50
                skip_town_resolution = True

        if gaz is not None and not is_contradictory and not skip_town_resolution:
            if nothing_recognized:
                # No prefecture or municipality written: deduce it from the postal code or a town name
                # that exists in only a few places, never from free text without block numbers.
                candidates = self._global_candidates(gaz, town_text, postal_code, has_numbers, first_number)
            elif kyoto_clause is not None and muni_rec is None and not is_ambiguous:
                kyoto_city = self.registry.get_municipality_by_code("261009")
                candidates = self.registry.wards_of(kyoto_city) if kyoto_city else []
            else:
                candidates = expand_candidates(
                    self.registry, muni_rec, candidate_records if is_ambiguous else (),
                    pref_code if (pref_rec is not None and muni_rec is None and not is_ambiguous) else None,
                )
            chome_explicit = block_dict["chome_explicit"] or hokkaido_clause is not None
            if (pref_rec is not None and muni_rec is None and not is_ambiguous and not is_pref_inferred
                    and not working_text.startswith(pref_rec.name) and town_text):
                # Only a prefecture stem was read ('兵庫北4-1-1'): the stem may belong to the town name
                # (佐賀市兵庫北). A town matching the whole text outranks a short town after the stem.
                whole = self._global_candidates(gaz, pref_rec.stem + town_text, postal_code, has_numbers, first_number)
                if whole:
                    short_res = resolve_town(gaz, candidates, town_text, chome_val, postal_code, chome_explicit,
                                             first_number) if len(town_text) >= 2 else None
                    if short_res is not None and short_res.municipality is not None and short_res.town_verified:
                        candidates = list(candidates) + [w for w in whole if w not in candidates]
                    else:
                        # '宮崎駅東3丁目', '兵庫塚町281': the whole text is the town, the stem is not a prefecture
                        candidates, town_text = whole, pref_rec.stem + town_text
                        pref_rec, pref_name, pref_code, is_pref_inferred = None, None, None, True
            town_res = resolve_town(gaz, candidates, town_text, chome_val, postal_code, chome_explicit, first_number)
            if (town_res.resolved_from_candidates and admin_res.is_ambiguous and matched_raw_name
                    and matched_raw_name[-1] in "町村" and town_text):
                # '金山町金山' resolved among the two municipalities called 金山町 may still be the
                # town 金山町金山 of a third place (下呂市): then nothing is settled.
                known = {c.lg_code for c in candidate_records}
                elsewhere = [lg for lg, m in gaz.municipalities_with_town(matched_raw_name + town_text)
                             if m.exact and lg not in known and (pref_rec is None or is_pref_inferred or lg[:2] == pref_rec.code)]
                if elsewhere and town_res.municipality is not None:
                    others = [r for r in (self.registry.get_municipality_by_code(lg) for lg in elsewhere) if r]
                    town_res = TownResolution(
                        remaining_candidates=(town_res.municipality, *others),
                        postal_code=postal_code,
                        notes=(f"'{matched_raw_name}{town_text}' is also a town name in {len(others)} other place(s)",),
                    )
            notes.extend(town_res.notes)
            chosen = town_res.municipality

            if chosen is not None and (muni_rec is None or chosen.lg_code != muni_rec.lg_code):
                # Adopt the single municipality the town / postal code points to
                muni_rec = chosen
                if pref_rec is None or pref_rec.code != chosen.prefecture_code:
                    pref_rec = self.registry.get_prefecture_by_code(chosen.prefecture_code)
                    is_pref_inferred = True
                pref_code = pref_rec.code if pref_rec else None
                pref_name = pref_rec.name if pref_rec else None
                lg_code = chosen.lg_code
                city_name = chosen.city
                ward_name = chosen.ward
                county_name = chosen.county
                municipality_inferred = True
                is_ambiguous = False
                ambiguous_candidates = ()
                candidate_records = ()
                tier_map["prefecture"] = (TaxonomyTier.TIER_3_HEURISTIC.value if is_pref_inferred
                                          else TaxonomyTier.TIER_1_STATUTORY.value)
                tier_map["municipality"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                tier_map["lg_code"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                tier_map.pop("ward", None)
                if nothing_recognized:
                    notes.append(f"municipality deduced from the {'postal code' if not town_res.match else 'town name'}: "
                                 f"{chosen.prefecture_name}{chosen.name} is the only match in Japan")
                    confidence = 0.75
                else:
                    confidence = 0.85 if is_pref_inferred else 0.90
                nothing_recognized = False
            elif chosen is None and town_res.remaining_candidates and (
                    is_ambiguous or nothing_recognized
                    or (pref_rec is not None and muni_rec is None and 1 < len(town_res.remaining_candidates) < len(candidates))):
                narrowed = town_res.remaining_candidates
                if True:
                    if nothing_recognized:
                        is_ambiguous = True
                        is_pref_inferred = True
                        city_name = None
                        confidence = 0.30
                        tier_map["municipality"] = TaxonomyTier.TIER_3_HEURISTIC.value
                        nothing_recognized = False
                    elif not is_ambiguous:
                        # Prefecture written, municipality left out, and the town is in more than one of them
                        is_ambiguous = True
                        city_name = None
                        confidence = 0.50
                        tier_map["municipality"] = TaxonomyTier.TIER_3_HEURISTIC.value
                    before = {c.lg_code for c in candidate_records}
                    after = {c.lg_code for c in narrowed}
                    if after != before:
                        if candidate_records and after < before:
                            notes.append(f"town narrowed {len(candidate_records)} candidate municipalities to {len(narrowed)}")
                        candidate_records = narrowed
                        ambiguous_candidates = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in narrowed)

        # Only a prefecture stem was recognized ('東京タワー' -> 東京) and nothing after it is a registered
        # town or a block number: a name that mentions a place, so the text is not rewritten as an address
        stem_only_name = (
            pref_rec is not None and muni_rec is None and not is_ambiguous and not is_pref_inferred
            and not working_text.startswith(pref_rec.name) and not has_numbers
            and kyoto_clause is None and hokkaido_clause is None
            and (town_res is None or town_res.match is None)
        )

        # Validation Guard: Reject inputs with zero verified Japanese administrative or conventional entities
        if nothing_recognized:
            latency_us = (time.perf_counter_ns() - start_time_ns) / 1_000.0
            return NormalizedAddress(
                input_raw=raw_address,
                input_sanitized=sanitized,
                canonical=sanitized,
                components=AddressComponents(unparsed_tail=sanitized),
                tier_map={},
                confidence_score=0.0,
                latency_microseconds=round(latency_us, 2),
            )

        # Gazetteer-guided reading of the block numbers and the registered town spelling
        match = town_res.match if town_res else None
        chome_verified = town_res.chome_verified if town_res else None
        chome_unlisted = town_res.chome_unlisted if town_res else False
        record = town_res.record if town_res else None
        variant = town_res.variant if town_res else None
        if match is not None and variant in ("banchou", "no"):
            # The first number belongs to the registered name ('つつじが丘南1番町', '本町六の')
            lot_style = banchi_val is not None
            nums = [v for v in (chome_val, ban_val, go_val, banchi_val, edaban_val) if v is not None]
            rest = nums[1:]
            chome_val = ban_val = go_val = banchi_val = edaban_val = None
            if variant == "no" and rest and rest[0] in match.entry.chomes:
                chome_val, rest = rest[0], rest[1:]
                chome_verified = True
            ban_val = rest[0] if rest else None
            go_val = rest[1] if len(rest) > 1 else None
            regime_val = AddressRegime.UNSPECIFIED.value
            if lot_style and chome_val is None:
                # '鴻之台1丁目72番地' is 鴻之台1番町, lot 72
                banchi_val, edaban_val, ban_val, go_val = ban_val, go_val, None, None
                regime_val = AddressRegime.CHIBAN.value
            record = match.entry.record_for(chome_val)
            notes.append(f"read '{town_text}' with its first number as the registered town {match.entry.name}")
        elif match is not None and variant == "machi":
            notes.append(f"read '{town_text}' as the registered town {match.entry.name}")
        elif match is not None and variant == "kana":
            notes.append(f"read '{town_text}' by its reading as the registered town {match.entry.name}")
        partial_tail = ""
        lot_number: Optional[str] = unnumbered_lot
        if unnumbered_lot:
            regime_val = AddressRegime.CHIBAN.value
        if (match is not None and (chome_verified is False or chome_unlisted) and not block_dict["chome_explicit"]
                and ban_val is not None and gaz is not None and lg_code):
            # Towns registered as '本町六の一丁目': '本町6-1-79' is 本町六の 1丁目 79番
            alt_entry = gaz.towns_in(lg_code).get(town_key(f"{town_text}{chome_val}の"))
            if alt_entry is not None and ban_val in alt_entry.chomes:
                notes[:] = [n for n in notes if "does not exist" not in n and "is not in the registry" not in n]
                chome_unlisted = False
                notes.append(f"read {town_text}{chome_val}-{ban_val} as the registered {alt_entry.name}{ban_val}丁目")
                town_text = alt_entry.name
                match = TownMatch(lg_code, alt_entry, len(town_text), exact=True)
                chome_val, ban_val, go_val = ban_val, go_val, None
                if tail_text.startswith("-") and tail_text[1:].split(" ")[0].isdigit():
                    go_val = int(tail_text[1:].split(" ")[0])
                    tail_text = tail_text[1 + len(str(go_val)):].strip()
                chome_verified = True
                record = alt_entry.record_for(chome_val)
        if match is not None and hokkaido_clause is None:
            entry = match.entry
            chome_town = entry.has_chome and all(r.chome is not None for r in entry.records)
            lot_possible = not entry.has_chome or (not chome_town and chome_val not in entry.chomes)
            if (lot_possible and chome_val is not None and not block_dict["chome_explicit"]
                    and ban_val is not None and go_val is not None):
                # A town without 丁目 written 'N-N-N' is a three-part lot number (e.g. Iwate's
                # 地割: '西見前20-113-1'), not 丁目-番-号; keep it as written instead of guessing labels.
                lot_number = f"{chome_val}-{ban_val}-{go_val}"
                notes[:] = [n for n in notes if "does not exist" not in n and "is not in the registry" not in n
                            and "is not listed" not in n]
                chome_unlisted = False
                notes.append(f"{entry.name} is not divided into 丁目; kept {lot_number} as a lot number")
                banchi_val, edaban_val = chome_val, ban_val
                chome_val = ban_val = go_val = None
                regime_val = AddressRegime.CHIBAN.value
                chome_verified = None
                record = entry.record_for(None)
            if chome_town and chome_val is None and banchi_val is None and ban_val is not None and ban_val in entry.chomes:
                # Every part of this town is a 丁目, so '六本木6-10' is 6丁目10番 and '六本木6' is 6丁目
                notes.append(f"{entry.name} is divided into 丁目; read {ban_val}" + (f"-{go_val}" if go_val is not None else "")
                             + f" as {ban_val}丁目" + (f"{go_val}番" if go_val is not None else ""))
                chome_val, ban_val, go_val = ban_val, go_val, None
                # 丁目 towns may still use 地番 ('東町1丁目220番地'), so the regime stays unspecified
                regime_val = AddressRegime.UNSPECIFIED.value
                chome_verified = True
                record = entry.record_for(chome_val)
            elif (entry.name.startswith(("大字", "字")) and not entry.has_chome and chome_val is None
                  and banchi_val is None and ban_val is not None and kyoto_clause is None):
                # A registered 大字 / 字 is a cadastral area (地番): '南長野692-2' is 692番地の2, not 692番2号
                banchi_val, edaban_val, ban_val, go_val = ban_val, go_val, None, None
                regime_val = AddressRegime.CHIBAN.value
            registered = entry.name
            user_part = town_text[:match.consumed]
            # 大字 / 字 is kept the way the input wrote it, whichever way the registry spells the town:
            # writing 大字 says the area is cadastral, and dropping it would lose that
            for prefix in ("大字", "字"):
                if registered.startswith(prefix) and not user_part.startswith(prefix):
                    registered = registered[len(prefix):]
                    break
                if user_part.startswith(prefix) and not registered.startswith(("大字", "字")) and variant is None:
                    registered = prefix + registered
                    break
            remainder = town_text[match.consumed:]
            if (remainder and not has_numbers and len(remainder) >= 3 and remainder.endswith("内")
                    and not koaza_remainder(remainder)):
                # '村松町愛媛製紙株式会社内', '基町ショッピングセンター内': inside a facility of that town
                tail_text = f"{remainder} {tail_text}".strip()
                remainder = ""
            elif (remainder and not match.exact and not koaza_remainder(remainder)
                    and not town_text.startswith(("大字", "字"))):
                partial_tail = remainder
            town_name = registered + remainder
            if remainder and entry.records and entry.records[0].kind == "1" and koaza_val is None:
                koaza_val = remainder[1:] if remainder.startswith("字") else remainder

        # A lot with a kana suffix ('大栃1800-イ'): kept as written
        suffix = re.match(r"^-([イロハニホヘトチリヌルヲ甲乙丙丁])(?![\d])", tail_text)
        if suffix and lot_number is None and go_val is None and edaban_val is None and (ban_val or banchi_val):
            lot_number = f"{ban_val or banchi_val}-{suffix.group(1)}"
            banchi_val, ban_val = ban_val or banchi_val, None
            tail_text = tail_text[suffix.end():].strip()
            regime_val = AddressRegime.CHIBAN.value
        # A lot-series lot after the 丁目 or town ('相生町1-乙394', '1丁目乙394'): kept as written
        if lot_number is None and ban_val is None and banchi_val is None:
            series = _SERIES_LOT.match(tail_text)
            if series:
                lot_number, tail_text = series.group("lot"), series.group("rest").strip()
                regime_val = AddressRegime.CHIBAN.value

        # Kyoto conventional navigation addresses strictly use cadastral lot numbers (地番)
        if kyoto_clause and (ban_val is not None and banchi_val is None):
            banchi_val = ban_val
            edaban_val = go_val
            ban_val = None
            go_val = None
            regime_val = AddressRegime.CHIBAN.value

        # Block-level check (街区レベル位置参照情報), when that prefecture's block data is installed
        block_point = None
        block_verified: Optional[bool] = None
        block_no = ban_val if ban_val is not None else banchi_val
        if (gaz is not None and match is not None and lg_code and block_no is not None and not is_ambiguous
                and chome_verified is not False and gaz.blocks_available(lg_code[:2])):
            block_point = gaz.block_point(lg_code, match.entry.name, chome_val, block_no)
            block_verified = block_point is not None
            if block_point is not None and regime_val == AddressRegime.UNSPECIFIED.value:
                # The block data records whether this block uses 住居表示 or 地番
                if block_point.jukyo_hyoji:
                    regime_val = AddressRegime.GAIKU_HOSHIKI.value
                else:
                    regime_val = AddressRegime.CHIBAN.value
                    if ban_val is not None:
                        banchi_val, edaban_val, ban_val, go_val = ban_val, go_val, None, None
            elif block_point is None:
                notes.append(f"block {block_no} is not in the MLIT block-level data for this town")

        if county_name:
            tier_map["county"] = TaxonomyTier.TIER_1_STATUTORY.value
        if town_name:
            tier_map["town"] = (TaxonomyTier.TIER_1_STATUTORY.value if match is not None
                                else TaxonomyTier.TIER_3_HEURISTIC.value)
        if oaza_val:
            tier_map["oaza"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if koaza_val:
            tier_map["koaza"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if chome_val is not None:
            tier_map["chome"] = (TaxonomyTier.TIER_1_STATUTORY.value if chome_verified
                                 else TaxonomyTier.TIER_2_CONVENTIONAL.value)
        if ban_val is not None:
            tier_map["ban"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
        if go_val is not None:
            tier_map["go"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
        if banchi_val is not None:
            tier_map["banchi"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
        if edaban_val is not None:
            tier_map["edaban"] = TaxonomyTier.TIER_2_CONVENTIONAL.value

        # Stage 6: Building, Floor, and Unit Disentanglement
        building_name, floor_val, unit_val = BuildingParser.parse(tail_text)
        if notes_in_brackets:
            building_name = " ".join(x for x in [building_name] + [n.strip() for n in notes_in_brackets] if x)

        if building_name:
            tier_map["building"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if floor_val:
            tier_map["floor"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if unit_val:
            tier_map["unit"] = TaxonomyTier.TIER_3_HEURISTIC.value

        # Assembling canonical representation
        canonical_parts = []
        if pref_name:
            canonical_parts.append(pref_name)
        if county_name:
            canonical_parts.append(county_name)
        if city_name:
            canonical_parts.append(city_name)
        if ward_name and ward_name not in (city_name or ""):
            canonical_parts.append(ward_name)

        if kyoto_clause:
            canonical_parts.append(kyoto_clause.raw_clause)

        if town_name:
            canonical_parts.append(town_name)

        if hokkaido_clause:
            canonical_parts.append(f"{hokkaido_clause.cardinal_ns}{hokkaido_clause.jo}条{hokkaido_clause.cardinal_ew}{hokkaido_clause.chome}丁目")

        # Block / Lot string formatting
        if chome_val is not None and not hokkaido_clause:
            canonical_parts.append(f"{chome_val}丁目")

        if lot_number is not None:
            canonical_parts.append(lot_number)
        elif ban_val is not None and go_val is not None:
            canonical_parts.append(f"{ban_val}番{go_val}号")
        elif ban_val is not None:
            canonical_parts.append(f"{ban_val}番")
        elif banchi_val is not None and edaban_val is not None:
            canonical_parts.append(f"{banchi_val}番地の{edaban_val}")
        elif banchi_val is not None:
            canonical_parts.append(f"{banchi_val}番地")

        # Building & Unit
        secondary_parts = []
        if building_name:
            secondary_parts.append(building_name)
        if floor_val:
            secondary_parts.append(floor_val)
        if unit_val:
            secondary_parts.append(unit_val)

        base_addr = sanitized if stem_only_name else "".join(canonical_parts)
        if secondary_parts:
            canonical_str = f"{base_addr} {' '.join(secondary_parts)}"
        else:
            canonical_str = base_addr

        town_verified = town_res.town_verified if town_res else None
        if (town_res is not None and town_res.municipality is None and town_text and muni_rec is not None
                and not is_ambiguous and gaz is not None and self.registry.wards_of(muni_rec)):
            # A designated city whose wards were searched without success ('札幌市立白石中学校')
            town_verified = False
            notes.append(f"town '{town_text}' is not registered in any ward of {muni_rec.name}")
        if partial_tail and town_verified and not has_numbers:
            # '高岡市立野村小学校' starts with the town 立野 but the rest is not part of an address
            town_verified = False
            notes.append(f"'{partial_tail}' after the town {match.entry.name if match else ''} is not part of an address")

        # Postal code: keep the written one; otherwise fill it in when the town has exactly one
        postal_out = postal_code
        postal_consistent = town_res.postal_consistent if town_res else None
        if postal_out is None and gaz is not None and lg_code and not is_ambiguous:
            # Japan Post lists some 字 as towns of their own ('平良久貝'), so the town as written comes
            # first, then the registered town it belongs to, then the municipality-wide code
            codes: Optional[List[str]] = None
            for name in dict.fromkeys(n for n in (town_name, match.entry.name if match else None) if n):
                codes = gaz.postal_codes_of_town(lg_code, name, chome_val)
                if codes:
                    break
            if not codes:
                codes = gaz.postal_codes_for(lg_code, None)
            if len(codes) == 1:
                postal_out = f"{codes[0][:3]}-{codes[0][3:]}"

        components = AddressComponents(
            prefecture_code=pref_code,
            prefecture=pref_name,
            prefecture_inferred=is_pref_inferred,
            lg_code=lg_code,
            county=county_name,
            city=city_name,
            ward=ward_name,
            oaza=oaza_val,
            koaza=koaza_val,
            town=town_name or None,
            chome=chome_val,
            ban=ban_val,
            go=go_val,
            banchi=banchi_val,
            edaban=edaban_val,
            building=building_name,
            floor=floor_val,
            unit=unit_val,
            kyoto_direction=kyoto_clause,
            hokkaido_grid=hokkaido_clause,
            address_regime=regime_val,
            is_ambiguous=is_ambiguous,
            ambiguous_candidates=ambiguous_candidates,
            is_contradictory=is_contradictory,
            unparsed_tail=None if (building_name or floor_val or unit_val) else (tail_text or None),
            municipality_inferred=municipality_inferred,
            town_verified=town_verified,
            chome_verified=chome_verified,
            chome_unlisted=chome_unlisted and chome_val is not None,
            machiaza_id=record.machiaza_id if record else None,
            postal_code=postal_out,
            postal_code_consistent=postal_consistent,
            block_verified=block_verified,
            lot_number=lot_number,
            town_registered_elsewhere=town_res.town_registered_elsewhere if town_res else (),
            former_municipality=former_name,
        )

        # Offline location: the 丁目 / town representative point
        latitude = longitude = None
        location_level = None
        if block_point is not None:
            latitude, longitude = block_point.latitude, block_point.longitude
            location_level = "block"
        elif record is not None:
            latitude, longitude = record.latitude, record.longitude
            location_level = "chome" if record.chome is not None else "town"
        elif match is not None and not is_ambiguous and match.entry.records:
            pts = match.entry.records
            lat_span = max(r.latitude for r in pts) - min(r.latitude for r in pts)
            lon_span = max(r.longitude for r in pts) - min(r.longitude for r in pts)
            if lat_span < 0.03 and lon_span < 0.03:  # roughly 3 km: one compact town
                latitude = round(sum(r.latitude for r in pts) / len(pts), 6)
                longitude = round(sum(r.longitude for r in pts) / len(pts), 6)
                location_level = "town"

        kana = romaji = None
        if lg_code and not is_ambiguous:
            muni_for_reading = muni_rec or self.registry.get_municipality_by_code(lg_code)
            pref_for_reading = self.registry.get_prefecture_by_code(pref_code) if pref_code else None
            kana = kana_reading(pref_for_reading, muni_for_reading, match.entry if match else None)
            romaji = romaji_address(pref_for_reading, muni_for_reading, match.entry if match else None, components)

        latency_us = (time.perf_counter_ns() - start_time_ns) / 1_000.0

        return NormalizedAddress(
            input_raw=raw_address,
            input_sanitized=sanitized,
            canonical=canonical_str,
            components=components,
            tier_map=tier_map,
            confidence_score=round(confidence, 2),
            latency_microseconds=round(latency_us, 2),
            kana=kana,
            romaji=romaji,
            latitude=latitude,
            longitude=longitude,
            location_level=location_level,
            notes=tuple(notes),
        )

    def _town_of_prefecture(self, pref_rec: Any, text: str) -> Optional[MunicipalityRecord]:
        """The one municipality of the prefecture where ``text`` (a name like '長島町' that is a municipality
        elsewhere, then block numbers) is a registered town with that 丁目, or None."""
        gaz = self.gazetteer
        if gaz is None or not re.match(r"^\D{2,}?[町村]", text):
            return None
        block, town_text, _ = BlockFSM.parse(text)
        numbers = [block[k] for k in ("chome", "ban", "banchi") if block[k] is not None]
        if not town_text or not numbers:
            return None
        candidates = expand_candidates(self.registry, None, (), pref_rec.code)
        res = resolve_town(gaz, candidates, town_text, block["chome"], None, block["chome_explicit"], numbers[0])
        if (res.municipality is None or not res.town_verified or res.match is None or not res.match.exact
                or res.chome_verified is False or res.chome_unlisted):
            return None
        return res.municipality

    def _town_reaches_number(self, lg_code: str, text: str) -> bool:
        """True when a registered town of the municipality covers ``text`` up to its block number."""
        gaz = self.gazetteer
        hit = gaz.match_town(lg_code, text) if gaz is not None and text else None
        if hit is None or hit.consumed < 2:
            return False
        after = text[hit.consumed:]
        if (not after or after[0].isdigit() or after[0] in " -" or koaza_remainder(after)
                or after.startswith(("丁目", "番")) or lot_series_follows(after)):
            return True
        koaza = re.match(r"^([^\d\s]{1,6})\d", after)            # '長篠町' + '新田東' + 11
        return koaza is not None and unmarked_koaza(hit, koaza.group(1))

    def _repair_municipality(self, pref_rec: Any, muni_rec: Optional[MunicipalityRecord],
                             text: str) -> Optional[Tuple[MunicipalityRecord, str, str]]:
        """The municipality or ward a mistyped name stands for, proved by the town that follows it.

        Returns (municipality, text after its name, note) or None. Four mistakes are read:
          a ward without 区 after its city     '浜松市中央小池町', '仙台市青葉上杉'
          a ward one character off             '熊本市通央区水前寺'
          a municipality without 市 / 区 / 町 / 村 '大阪府東大阪岩田町', '愛知県名古屋中川区千音寺'
          a municipality one character off     '鳥取県烏取市古海', '福岡県大宰府市向佐野'
        Each needs the registered town after the name to run up to the block number, exactly one
        municipality to fit, and no registered town to read the text as written.
        """
        if not text or self.gazetteer is None:
            return None
        # A name that no longer exists ('浜松市中区', '浦和市') is explained by the former-name step instead
        formers = get_former_municipalities()
        if muni_rec is not None:
            former = formers.match(muni_rec.city + text, muni_rec.prefecture_code)
            if former and former[1] > len(muni_rec.city):
                return None
        elif formers.match(text, pref_rec.code if pref_rec is not None else None):
            return None
        folded = fold_same_length(text)
        reaches = self._town_reaches_number
        if pref_rec is None:
            # No prefecture: only a designated city without 市 followed by one of its wards is certain
            # ('北九州若松区西園町…', '名古屋中川区…')
            found_city: List[Tuple[MunicipalityRecord, int]] = []
            for city in self.registry.list_municipalities():
                if city.entity_type != "designated_city" or len(city.name) < 3:
                    continue
                stem = fold_same_length(city.name[:-1])
                if not folded.startswith(stem):
                    continue
                for w in self.registry.wards_of(city):
                    if w.ward and folded[len(stem):].startswith(fold_same_length(w.ward)):
                        found_city.append((w, len(stem) + len(w.ward)))
            if len(found_city) != 1:
                return None
            ward, used = found_city[0]
            ward_name = ward.ward or ""
            return ward, text[used:].lstrip(), f"read '{text[:used - len(ward_name)]}' as {ward.city}: {ward_name} follows it"

        if muni_rec is not None:
            if muni_rec.entity_type != "designated_city":
                return None
            wards = [w for w in self.registry.wards_of(muni_rec) if w.ward]
            if any(reaches(w.lg_code, text) for w in wards):
                return None
            fits: List[Tuple[MunicipalityRecord, int, str]] = []
            for w in wards:
                stem = fold_same_length((w.ward or "")[:-1])
                if len(stem) >= 2 and folded.startswith(stem) and reaches(w.lg_code, text[len(stem):]):
                    fits.append((w, len(stem), f"read '{text[:len(stem)]}' as {w.ward}: the town after it is registered there"))
            cut = folded.find("区", 0, 6)
            if not fits and cut >= 1:
                written = folded[:cut + 1]
                for w in wards:
                    if one_edit_apart(fold_same_length(w.ward or ""), written) and reaches(w.lg_code, text[cut + 1:]):
                        fits.append((w, cut + 1, f"read '{text[:cut + 1]}' as {w.ward}: {muni_rec.city} has no ward spelt that way"))
            if len({w.lg_code for w, _, _ in fits}) != 1:
                return None
            ward, used, why = fits[0]
            return ward, text[used:].lstrip(), why

        municipalities = self.registry.list_municipalities(pref_rec.code)
        found: List[Tuple[MunicipalityRecord, int, str]] = []
        county = re.match(r"^(\S{1,5}?郡)\s*", folded)
        if county:
            # '名西郡浦庄字上浦…' (the municipality left out) and '最上郡真室川大字…' (町 left out)
            members = [m for m in municipalities if m.county and fold_same_length(m.county) == county.group(1)]
            rest = text[county.end():]
            for m in members:
                stem = fold_same_length(m.name[:-1])
                if len(stem) >= 2 and fold_same_length(rest).startswith(stem) and reaches(m.lg_code, rest[len(stem):]):
                    found.append((m, county.end() + len(stem), f"read '{text[:county.end() + len(stem)]}' as "
                                  f"{m.county}{m.name}: the town after it is registered there"))
            if not found:
                holders = [m for m in members if reaches(m.lg_code, rest)]
                if len(holders) == 1:
                    found.append((holders[0], county.end(), f"the town after {holders[0].county} is in "
                                  f"{holders[0].name}, the only one of its municipalities that has it"))
            if len({m.lg_code for m, _, _ in found}) == 1:
                muni, used, why = found[0]
                return muni, text[used:].lstrip(), why
            return None
        for m in municipalities:
            if m.entity_type == "administrative_ward":
                continue
            stem = fold_same_length(m.name[:-1])
            if len(stem) < 2 or not folded.startswith(stem):
                continue
            rest = text[len(stem):]
            if m.entity_type == "designated_city":
                # The city without 市, then one of its wards ('名古屋中川区千音寺…')
                for w in self.registry.wards_of(m):
                    if w.ward and fold_same_length(rest).startswith(fold_same_length(w.ward)):
                        found.append((w, len(stem) + len(w.ward),
                                      f"read '{text[:len(stem)]}' as {m.name}: {w.ward} follows it"))
            elif reaches(m.lg_code, rest):
                found.append((m, len(stem), f"read '{text[:len(stem)]}' as {m.name}: the town after it is registered there"))
        if not found:
            for end in range(2, min(len(folded), 8) + 1):
                written = folded[:end]
                if written[-1] not in "市区町村" or any(ch.isdigit() for ch in written):
                    continue
                for m in municipalities:
                    if m.entity_type == "administrative_ward" or (end == 2 and m.entity_type != "designated_city"):
                        continue   # two characters are too few, unless a ward of that city follows ('葉市中央区')
                    target = fold_same_length(m.name)
                    if target[-1] != written[-1] or not one_edit_apart(target, written):
                        continue
                    if written[-1] in "町村" and len(target) != len(written):
                        continue  # '栄町' is a town name before it is a shortened '東栄町'
                    if m.entity_type == "designated_city":
                        rest = fold_same_length(text[end:])
                        for w in self.registry.wards_of(m):
                            if w.ward and rest.startswith(fold_same_length(w.ward)):
                                found.append((w, end + len(w.ward), f"read '{text[:end]}' as {m.name}: "
                                              f"no municipality of {pref_rec.name} is spelt that way"))
                    elif reaches(m.lg_code, text[end:]):
                        found.append((m, end, f"read '{text[:end]}' as {m.name}: no municipality of {pref_rec.name} is spelt that way"))
                if found:
                    break
        if len({m.lg_code for m, _, _ in found}) != 1:
            return None
        # The text as written may be a town of the prefecture with the municipality left out
        gaz = self.gazetteer
        for lg, hit in gaz.municipalities_with_town(text):
            if lg[:2] == pref_rec.code and reaches(lg, text):
                return None
        muni, used, why = found[0]
        return muni, text[used:].lstrip(), why

    def _registered_town_prefix(self, text: str, muni_rec: Optional[MunicipalityRecord],
                                candidates: Tuple[MunicipalityRecord, ...], pref_rec) -> Optional[str]:
        """The start of ``text`` when it is a registered town whose name contains a number."""
        gaz = self.gazetteer
        if gaz is None or not _NUMBERED_TOWN.match(text):
            return None
        if muni_rec is not None:
            pool = self.registry.wards_of(muni_rec) or [muni_rec]
        elif candidates:
            pool = list(candidates)
        else:
            return None
        best = None
        for m in pool:
            match = gaz.match_town(m.lg_code, text)
            if match is not None and any(ch.isdigit() for ch in text[:match.consumed]):
                if best is None or match.consumed > best:
                    best = match.consumed
        if best:
            return text[:best]
        structural = _STRUCTURAL_TOWN.match(text)
        return structural.group("town") if structural else None

    def _town_reading(self, gaz: Gazetteer, working_text: str, post_admin_text: str,
                      pref_rec, is_pref_inferred: bool, muni_rec: MunicipalityRecord,
                      town_text: str) -> Optional[Tuple[str, List[MunicipalityRecord], str]]:
        """Checks whether a municipality name like '栄町' should instead be read as a town name.

        Returns None to keep the municipality reading, ('town', [target], surface) when only the
        town reading is registered, or ('ambiguous', [municipality, *towns], surface).
        """
        consumed = working_text[:len(working_text) - len(post_admin_text)].strip()
        surface = consumed
        if pref_rec is not None and not is_pref_inferred:
            for written in (pref_rec.name, pref_rec.stem):
                if surface.startswith(written):
                    surface = surface[len(written):].strip()
                    break
        # Only bare 町 / 村 names collide with town names; '西多摩郡日の出町' or '府中市' do not.
        # A name on its own ('福島町') is taken as the municipality.
        if not surface or surface[-1] not in "町村" or (muni_rec.county and surface.startswith(muni_rec.county)):
            return None
        if not town_text and not re.search(r"\d", post_admin_text):
            return None
        found = [(lg, m) for lg, m in gaz.municipalities_with_town(surface + town_text)
                 if lg != muni_rec.lg_code and m.consumed >= len(surface)]
        if pref_rec is not None and not is_pref_inferred:
            found = [(lg, m) for lg, m in found if lg[:2] == pref_rec.code]
        if not found:
            return None
        muni_verified = (gaz.match_town(muni_rec.lg_code, town_text) is not None) if town_text else None
        exact = [lg for lg, m in found if m.exact]
        if muni_verified and not exact:
            return None
        records = [r for r in (self.registry.get_municipality_by_code(lg) for lg, _ in found) if r is not None]
        if muni_verified is False and len(exact) == 1:
            target = self.registry.get_municipality_by_code(exact[0])
            if target is not None:
                return "town", [target], surface
        return "ambiguous", [muni_rec] + records, surface

    def _global_candidates(self, gaz: Gazetteer, town_text: str, postal_code: Optional[str],
                           has_numbers: bool, first_number: Optional[int] = None) -> List[MunicipalityRecord]:
        lgs: List[str] = []
        if not town_text and not has_numbers:
            return []  # a postal code on its own is not an address
        if postal_code:
            lgs = sorted({p.lg_code for p in gaz.postal_records(postal_code)})
        if not lgs and town_text and has_numbers:
            # Include registered spellings the input may have shortened, so that a town written
            # '伊勢宮' does not look unique when 伊勢宮町 exists elsewhere
            found = gaz.municipalities_with_town(town_text)
            lgs = [lg for lg, m in found if m.exact or koaza_remainder(town_text[m.consumed:])]
            if not lgs:
                # '吉良町中野郷中74': the longest registered 大字 the text starts with, then its 字
                loose = [(lg, m) for lg, m in found if unmarked_koaza(m, town_text[m.consumed:])]
                if loose:
                    longest = max(m.consumed for _, m in loose)
                    lgs = [lg for lg, m in loose if m.consumed == longest]
            lgs += [lg for lg in gaz.municipalities_with_exact_town([t for t, _ in town_variants(town_text, first_number)])
                    if lg not in lgs]
        if len(lgs) > _MAX_GLOBAL_TOWN_CANDIDATES:
            return []
        records = [self.registry.get_municipality_by_code(lg) for lg in lgs]
        return [r for r in records if r is not None]

    def parse(self, raw_address: str) -> AddressComponents:
        """Parses a Japanese address string into granular AddressComponents AST.

        Args:
            raw_address: Raw user-input address string.

        Returns:
            AddressComponents data object with decomposed administrative and block fields.
        """
        return self.normalize(raw_address).components

    def validate(self, raw_address: str, strict: bool = False,
                 autocorrect: Optional[bool] = None) -> ValidationResult:
        """Validates an address string against statutory administrative registries.

        Evaluates:
        - ACCEPTED: Address recognized with valid municipal authority and high confidence.
        - AMBIGUOUS: Omitted prefecture matches multiple statutory municipalities.
        - MALFORMED: Rejected by administrative parser or confidence == 0.0.
        - UNSUPPORTED: Structurally unparsed or unresolvable tail components.

        With the gazetteer available, MALFORMED also covers a 丁目 that does not
        exist in the town and a postal code that belongs to another municipality.
        ``strict=True`` additionally requires the town to be found in the gazetteer.

        Args:
            raw_address: Raw user-input address string.
            strict: Require town-level verification for ACCEPTED.

        Returns:
            ValidationResult with status, validity flag, confidence, and diagnostic message.
        """
        if not raw_address or not raw_address.strip():
            return ValidationResult(
                raw_input=raw_address or "",
                status=ValidationStatus.MALFORMED.value,
                valid=False,
                confidence_score=0.0,
                address_regime=AddressRegime.UNSPECIFIED.value,
                lg_code=None,
                is_ambiguous=False,
                ambiguous_candidates=(),
                message="Empty or whitespace address string.",
            )

        res = self.normalize(raw_address, autocorrect=autocorrect)
        c = res.components
        level = _verification_level(c)
        warnings = tuple(res.notes)
        if c.lg_code and c.precision in ("municipality", "town", "chome") and res.confidence_score > 0:
            warnings += ("no block or lot number: this locates an area, not a building",)
        if c.chome_unlisted:
            warnings += (f"{c.chome}丁目 is not in the registry for {c.town}: accepted, but not verified",)

        def result(status: ValidationStatus, message: str, lg: Optional[str] = None,
                   confidence: Optional[float] = None, regime: Optional[str] = None) -> ValidationResult:
            return ValidationResult(
                raw_input=raw_address,
                status=status.value,
                valid=status == ValidationStatus.ACCEPTED,
                confidence_score=res.confidence_score if confidence is None else confidence,
                address_regime=c.address_regime if regime is None else regime,
                lg_code=lg,
                is_ambiguous=status == ValidationStatus.AMBIGUOUS,
                ambiguous_candidates=c.ambiguous_candidates if status == ValidationStatus.AMBIGUOUS else (),
                message=message,
                verification_level=level if status == ValidationStatus.ACCEPTED else "none",
                warnings=warnings,
                precision=c.precision if res.confidence_score > 0 else "none",
                suggestions=res.suggestions,
            )

        if c.is_contradictory:
            return result(ValidationStatus.MALFORMED,
                          "Contradiction detected: municipality does not belong to specified prefecture.",
                          confidence=0.0)

        if res.confidence_score == 0.0:
            return result(ValidationStatus.MALFORMED,
                          "Input rejected: no recognized Japanese administrative jurisdiction or structure.",
                          confidence=0.0, regime=AddressRegime.UNSPECIFIED.value)

        if c.is_ambiguous:
            return result(ValidationStatus.AMBIGUOUS,
                          f"Ambiguous administrative jurisdiction matches {len(c.ambiguous_candidates)} candidates."
                          if c.prefecture
                          else f"Omitted prefecture matches {len(c.ambiguous_candidates)} statutory municipalities.")

        if c.chome_verified is False:
            return result(ValidationStatus.MALFORMED,
                          "Nonexistent 丁目: " + next(
                              (n for n in res.notes if "does not exist" in n), f"{c.town} has no {c.chome}丁目."),
                          lg=c.lg_code)

        if c.town_registered_elsewhere:
            return result(ValidationStatus.MALFORMED,
                          "Town belongs to a different municipality of the same name: " + next(
                              (n for n in res.notes if "a different" in n), ""),
                          lg=c.lg_code)

        if c.postal_code_consistent is False:
            return result(ValidationStatus.MALFORMED,
                          "Postal code contradicts the address: " + next(
                              (n for n in res.notes if n.startswith("postal code")), "it belongs elsewhere."),
                          lg=c.lg_code)

        if c.unparsed_tail and len(c.unparsed_tail.strip()) > 5:
            return result(ValidationStatus.UNSUPPORTED,
                          f"Input contains unparsed or unsupported tokens: '{c.unparsed_tail}'.",
                          lg=c.lg_code)

        no_numbers = all(v is None for v in (c.chome, c.ban, c.go, c.banchi, c.edaban, c.lot_number))
        if c.town_verified is False and no_numbers and c.hokkaido_grid is None and c.kyoto_direction is None:
            # '高崎市立国府小学校': a municipality followed by text that is neither a registered town
            # nor a block number is a name that mentions a place, not an address
            return result(ValidationStatus.UNSUPPORTED,
                          f"Text after the municipality ('{c.town}') is not a registered town and has no block number.",
                          lg=c.lg_code)

        if strict and c.lg_code is not None and c.town_verified is not True:
            return result(ValidationStatus.UNSUPPORTED,
                          "Strict mode: the town could not be verified against the national gazetteer.",
                          lg=c.lg_code)

        if strict and c.chome_unlisted:
            return result(ValidationStatus.UNSUPPORTED,
                          f"Strict mode: {c.chome}丁目 is not in the registry for {c.town}.",
                          lg=c.lg_code)

        if c.lg_code is not None and res.confidence_score >= 0.5:
            message = {
                "chome": "Municipality, town and 丁目 verified against official registries.",
                "town": "Municipality and town verified against official registries.",
            }.get(level, "Local government entity verified against official statutory registry.")
            return result(ValidationStatus.ACCEPTED, message, lg=c.lg_code)

        return result(ValidationStatus.UNSUPPORTED,
                      "Administrative entity could not be resolved to a local government code.",
                      lg=c.lg_code)


def _verification_level(c: AddressComponents) -> str:
    if c.lg_code is None:
        return "none"
    if c.town_verified:
        return "chome" if c.chome_verified else "town"
    return "municipality"


_DEFAULT_ENGINE: Optional[AddressNormalizer] = None


def get_engine() -> AddressNormalizer:
    """The shared default engine (created on first use)."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AddressNormalizer()
    return _DEFAULT_ENGINE


def normalize(address: str, autocorrect: bool = False) -> NormalizedAddress:
    """Public convenience function to normalize a Japanese address."""
    return get_engine().normalize(address, autocorrect=autocorrect)


def parse(address: str) -> AddressComponents:
    """Public convenience function to parse a Japanese address into AddressComponents."""
    return get_engine().parse(address)


def validate(address: str, strict: bool = False, autocorrect: bool = False) -> ValidationResult:
    """Public convenience function to validate a Japanese address against statutory registries."""
    return get_engine().validate(address, strict=strict, autocorrect=autocorrect)
