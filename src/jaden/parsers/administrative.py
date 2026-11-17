"""JADEN: Administrative boundary resolver (Prefecture, Municipality, Ward).

Utilizes dual PrefixTries for O(L) resolution of JIS X 0401 prefectures
and JIS X 0402 / MIC municipalities. Supports deterministic statutory matching (Tier 1),
heuristic omitted-prefecture inference (Tier 3), and multi-jurisdiction ambiguity detection.
"""

import dataclasses
import re
from dataclasses import dataclass
from typing import Optional, Tuple, List, Dict
from ..core.townkey import fold_same_length, one_edit_apart
from ..core.trie import PrefixTrie
from ..data.loader import AddressDataRegistry, get_registry, MunicipalityRecord
from ..models.codes import PrefectureRecord


@dataclass(frozen=True, slots=True)
class AdministrativeParseResult:
    """Strongly typed result of administrative prefix resolution."""
    prefecture: Optional[PrefectureRecord]
    municipality: Optional[MunicipalityRecord]
    remaining_text: str
    is_prefecture_inferred: bool
    is_ambiguous: bool = False
    ambiguous_candidates: Tuple[str, ...] = ()
    matched_raw_name: Optional[str] = None
    is_contradictory: bool = False
    candidate_records: Tuple[MunicipalityRecord, ...] = ()

    def __iter__(self):
        """Allows backward-compatible 4-tuple unpacking:
        pref, muni, rem, is_inferred = parser.parse(text)
        """
        return iter((self.prefecture, self.municipality, self.remaining_text, self.is_prefecture_inferred))


class AdministrativeParser:
    """Parses prefecture and municipality components using high-speed PrefixTries."""

    def __init__(self, registry: Optional[AddressDataRegistry] = None) -> None:
        self.registry = registry or get_registry()
        self._pref_trie: PrefixTrie[PrefectureRecord] = PrefixTrie()
        self._muni_trie: PrefixTrie[List[MunicipalityRecord]] = PrefixTrie()
        self._ward_trie_by_pref: Dict[str, PrefixTrie[List[MunicipalityRecord]]] = {}
        self._ward_trie_global: PrefixTrie[List[MunicipalityRecord]] = PrefixTrie()
        self._initialized: bool = False
        self._build_tries()

    def _build_tries(self) -> None:
        if self._initialized:
            return

        # Keys are folded (ヶ/ケ/が, の/ノ, old kanji forms) and so is the text they are matched against:
        # '茅ケ崎市', '保土ヶ谷区', '須惠町' and '塩釜市' find 茅ヶ崎市, 保土ケ谷区, 須恵町 and 塩竈市.
        fold = fold_same_length

        # 1. Populate Prefecture Trie with both full names ('東京都') and stems ('東京')
        for pref in self.registry.list_all_prefectures():
            self._pref_trie.insert(pref.name, pref)
            if len(pref.stem) >= 2:
                self._pref_trie.insert(pref.stem, pref)
            self._ward_trie_by_pref[pref.code] = PrefixTrie()

        # 2. Populate Municipality Trie & Ward Tries
        for code, muni in self.registry._municipalities_by_code.items():
            # Full name: e.g. '京都市中京区', '横浜市中区', '千代田区', '八王子市'
            existing = self._muni_trie.search_exact(fold(muni.name)) or []
            if muni not in existing:
                existing.append(muni)
            self._muni_trie.insert(fold(muni.name), existing)

            # County-prefixed town/village name: e.g. '西多摩郡日の出町', '中郡大磯町', '石狩郡当別町'
            if muni.county:
                county_full = fold(f"{muni.county}{muni.name}")
                existing_cf = self._muni_trie.search_exact(county_full) or []
                if muni not in existing_cf:
                    existing_cf.append(muni)
                self._muni_trie.insert(county_full, existing_cf)

            # Designated city base name: e.g. '京都市', '横浜市'
            if muni.entity_type == "designated_city":
                existing_city = self._muni_trie.search_exact(fold(muni.city)) or []
                if muni not in existing_city:
                    existing_city.append(muni)
                self._muni_trie.insert(fold(muni.city), existing_city)

            # Bare administrative ward name: e.g. '中央区' in '札幌市中央区'
            if muni.ward and muni.ward != muni.name:
                existing_w = self._muni_trie.search_exact(fold(muni.ward)) or []
                if muni not in existing_w:
                    existing_w.append(muni)
                self._muni_trie.insert(fold(muni.ward), existing_w)

            # If it has an administrative ward: e.g. '中京区' in Kyoto, '南区' in Yokohama / Sagamihara
            if muni.ward:
                pref_code = muni.prefecture_code
                if pref_code in self._ward_trie_by_pref:
                    existing_pref_w = self._ward_trie_by_pref[pref_code].search_exact(fold(muni.ward)) or []
                    if muni not in existing_pref_w:
                        existing_pref_w.append(muni)
                    self._ward_trie_by_pref[pref_code].insert(fold(muni.ward), existing_pref_w)

                # Global ward list for heuristic resolution
                existing_ward = self._ward_trie_global.search_exact(fold(muni.ward)) or []
                if muni not in existing_ward:
                    existing_ward.append(muni)
                self._ward_trie_global.insert(fold(muni.ward), existing_ward)

            # Also index Tokyo's special wards in global ward trie for ward-level resolution
            if muni.entity_type == "special_ward":
                existing_ward = self._ward_trie_global.search_exact(fold(muni.name)) or []
                if muni not in existing_ward:
                    existing_ward.append(muni)
                self._ward_trie_global.insert(fold(muni.name), existing_ward)

        # The registry notation of two Izu island municipalities carries the island name
        for alias, name in (("八丈島八丈町", "八丈町"), ("三宅島三宅村", "三宅村")):
            records = [m for m in self._muni_trie.search_exact(fold(name)) or [] if m.prefecture_code == "13"]
            if records:
                self._muni_trie.insert(fold(alias), records)

        self._initialized = True

    def parse(self, text: str) -> AdministrativeParseResult:
        """Resolves the administrative hierarchy from the front of the address text.

        The text is matched in folded form, so spelling variants of a municipality name are found;
        ``remaining_text`` is cut from the text as written. When nothing is found, a repeated
        prefecture or municipality name and a misspelt or spaced county name are repaired and the
        text is read again.

        Returns:
            AdministrativeParseResult (supports 4-tuple unpacking for backward compatibility).
        """
        text = text.strip()
        if not text:
            return AdministrativeParseResult(None, None, "", False)
        res = self._parse_folded(fold_same_length(text), text)
        if res.municipality is None and not res.is_ambiguous:
            repaired = self._repair(text)
            if repaired is not None:
                again = self._parse_folded(fold_same_length(repaired), repaired)
                if again.municipality is not None or again.is_ambiguous:
                    res, text = again, repaired
        if res.municipality is not None:
            res = self._skip_repeated_name(res)
        # The remainder is always a suffix of the folded text, which has the length of the written one
        rest = text[len(text) - len(res.remaining_text):] if res.remaining_text else ""
        return dataclasses.replace(res, remaining_text=rest)

    def _skip_repeated_name(self, res: AdministrativeParseResult) -> AdministrativeParseResult:
        """'札幌市札幌市南区石山…', '龍ヶ崎市龍ケ崎市貝原塚町…': the name typed twice is read once."""
        muni = res.municipality
        rest = res.remaining_text
        if muni is None or not rest:
            return res
        names = [muni.prefecture_name + muni.name, muni.name]
        if muni.city and muni.city != muni.name:
            names += [muni.prefecture_name + muni.city, muni.city]
        if muni.ward and muni.ward != muni.name and len(muni.ward) >= 2:
            names.append(muni.ward)                      # '京都市下京区下京区西七条…'
        for name in names:
            folded = fold_same_length(name)
            if rest.startswith(folded) and len(rest) > len(folded):
                rest = rest[len(folded):].lstrip()
                if name == muni.ward:
                    return dataclasses.replace(res, remaining_text=rest)
                if muni.city and muni.city != muni.name and not muni.ward:
                    break
                # After a repeated city name the ward may follow ('横浜市横浜市金沢区…')
                ward_trie = self._ward_trie_by_pref.get(muni.prefecture_code)
                if muni.entity_type == "designated_city" and ward_trie is not None:
                    hit = ward_trie.longest_prefix(rest, 0)
                    wards = [w for w in hit[1] if w.city == muni.city] if hit else []
                    if hit and wards:
                        return dataclasses.replace(res, municipality=wards[0], remaining_text=rest[hit[2]:].lstrip())
                return dataclasses.replace(res, remaining_text=rest)
        return res

    _COUNTY = re.compile(r"^([^\s\d]{1,4})([郡群])\s*")

    def _repair(self, text: str) -> Optional[str]:
        """The text with a repeated prefecture name removed, or its county name corrected; None when
        there is nothing to repair. Only the administrative head is touched."""
        folded = fold_same_length(text)
        pref_hit = self._pref_trie.longest_prefix(folded, 0)
        if pref_hit is None:
            fixed = self._repair_prefecture(text, folded)
            if fixed is not None:
                return fixed
        head_end = 0
        pref = None
        if pref_hit and pref_hit[0] == pref_hit[1].name:
            pref = pref_hit[1]
            head_end = pref_hit[2]
            while folded[head_end:].lstrip().startswith(pref.name):   # '三重県三重県津市…'
                head_end += len(folded[head_end:]) - len(folded[head_end:].lstrip()) + len(pref.name)
            if head_end != pref_hit[2]:
                return pref.name + text[head_end:]
        body = folded[head_end:]
        offset = head_end + len(body) - len(body.lstrip())
        body = body.lstrip()
        m = self._COUNTY.match(body)
        if not m:
            return None
        # '粕屋郡須恵町' (糟屋郡), '河西群芽室町' (河西郡), '西牟婁郡　白浜町': the town decides, the county must be close
        after = body[m.end():]
        hit = self._muni_trie.longest_prefix(after, 0)
        if not hit:
            return None
        written = m.group(1) + "郡"
        for cand in hit[1]:
            if not cand.county or (pref is not None and cand.prefecture_code != pref.code):
                continue
            county = fold_same_length(cand.county)
            if county == written or one_edit_apart(county, written):
                return text[:offset] + cand.county + text[offset + m.end():]
        return None

    def _repair_prefecture(self, text: str, folded: str) -> Optional[str]:
        """'大坂府堺市…' (one character off), 'ｼ静岡県浜松市…', '福福島県…', 'な名古屋市…' (stray or doubled
        characters in front): the text with the registered name, or None."""
        for start in (1, 2):
            if len(folded) <= start:
                continue
            stray = not any("一" <= ch <= "鿿" for ch in folded[:start])
            doubled = start == 1 and folded[0] == folded[1]          # '福福島県…'
            if not (stray or doubled):
                continue
            hit = self._pref_trie.longest_prefix(folded, start)
            if hit and hit[0] == hit[1].name:
                return text[start:]
            muni = self._muni_trie.longest_prefix(folded, start)
            if stray and muni and len(muni[0]) >= 3:                  # 'な名古屋市北区…'
                return text[start:]
        for end in (3, 4):
            written = folded[:end]
            if len(folded) <= end or written[-1] not in "都道府県":
                continue
            fits = [p for p in self.registry.list_all_prefectures()
                    if len(p.name) == end and one_edit_apart(p.name, written)]
            if len(fits) != 1:
                continue
            after = self._muni_trie.longest_prefix(folded, end)
            if after and any(m.prefecture_code == fits[0].code for m in after[1]):
                return fits[0].name + text[end:]
        return None

    def _parse_folded(self, text: str, written: str) -> AdministrativeParseResult:
        """``parse`` on text that is already folded and stripped; ``written`` is the same text unfolded."""

        def lookup(trie: PrefixTrie[List[MunicipalityRecord]], sub: str) -> Optional[Tuple[str, List[MunicipalityRecord], int]]:
            # Folding makes 鹿嶋市 (Ibaraki) and 鹿島市 (Saga) one key: the spelling as written decides
            hit = trie.longest_prefix(sub, 0)
            if hit and len(hit[1]) > 1:
                start = len(written) - len(sub)
                spelt = written[start:start + hit[2]]
                exact = [c for c in hit[1] if spelt in (c.name, c.city, c.ward, f"{c.county or ''}{c.name}")]
                if exact and len(exact) < len(hit[1]):
                    return hit[0], exact, hit[2]
            return hit

        # Pass 1: Try matching Prefecture from the front
        pref_match = self._pref_trie.longest_prefix(text, 0)
        if pref_match:
            matched_pref_str, pref_record, rem_idx = pref_match

            # Stem Hijacking Guard:
            # If we matched only the bare stem (e.g. '京都' from '京都府', '愛知' from '愛知県')
            # rather than the full statutory name ('京都府', '愛知県'), verify whether the input
            # actually starts with a longer municipality, county, or ward entity at index 0.
            # Examples: '京都市中京区...', '愛知郡愛荘町...', '福島町...', '福島区...', '長野原町...', '京都郡苅田町...'
            bypass_pref = False
            if matched_pref_str != pref_record.name:
                muni_at_0 = lookup(self._muni_trie, text)
                ward_at_0 = lookup(self._ward_trie_global, text)
                len_muni = len(muni_at_0[0]) if muni_at_0 else 0
                len_ward = len(ward_at_0[0]) if ward_at_0 else 0
                if max(len_muni, len_ward) > len(matched_pref_str):
                    bypass_pref = True

            if not bypass_pref:
                muni_text = text[rem_idx:].lstrip()

                # 1a. Try municipality match under this prefecture
                muni_match = lookup(self._muni_trie, muni_text)
                if muni_match:
                    matched_key, candidates, muni_end_idx = muni_match
                    # Filter candidates belonging to this specific prefecture
                    pref_candidates = [c for c in candidates if c.prefecture_code == pref_record.code]
                    if len(pref_candidates) > 1:
                        # Intra-prefecture duplicate ward ambiguity (e.g. '神奈川県南区', '大阪府北区')
                        post_muni = muni_text[muni_end_idx:].lstrip()
                        ambiguous_list = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in pref_candidates)
                        return AdministrativeParseResult(
                            pref_record, None, post_muni,
                            is_prefecture_inferred=False,
                            is_ambiguous=True,
                            ambiguous_candidates=ambiguous_list,
                            matched_raw_name=matched_key,
                            candidate_records=tuple(pref_candidates),
                        )
                    elif len(pref_candidates) == 1:
                        matched_muni = pref_candidates[0]
                        post_muni = muni_text[muni_end_idx:].lstrip()

                        # If matched a designated city base (e.g. '京都市', '大阪市', '横浜市'), check if ward follows ('中京区', '北区', '南区')
                        if matched_muni.entity_type == "designated_city" and pref_record.code in self._ward_trie_by_pref:
                            ward_match = lookup(self._ward_trie_by_pref[pref_record.code], post_muni)
                            if ward_match:
                                _, ward_cands, ward_end_idx = ward_match
                                # Filter ward candidates belonging to this specific designated city
                                matching_ward = [w for w in ward_cands if w.city == matched_muni.city]
                                if matching_ward:
                                    return AdministrativeParseResult(
                                        pref_record, matching_ward[0], post_muni[ward_end_idx:].lstrip(), False
                                    )

                        return AdministrativeParseResult(
                            pref_record, matched_muni, post_muni, False
                        )
                    else:
                        # Cross-prefecture contradiction: municipality matched does not belong to specified prefecture
                        return AdministrativeParseResult(
                            pref_record, None, muni_text,
                            is_prefecture_inferred=False,
                            is_ambiguous=False,
                            ambiguous_candidates=(),
                            matched_raw_name=matched_key,
                            is_contradictory=True,
                        )

                # 1b. Check if designated city was omitted and ward directly follows prefecture
                # e.g., '京都府中京区...' -> '京都市中京区'
                if pref_record.code in self._ward_trie_by_pref:
                    ward_match = lookup(self._ward_trie_by_pref[pref_record.code], muni_text)
                    if ward_match:
                        matched_ward_key, ward_cands, ward_end_idx = ward_match
                        if len(ward_cands) > 1:
                            post_ward = muni_text[ward_end_idx:].lstrip()
                            ambiguous_list = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in ward_cands)
                            return AdministrativeParseResult(
                                pref_record, None, post_ward,
                                is_prefecture_inferred=False,
                                is_ambiguous=True,
                                ambiguous_candidates=ambiguous_list,
                                matched_raw_name=matched_ward_key,
                                candidate_records=tuple(ward_cands),
                            )
                        elif len(ward_cands) == 1:
                            return AdministrativeParseResult(
                                pref_record, ward_cands[0], muni_text[ward_end_idx:].lstrip(), False
                            )

                # Check global ward match for cross-prefecture contradiction (e.g. '東京都博多区')
                ward_match_global = lookup(self._ward_trie_global, muni_text)
                if ward_match_global:
                    matched_ward_key, global_ward_cands, _ = ward_match_global
                    if not any(c.prefecture_code == pref_record.code for c in global_ward_cands):
                        return AdministrativeParseResult(
                            pref_record, None, muni_text,
                            is_prefecture_inferred=False,
                            is_ambiguous=False,
                            ambiguous_candidates=(),
                            matched_raw_name=matched_ward_key,
                            is_contradictory=True,
                        )

                # If no municipality matched from trie, return prefecture and remainder
                return AdministrativeParseResult(pref_record, None, muni_text, False)

        # Pass 2: Prefecture omitted in user input -> Ambiguity-aware resolution (Tier 3)
        # Try matching Municipality directly from index 0
        muni_match = lookup(self._muni_trie, text)
        if muni_match:
            matched_key, candidates, rem_idx = muni_match
            rem_text = text[rem_idx:].lstrip()

            # Case 2a: Unambiguous municipality across Japan (e.g. '八王子市', '京都市', '新宿区')
            if len(candidates) == 1:
                muni_record = candidates[0]
                inferred_pref = self.registry.get_prefecture_by_code(muni_record.prefecture_code)

                # If matched designated city base ('京都市'), check if ward follows ('中京区')
                if muni_record.entity_type == "designated_city" and inferred_pref and inferred_pref.code in self._ward_trie_by_pref:
                    ward_match = lookup(self._ward_trie_by_pref[inferred_pref.code], rem_text)
                    if ward_match:
                        _, ward_cands, ward_end_idx = ward_match
                        matching_ward = [w for w in ward_cands if w.city == muni_record.city]
                        if matching_ward:
                            return AdministrativeParseResult(
                                inferred_pref, matching_ward[0], rem_text[ward_end_idx:].lstrip(),
                                is_prefecture_inferred=True, is_ambiguous=False
                            )

                return AdministrativeParseResult(
                    inferred_pref, muni_record, rem_text,
                    is_prefecture_inferred=True, is_ambiguous=False
                )

            # Case 2b: Ambiguous municipality name existing across multiple records or prefectures
            # (e.g. '府中市' in Tokyo & Hiroshima, '伊達市' in Hokkaido & Fukushima, '泊村' in Hokkaido, '中央区' across 11 prefectures)
            ambiguous_list = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in candidates)
            return AdministrativeParseResult(
                None, None, rem_text,
                is_prefecture_inferred=True,
                is_ambiguous=True,
                ambiguous_candidates=ambiguous_list,
                matched_raw_name=matched_key,
                candidate_records=tuple(candidates),
            )

        # Pass 2b: Omitted prefecture + designated city, starting directly with a ward
        # e.g., '中京区寺町通...' (unambiguous) vs '中央区銀座...' (ambiguous across 11 cities/prefectures)
        ward_match_global = lookup(self._ward_trie_global, text)
        if ward_match_global:
            matched_ward_name, ward_candidates, rem_idx = ward_match_global
            rem_text = text[rem_idx:].lstrip()

            # Unambiguous ward across Japan
            if len(ward_candidates) == 1:
                muni_record = ward_candidates[0]
                inferred_pref = self.registry.get_prefecture_by_code(muni_record.prefecture_code)
                return AdministrativeParseResult(
                    inferred_pref, muni_record, rem_text,
                    is_prefecture_inferred=True, is_ambiguous=False
                )

            # Ambiguous ward across Japan
            ambiguous_list = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in ward_candidates)
            return AdministrativeParseResult(
                None, None, rem_text,
                is_prefecture_inferred=True,
                is_ambiguous=True,
                ambiguous_candidates=ambiguous_list,
                matched_raw_name=matched_ward_name,
                candidate_records=tuple(ward_candidates),
            )

        # Pass 3: No administrative prefix recognized
        return AdministrativeParseResult(None, None, text, False, False, (), None)
