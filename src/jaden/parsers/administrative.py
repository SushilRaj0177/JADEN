"""JADEN: Administrative boundary resolver (Prefecture, Municipality, Ward).

Utilizes dual PrefixTries for O(L) resolution of JIS X 0401 prefectures
and JIS X 0402 / MIC municipalities. Supports deterministic statutory matching (Tier 1),
heuristic omitted-prefecture inference (Tier 3), and multi-jurisdiction ambiguity detection.
"""

from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Dict, Final
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

        # 1. Populate Prefecture Trie with both full names ('東京都') and stems ('東京')
        for pref in self.registry.list_all_prefectures():
            self._pref_trie.insert(pref.name, pref)
            if len(pref.stem) >= 2:
                self._pref_trie.insert(pref.stem, pref)
            self._ward_trie_by_pref[pref.code] = PrefixTrie()

        # 2. Populate Municipality Trie & Ward Tries
        for code, muni in self.registry._municipalities_by_code.items():
            # Full name: e.g. '京都市中京区', '横浜市中区', '千代田区', '八王子市'
            existing = self._muni_trie.search_exact(muni.name) or []
            if muni not in existing:
                existing.append(muni)
            self._muni_trie.insert(muni.name, existing)

            # County-prefixed town/village name: e.g. '西多摩郡日の出町', '中郡大磯町', '石狩郡当別町'
            if muni.county:
                county_full = f"{muni.county}{muni.name}"
                existing_cf = self._muni_trie.search_exact(county_full) or []
                if muni not in existing_cf:
                    existing_cf.append(muni)
                self._muni_trie.insert(county_full, existing_cf)

            # Designated city base name: e.g. '京都市', '横浜市'
            if muni.entity_type == "designated_city":
                existing_city = self._muni_trie.search_exact(muni.city) or []
                if muni not in existing_city:
                    existing_city.append(muni)
                self._muni_trie.insert(muni.city, existing_city)

            # Bare administrative ward name: e.g. '中央区' in '札幌市中央区'
            if muni.ward and muni.ward != muni.name:
                existing_w = self._muni_trie.search_exact(muni.ward) or []
                if muni not in existing_w:
                    existing_w.append(muni)
                self._muni_trie.insert(muni.ward, existing_w)

            # If it has an administrative ward: e.g. '中京区' in Kyoto, '南区' in Yokohama / Sagamihara
            if muni.ward:
                pref_code = muni.prefecture_code
                if pref_code in self._ward_trie_by_pref:
                    existing_pref_w = self._ward_trie_by_pref[pref_code].search_exact(muni.ward) or []
                    if muni not in existing_pref_w:
                        existing_pref_w.append(muni)
                    self._ward_trie_by_pref[pref_code].insert(muni.ward, existing_pref_w)

                # Global ward list for heuristic resolution
                existing_ward = self._ward_trie_global.search_exact(muni.ward) or []
                if muni not in existing_ward:
                    existing_ward.append(muni)
                self._ward_trie_global.insert(muni.ward, existing_ward)

            # Also index Tokyo's special wards in global ward trie for ward-level resolution
            if muni.entity_type == "special_ward":
                existing_ward = self._ward_trie_global.search_exact(muni.name) or []
                if muni not in existing_ward:
                    existing_ward.append(muni)
                self._ward_trie_global.insert(muni.name, existing_ward)

        self._initialized = True

    def parse(self, text: str) -> AdministrativeParseResult:
        """Resolves the administrative hierarchy from the front of the address text.

        Returns:
            AdministrativeParseResult (supports 4-tuple unpacking for backward compatibility).
        """
        text = text.strip()
        if not text:
            return AdministrativeParseResult(None, None, "", False)

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
                muni_at_0 = self._muni_trie.longest_prefix(text, 0)
                ward_at_0 = self._ward_trie_global.longest_prefix(text, 0)
                len_muni = len(muni_at_0[0]) if muni_at_0 else 0
                len_ward = len(ward_at_0[0]) if ward_at_0 else 0
                if max(len_muni, len_ward) > len(matched_pref_str):
                    bypass_pref = True

            if not bypass_pref:
                muni_text = text[rem_idx:].lstrip()

                # 1a. Try municipality match under this prefecture
                muni_match = self._muni_trie.longest_prefix(muni_text, 0)
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
                        )
                    elif len(pref_candidates) == 1:
                        matched_muni = pref_candidates[0]
                        post_muni = muni_text[muni_end_idx:].lstrip()

                        # If matched a designated city base (e.g. '京都市', '大阪市', '横浜市'), check if ward follows ('中京区', '北区', '南区')
                        if matched_muni.entity_type == "designated_city" and pref_record.code in self._ward_trie_by_pref:
                            ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(post_muni, 0)
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
                    ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(muni_text, 0)
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
                            )
                        elif len(ward_cands) == 1:
                            return AdministrativeParseResult(
                                pref_record, ward_cands[0], muni_text[ward_end_idx:].lstrip(), False
                            )

                # Check global ward match for cross-prefecture contradiction (e.g. '東京都博多区')
                ward_match_global = self._ward_trie_global.longest_prefix(muni_text, 0)
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
        muni_match = self._muni_trie.longest_prefix(text, 0)
        if muni_match:
            matched_key, candidates, rem_idx = muni_match
            rem_text = text[rem_idx:].lstrip()

            # Case 2a: Unambiguous municipality across Japan (e.g. '八王子市', '京都市', '新宿区')
            if len(candidates) == 1:
                muni_record = candidates[0]
                pref_record = self.registry.get_prefecture_by_code(muni_record.prefecture_code)

                # If matched designated city base ('京都市'), check if ward follows ('中京区')
                if muni_record.entity_type == "designated_city" and pref_record and pref_record.code in self._ward_trie_by_pref:
                    ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(rem_text, 0)
                    if ward_match:
                        _, ward_cands, ward_end_idx = ward_match
                        matching_ward = [w for w in ward_cands if w.city == muni_record.city]
                        if matching_ward:
                            return AdministrativeParseResult(
                                pref_record, matching_ward[0], rem_text[ward_end_idx:].lstrip(),
                                is_prefecture_inferred=True, is_ambiguous=False
                            )

                return AdministrativeParseResult(
                    pref_record, muni_record, rem_text,
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
                matched_raw_name=matched_key
            )

        # Pass 2b: Omitted prefecture + designated city, starting directly with a ward
        # e.g., '中京区寺町通...' (unambiguous) vs '中央区銀座...' (ambiguous across 11 cities/prefectures)
        ward_match_global = self._ward_trie_global.longest_prefix(text, 0)
        if ward_match_global:
            matched_ward_name, ward_candidates, rem_idx = ward_match_global
            rem_text = text[rem_idx:].lstrip()

            # Unambiguous ward across Japan
            if len(ward_candidates) == 1:
                muni_record = ward_candidates[0]
                pref_record = self.registry.get_prefecture_by_code(muni_record.prefecture_code)
                return AdministrativeParseResult(
                    pref_record, muni_record, rem_text,
                    is_prefecture_inferred=True, is_ambiguous=False
                )

            # Ambiguous ward across Japan
            ambiguous_list = tuple(f"{c.prefecture_name}{c.name} ({c.lg_code})" for c in ward_candidates)
            return AdministrativeParseResult(
                None, None, rem_text,
                is_prefecture_inferred=True,
                is_ambiguous=True,
                ambiguous_candidates=ambiguous_list,
                matched_raw_name=matched_ward_name
            )

        # Pass 3: No administrative prefix recognized
        return AdministrativeParseResult(None, None, text, False, False, (), None)
