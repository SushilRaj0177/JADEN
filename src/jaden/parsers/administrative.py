"""JADEN: Administrative boundary resolver (Prefecture, Municipality, Ward).

Utilizes dual PrefixTries for O(L) resolution of JIS X 0401 prefectures
and JIS X 0402 / MIC municipalities. Supports deterministic matching (Tier 1)
and heuristic omitted-prefecture inference (Tier 3).
"""

from typing import Optional, Tuple, List
from ..core.trie import PrefixTrie
from ..data.loader import AddressDataRegistry, get_registry, MunicipalityRecord
from ..models.codes import PrefectureRecord


class AdministrativeParser:
    """Parses prefecture and municipality components using high-speed PrefixTries."""

    def __init__(self, registry: Optional[AddressDataRegistry] = None) -> None:
        self.registry = registry or get_registry()
        self._pref_trie: PrefixTrie[PrefectureRecord] = PrefixTrie()
        self._muni_trie: PrefixTrie[MunicipalityRecord] = PrefixTrie()
        self._ward_trie_by_pref: Dict[str, PrefixTrie[MunicipalityRecord]] = {}
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
            self._muni_trie.insert(muni.name, muni)

            # Designated city base name: e.g. '京都市', '横浜市'
            if muni.entity_type == "designated_city":
                self._muni_trie.insert(muni.city, muni)

            # If it has an administrative ward: e.g. '中京区' in Kyoto
            if muni.ward:
                pref_code = muni.prefecture_code
                if pref_code in self._ward_trie_by_pref:
                    self._ward_trie_by_pref[pref_code].insert(muni.ward, muni)

                # Global ward list for heuristic resolution
                existing = self._ward_trie_global.search_exact(muni.ward) or []
                existing.append(muni)
                self._ward_trie_global.insert(muni.ward, existing)

        self._initialized = True

    def parse(self, text: str) -> Tuple[
        Optional[PrefectureRecord],
        Optional[MunicipalityRecord],
        str,
        bool  # is_prefecture_inferred (Tier 3)
    ]:
        """Resolves the administrative hierarchy from the front of the address text.

        Returns:
            (prefecture_record, municipality_record, remaining_text, is_prefecture_inferred)
        """
        text = text.strip()
        if not text:
            return None, None, "", False

        pref_record: Optional[PrefectureRecord] = None
        muni_record: Optional[MunicipalityRecord] = None
        is_inferred: bool = False
        rem_idx = 0

        # Pass 1: Try matching Prefecture from the front
        pref_match = self._pref_trie.longest_prefix(text, 0)
        if pref_match:
            _, pref_record, rem_idx = pref_match
            muni_text = text[rem_idx:].lstrip()

            # 1a. Try full municipality match
            muni_match = self._muni_trie.longest_prefix(muni_text, 0)
            if muni_match:
                _, matched_muni, muni_end_idx = muni_match
                if matched_muni.prefecture_code == pref_record.code:
                    muni_record = matched_muni
                    post_muni = muni_text[muni_end_idx:].lstrip()

                    # If matched a designated city base (e.g. '京都市'), check if ward follows ('中京区')
                    if matched_muni.entity_type == "designated_city" and pref_record.code in self._ward_trie_by_pref:
                        ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(post_muni, 0)
                        if ward_match:
                            _, specific_ward_muni, ward_end_idx = ward_match
                            return pref_record, specific_ward_muni, post_muni[ward_end_idx:].lstrip(), False

                    return pref_record, muni_record, post_muni, False

            # 1b. Check if designated city was omitted and ward directly follows prefecture
            # e.g., '京都府中京区...' -> '京都市中京区'
            if pref_record.code in self._ward_trie_by_pref:
                ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(muni_text, 0)
                if ward_match:
                    _, specific_ward_muni, ward_end_idx = ward_match
                    return pref_record, specific_ward_muni, muni_text[ward_end_idx:].lstrip(), False

            # If no municipality matched from trie, return prefecture and remainder
            return pref_record, None, muni_text, False

        # Pass 2: Prefecture omitted in user input -> Heuristic inference (Tier 3)
        # Try matching Municipality directly from index 0
        muni_match = self._muni_trie.longest_prefix(text, 0)
        if muni_match:
            _, muni_record, rem_idx = muni_match
            pref_record = self.registry.get_prefecture_by_code(muni_record.prefecture_code)
            is_inferred = True
            rem_text = text[rem_idx:].lstrip()

            # If matched designated city base ('京都市'), check if ward follows ('中京区')
            if muni_record.entity_type == "designated_city" and pref_record and pref_record.code in self._ward_trie_by_pref:
                ward_match = self._ward_trie_by_pref[pref_record.code].longest_prefix(rem_text, 0)
                if ward_match:
                    _, specific_ward_muni, ward_end_idx = ward_match
                    return pref_record, specific_ward_muni, rem_text[ward_end_idx:].lstrip(), is_inferred

            return pref_record, muni_record, rem_text, is_inferred

        # Pass 2b: Omitted prefecture + designated city, starting directly with an administrative ward
        # e.g., '中京区寺町通...' (unique ward)
        ward_match_global = self._ward_trie_global.longest_prefix(text, 0)
        if ward_match_global:
            _, ward_list, rem_idx = ward_match_global
            # If the ward name is unambiguous across Japan (e.g. 中京区, 上京区, 下京区)
            if len(ward_list) == 1:
                muni_record = ward_list[0]
                pref_record = self.registry.get_prefecture_by_code(muni_record.prefecture_code)
                is_inferred = True
                return pref_record, muni_record, text[rem_idx:].lstrip(), is_inferred

        # Pass 3: No administrative prefix recognized
        return None, None, text, False
