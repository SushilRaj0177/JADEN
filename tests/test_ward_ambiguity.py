"""Tests for intra-prefecture duplicate ward ambiguity resolution (Finding B-3).

Verifies:
1. Intra-prefecture ward ambiguity detection (e.g. 南区/緑区 in Kanagawa, 北区/西区 in Osaka).
2. 'Prefecture known, city ambiguous' state representation in NormalizedAddress and AddressComponents.
3. ValidationStatus.AMBIGUOUS when intra-prefecture duplicate wards are unresolvable.
4. Deterministic unique resolution when the designated city is explicitly supplied.
"""

import pytest
from jaden import normalize, parse, validate, ValidationStatus


def test_intra_pref_ambiguity_kanagawa_minami_ku():
    """神奈川県南区1-1 is ambiguous between Yokohama and Sagamihara."""
    res = normalize("神奈川県南区1-1")
    comp = res.components
    assert comp.prefecture == "神奈川県"
    assert comp.prefecture_code == "14"
    assert comp.city is None
    assert comp.ward == "南区"
    assert comp.lg_code is None
    assert comp.is_ambiguous is True
    assert len(comp.ambiguous_candidates) == 2
    assert any("横浜市南区" in c for c in comp.ambiguous_candidates)
    assert any("相模原市南区" in c for c in comp.ambiguous_candidates)
    assert res.confidence_score == 0.50

    val = validate("神奈川県南区1-1")
    assert val.status == ValidationStatus.AMBIGUOUS.value
    assert val.valid is False
    assert val.lg_code is None
    assert "Ambiguous administrative jurisdiction" in val.message


def test_intra_pref_ambiguity_kanagawa_midori_ku():
    """神奈川県緑区1-1 is ambiguous between Yokohama and Sagamihara."""
    res = normalize("神奈川県緑区1-1")
    comp = res.components
    assert comp.prefecture == "神奈川県"
    assert comp.city is None
    assert comp.ward == "緑区"
    assert comp.lg_code is None
    assert comp.is_ambiguous is True
    assert len(comp.ambiguous_candidates) == 2
    assert any("横浜市緑区" in c for c in comp.ambiguous_candidates)
    assert any("相模原市緑区" in c for c in comp.ambiguous_candidates)


def test_intra_pref_ambiguity_osaka_kita_ku():
    """大阪府北区梅田1-1-1 is ambiguous between Osaka City and Sakai City."""
    res = normalize("大阪府北区梅田1-1-1")
    comp = res.components
    assert comp.prefecture == "大阪府"
    assert comp.prefecture_code == "27"
    assert comp.city is None
    assert comp.ward == "北区"
    assert comp.lg_code is None
    assert comp.is_ambiguous is True
    assert len(comp.ambiguous_candidates) == 2
    assert any("大阪市北区" in c for c in comp.ambiguous_candidates)
    assert any("堺市北区" in c for c in comp.ambiguous_candidates)
    assert res.confidence_score == 0.50

    val = validate("大阪府北区梅田1-1-1")
    assert val.status == ValidationStatus.AMBIGUOUS.value
    assert val.valid is False


def test_intra_pref_ambiguity_osaka_nishi_ku():
    """大阪府西区1-1 is ambiguous between Osaka City and Sakai City."""
    res = normalize("大阪府西区1-1")
    comp = res.components
    assert comp.prefecture == "大阪府"
    assert comp.city is None
    assert comp.ward == "西区"
    assert comp.lg_code is None
    assert comp.is_ambiguous is True
    assert len(comp.ambiguous_candidates) == 2
    assert any("大阪市西区" in c for c in comp.ambiguous_candidates)
    assert any("堺市西区" in c for c in comp.ambiguous_candidates)


def test_intra_pref_disambiguated_by_city_kanagawa():
    """Explicit designated city resolves Kanagawa wards deterministically."""
    yokohama = normalize("神奈川県横浜市南区1-1")
    assert yokohama.components.prefecture == "神奈川県"
    assert yokohama.components.city == "横浜市"
    assert yokohama.components.ward == "南区"
    assert yokohama.components.lg_code == "141054"
    assert yokohama.components.is_ambiguous is False
    assert yokohama.confidence_score == 1.0

    sagamihara = normalize("神奈川県相模原市南区1-1")
    assert sagamihara.components.prefecture == "神奈川県"
    assert sagamihara.components.city == "相模原市"
    assert sagamihara.components.ward == "南区"
    assert sagamihara.components.lg_code == "141534"
    assert sagamihara.components.is_ambiguous is False
    assert sagamihara.confidence_score == 1.0


def test_intra_pref_disambiguated_by_city_osaka():
    """Explicit designated city resolves Osaka wards deterministically."""
    osaka_city = normalize("大阪府大阪市北区梅田1-1")
    assert osaka_city.components.prefecture == "大阪府"
    assert osaka_city.components.city == "大阪市"
    assert osaka_city.components.ward == "北区"
    assert osaka_city.components.lg_code == "271276"
    assert osaka_city.components.is_ambiguous is False
    assert osaka_city.confidence_score == 1.0

    sakai_city = normalize("大阪府堺市北区新金岡町1-1")
    assert sakai_city.components.prefecture == "大阪府"
    assert sakai_city.components.city == "堺市"
    assert sakai_city.components.ward == "北区"
    assert sakai_city.components.lg_code == "271462"
    assert sakai_city.components.is_ambiguous is False
    assert sakai_city.confidence_score == 1.0


def test_unique_ward_in_prefecture():
    """Wards unique within their prefecture resolve directly without ambiguity."""
    res = normalize("神奈川県中区本町1-1")
    assert res.components.prefecture == "神奈川県"
    assert res.components.city == "横浜市"
    assert res.components.ward == "中区"
    assert res.components.lg_code == "141046"
    assert res.components.is_ambiguous is False
