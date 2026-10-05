"""Tests for validation criteria and taxonomy tier integrity (Finding B-2).

Verifies:
1. ACCEPTED status requires resolved local government code (lg_code is not None).
2. Diagnostic message for ACCEPTED does not use the word 'boundaries'.
3. Landmarks, POIs, and bare prefectures without resolved municipalities get UNSUPPORTED.
4. Cross-prefecture contradictions get MALFORMED.
5. Taxonomy tier classifications: statutory registry items are Tier 1, conventional addressing
   formats are Tier 2, and heuristic textual extractions are Tier 3.
"""

import pytest
from jaden import normalize, validate, ValidationStatus, TaxonomyTier


def test_validate_accepted_requires_resolved_lg_code():
    """Addresses with resolved statutory lg_code are ACCEPTED."""
    val = validate("東京都港区六本木1-2-3")
    assert val.status == ValidationStatus.ACCEPTED.value
    assert val.valid is True
    assert val.lg_code == "131032"
    assert "boundaries" not in val.message.lower()
    assert val.message == "Local government entity verified against official statutory registry."

    val_county = validate("神奈川県中郡大磯町国府本郷547")
    assert val_county.status == ValidationStatus.ACCEPTED.value
    assert val_county.valid is True
    assert val_county.lg_code == "143413"


def test_validate_unsupported_landmarks_and_pois():
    """Landmarks and proper nouns starting with prefecture stems/names are UNSUPPORTED."""
    landmarks = [
        "東京タワー",
        "京都タワー",
        "大阪城公園",
        "広島カープ",
        "静岡ガス",
    ]
    for lm in landmarks:
        val = validate(lm)
        assert val.status == ValidationStatus.UNSUPPORTED.value
        assert val.valid is False
        assert val.lg_code is None
        assert "Administrative entity could not be resolved to a local government code." in val.message


def test_validate_unsupported_bare_prefecture_and_gibberish():
    """Bare prefecture names or unresolvable municipal tails are UNSUPPORTED."""
    val_bare = validate("東京都")
    assert val_bare.status == ValidationStatus.UNSUPPORTED.value
    assert val_bare.valid is False

    val_gibberish = validate("東京都あいうえおかきくけこ1-2-3")
    assert val_gibberish.status == ValidationStatus.UNSUPPORTED.value
    assert val_gibberish.valid is False


def test_validate_malformed_cross_prefecture_contradictions():
    """Direct contradictions between prefecture and municipality are MALFORMED."""
    contradictions = [
        "東京都大阪市北区梅田1-1",
        "東京都博多区1-1",
    ]
    for c in contradictions:
        val = validate(c)
        assert val.status == ValidationStatus.MALFORMED.value
        assert val.valid is False
        assert "Contradiction detected" in val.message


def test_taxonomy_tier_integrity():
    """Components verified against statutory MIC registry are Tier 1; block numbers are Tier 2; heuristic town is Tier 3."""
    res = normalize("東京都港区六本木1-2-3")
    assert res.tier_map["prefecture"] == TaxonomyTier.TIER_1_STATUTORY.value
    assert res.tier_map["municipality"] == TaxonomyTier.TIER_1_STATUTORY.value
    assert res.tier_map["lg_code"] == TaxonomyTier.TIER_1_STATUTORY.value
    assert res.tier_map["town"] == TaxonomyTier.TIER_3_HEURISTIC.value
    assert res.tier_map["ban"] == TaxonomyTier.TIER_2_CONVENTIONAL.value
    assert res.tier_map["go"] == TaxonomyTier.TIER_2_CONVENTIONAL.value


def test_county_tier_integrity():
    """Counties in statutory registry are classified as Tier 1."""
    res = normalize("神奈川県中郡大磯町国府本郷547")
    assert res.tier_map["county"] == TaxonomyTier.TIER_1_STATUTORY.value
    assert res.tier_map["town"] == TaxonomyTier.TIER_3_HEURISTIC.value
    assert res.tier_map["ban"] == TaxonomyTier.TIER_2_CONVENTIONAL.value

    res_banchi = normalize("神奈川県中郡大磯町国府本郷547番地")
    assert res_banchi.tier_map["banchi"] == TaxonomyTier.TIER_2_CONVENTIONAL.value
