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

import time
from typing import Optional, Dict

from .models.codes import TaxonomyTier, AddressRegime
from .models.address import AddressComponents, NormalizedAddress
from .models.validation import ValidationResult, ValidationStatus
from .core.sanitizer import sanitize_address_text
from .core.kanji_numerals import normalize_kanji_numerals_in_blocks
from .parsers.administrative import AdministrativeParser
from .parsers.kyoto import KyotoParser
from .parsers.hokkaido import HokkaidoParser
from .parsers.fsm import BlockFSM
from .parsers.building import BuildingParser


class AddressNormalizer:
    """Production-grade Japanese address normalization engine."""

    def __init__(self) -> None:
        self.admin_parser = AdministrativeParser()

    def normalize(self, raw_address: str) -> NormalizedAddress:
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
        sanitized = sanitize_address_text(raw_address)

        # Stage 2: Context-bounded Kanji numeral conversion
        working_text = normalize_kanji_numerals_in_blocks(sanitized)

        tier_map: Dict[str, str] = {}
        confidence = 1.0

        # Stage 3: Administrative Boundary Resolution
        admin_res = self.admin_parser.parse(working_text)
        pref_rec = admin_res.prefecture
        muni_rec = admin_res.municipality
        post_admin_text = admin_res.remaining_text
        is_pref_inferred = admin_res.is_prefecture_inferred
        is_ambiguous = admin_res.is_ambiguous
        ambiguous_candidates = admin_res.ambiguous_candidates
        matched_raw_name = admin_res.matched_raw_name
        is_contradictory = admin_res.is_contradictory

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
                    tier_map["prefecture"] = TaxonomyTier.TIER_2_CONVENTIONAL.value

        # 4b. Hokkaido Jo-Chome Grid Parser
        is_hokkaido_candidate = (
            (pref_rec and pref_rec.code == "01")
            or ("条" in text_after_conventions and "丁目" in text_after_conventions and any(d in text_after_conventions for d in ["北", "南"]))
        )
        if is_hokkaido_candidate:
            hokkaido_clause, text_after_conventions = HokkaidoParser.parse(text_after_conventions)
            if hokkaido_clause:
                tier_map["hokkaido_grid"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                if not pref_name:
                    pref_name = "北海道"
                    pref_code = "01"
                    is_pref_inferred = True
                    tier_map["prefecture"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
                if is_ambiguous and matched_raw_name == "中央区":
                    # Sapporo is the only city in Japan with Jo-Chome cardinal grid + 中央区
                    city_name = "札幌市"
                    ward_name = "中央区"
                    lg_code = "011011"
                    is_ambiguous = False
                    ambiguous_candidates = ()

        # Validation Guard: Reject inputs with zero verified Japanese administrative or conventional entities
        if pref_name is None and city_name is None and not is_ambiguous and kyoto_clause is None and hokkaido_clause is None:
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

        # Stage 5: Chome-Ban-Go / Banchi-Edaban Block FSM
        has_chome_from_hokkaido = (hokkaido_clause is not None and hokkaido_clause.chome is not None)
        block_dict, town_name, tail_text = BlockFSM.parse(
            text_after_conventions,
            has_chome_already=has_chome_from_hokkaido
        )

        chome_val = block_dict["chome"] or (hokkaido_clause.chome if hokkaido_clause else None)
        ban_val = block_dict["ban"]
        go_val = block_dict["go"]
        banchi_val = block_dict["banchi"]
        edaban_val = block_dict["edaban"]
        oaza_val = block_dict["oaza"]
        koaza_val = block_dict["koaza"]
        regime_val = block_dict["address_regime"]

        # Kyoto conventional navigation addresses strictly use cadastral lot numbers (地番)
        if kyoto_clause and (ban_val is not None and banchi_val is None):
            banchi_val = ban_val
            edaban_val = go_val
            ban_val = None
            go_val = None
            regime_val = AddressRegime.CHIBAN.value

        if county_name:
            tier_map["county"] = TaxonomyTier.TIER_1_STATUTORY.value
        if town_name:
            tier_map["town"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if oaza_val:
            tier_map["oaza"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if koaza_val:
            tier_map["koaza"] = TaxonomyTier.TIER_3_HEURISTIC.value
        if chome_val is not None:
            tier_map["chome"] = TaxonomyTier.TIER_2_CONVENTIONAL.value
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

        if hokkaido_clause:
            canonical_parts.append(f"{hokkaido_clause.cardinal_ns}{hokkaido_clause.jo}条{hokkaido_clause.cardinal_ew}{hokkaido_clause.chome}丁目")
        elif town_name:
            canonical_parts.append(town_name)

        # Block / Lot string formatting
        if chome_val is not None and not hokkaido_clause:
            canonical_parts.append(f"{chome_val}丁目")

        if ban_val is not None and go_val is not None:
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

        base_addr = "".join(canonical_parts)
        if secondary_parts:
            canonical_str = f"{base_addr} {' '.join(secondary_parts)}"
        else:
            canonical_str = base_addr

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
        )

        latency_us = (time.perf_counter_ns() - start_time_ns) / 1_000.0

        return NormalizedAddress(
            input_raw=raw_address,
            input_sanitized=sanitized,
            canonical=canonical_str,
            components=components,
            tier_map=tier_map,
            confidence_score=round(confidence, 2),
            latency_microseconds=round(latency_us, 2),
        )

    def parse(self, raw_address: str) -> AddressComponents:
        """Parses a Japanese address string into granular AddressComponents AST.

        Args:
            raw_address: Raw user-input address string.

        Returns:
            AddressComponents data object with decomposed administrative and block fields.
        """
        return self.normalize(raw_address).components

    def validate(self, raw_address: str) -> ValidationResult:
        """Validates an address string against statutory administrative registries.

        Evaluates:
        - ACCEPTED: Address recognized with valid municipal authority and high confidence.
        - AMBIGUOUS: Omitted prefecture matches multiple statutory municipalities.
        - MALFORMED: Rejected by administrative parser or confidence == 0.0.
        - UNSUPPORTED: Structurally unparsed or unresolvable tail components.

        Args:
            raw_address: Raw user-input address string.

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

        res = self.normalize(raw_address)

        if res.components.is_contradictory:
            return ValidationResult(
                raw_input=raw_address,
                status=ValidationStatus.MALFORMED.value,
                valid=False,
                confidence_score=0.0,
                address_regime=res.components.address_regime,
                lg_code=None,
                is_ambiguous=False,
                ambiguous_candidates=(),
                message="Contradiction detected: municipality does not belong to specified prefecture.",
            )

        if res.confidence_score == 0.0:
            return ValidationResult(
                raw_input=raw_address,
                status=ValidationStatus.MALFORMED.value,
                valid=False,
                confidence_score=0.0,
                address_regime=AddressRegime.UNSPECIFIED.value,
                lg_code=None,
                is_ambiguous=False,
                ambiguous_candidates=(),
                message="Input rejected: no recognized Japanese administrative jurisdiction or structure.",
            )

        if res.components.is_ambiguous:
            return ValidationResult(
                raw_input=raw_address,
                status=ValidationStatus.AMBIGUOUS.value,
                valid=False,
                confidence_score=res.confidence_score,
                address_regime=res.components.address_regime,
                lg_code=None,
                is_ambiguous=True,
                ambiguous_candidates=res.components.ambiguous_candidates,
                message=(
                    f"Ambiguous administrative jurisdiction matches {len(res.components.ambiguous_candidates)} candidates."
                    if res.components.prefecture
                    else f"Omitted prefecture matches {len(res.components.ambiguous_candidates)} statutory municipalities."
                ),
            )

        if res.components.unparsed_tail and len(res.components.unparsed_tail.strip()) > 5:
            return ValidationResult(
                raw_input=raw_address,
                status=ValidationStatus.UNSUPPORTED.value,
                valid=False,
                confidence_score=res.confidence_score,
                address_regime=res.components.address_regime,
                lg_code=res.components.lg_code,
                is_ambiguous=False,
                ambiguous_candidates=(),
                message=f"Input contains unparsed or unsupported tokens: '{res.components.unparsed_tail}'.",
            )

        if res.components.lg_code is not None and res.confidence_score >= 0.5 and not res.components.is_ambiguous:
            return ValidationResult(
                raw_input=raw_address,
                status=ValidationStatus.ACCEPTED.value,
                valid=True,
                confidence_score=res.confidence_score,
                address_regime=res.components.address_regime,
                lg_code=res.components.lg_code,
                is_ambiguous=False,
                ambiguous_candidates=(),
                message="Local government entity verified against official statutory registry.",
            )

        return ValidationResult(
            raw_input=raw_address,
            status=ValidationStatus.UNSUPPORTED.value,
            valid=False,
            confidence_score=res.confidence_score,
            address_regime=res.components.address_regime,
            lg_code=res.components.lg_code,
            is_ambiguous=False,
            ambiguous_candidates=(),
            message="Administrative entity could not be resolved to a local government code.",
        )


_DEFAULT_ENGINE: Optional[AddressNormalizer] = None


def normalize(address: str) -> NormalizedAddress:
    """Public convenience function to normalize a Japanese address."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AddressNormalizer()
    return _DEFAULT_ENGINE.normalize(address)


def parse(address: str) -> AddressComponents:
    """Public convenience function to parse a Japanese address into AddressComponents."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AddressNormalizer()
    return _DEFAULT_ENGINE.parse(address)


def validate(address: str) -> ValidationResult:
    """Public convenience function to validate a Japanese address against statutory registries."""
    global _DEFAULT_ENGINE
    if _DEFAULT_ENGINE is None:
        _DEFAULT_ENGINE = AddressNormalizer()
    return _DEFAULT_ENGINE.validate(address)
