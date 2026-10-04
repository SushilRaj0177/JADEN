"""Unit tests for edge cases, malformed strings, and dirty real-world inputs."""

from jaden.engine import AddressNormalizer


def test_empty_and_whitespace_inputs():
    normalizer = AddressNormalizer()
    res1 = normalizer.normalize("")
    assert res1.canonical == ""
    assert res1.confidence_score == 0.0

    res2 = normalizer.normalize("   \t  \u3000 ")
    assert res2.canonical == ""
    assert res2.confidence_score == 0.0


def test_complex_dash_mixture():
    normalizer = AddressNormalizer()
    # Mixed full-width, em-dash, wave dash, choonpu between numbers
    inp = "東京都千代田区霞が関１―２～３ー４"
    res = normalizer.normalize(inp)
    assert res.components.prefecture == "東京都"
    assert res.components.city == "千代田区"
    assert res.components.town == "霞が関"
    assert res.components.chome == 1
    assert res.components.ban == 2


def test_omitted_prefecture_tokyo_special_ward():
    normalizer = AddressNormalizer()
    # '新宿区西新宿2-8-1 東京都庁'
    res = normalizer.normalize("新宿区西新宿2-8-1 東京都庁")
    assert res.components.prefecture == "東京都"
    assert res.components.prefecture_inferred is True
    assert res.components.city == "新宿区"
    assert res.components.town == "西新宿"
    assert res.components.chome == 2
    assert res.components.ban == 8
    assert res.components.go == 1
    assert res.components.building == "東京都庁"


def test_omitted_prefecture_yokohama():
    normalizer = AddressNormalizer()
    res = normalizer.normalize("横浜市中区海岸通1-1")
    assert res.components.prefecture == "神奈川県"
    assert res.components.prefecture_inferred is True
    assert res.components.city == "横浜市"
    assert res.components.ward == "中区"
    assert res.components.lg_code == "141046"


def test_compound_building_name():
    normalizer = AddressNormalizer()
    res = normalizer.normalize("東京都墨田区押上1-1-2 東京スカイツリーイーストタワー 31階")
    assert res.components.building == "東京スカイツリーイーストタワー"
    assert res.components.floor == "31階"
