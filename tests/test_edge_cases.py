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


def test_postal_code_prefix_normalization():
    import jaden
    addr1 = "〒106-0032 東京都港区六本木6-10-1"
    r1 = jaden.normalize(addr1)
    v1 = jaden.validate(addr1)
    assert r1.canonical == "東京都港区六本木6丁目10番1号"
    assert v1.status == "ACCEPTED"
    assert v1.valid is True

    addr2 = "106-0032 東京都港区六本木6-10-1"
    r2 = jaden.normalize(addr2)
    assert r2.canonical == "東京都港区六本木6丁目10番1号"
    assert jaden.validate(addr2).status == "ACCEPTED"

    addr3 = "〒106-0032東京都港区六本木6-10-1"
    r3 = jaden.normalize(addr3)
    assert r3.canonical == "東京都港区六本木6丁目10番1号"

    addr4 = "106-0032東京都港区六本木6-10-1"
    r4 = jaden.normalize(addr4)
    assert r4.canonical == "東京都港区六本木6丁目10番1号"

    # Bare postal code without address must not be accepted
    v_bare = jaden.validate("〒106-0032")
    assert v_bare.status != "ACCEPTED"


def test_box_drawing_dash_normalization():
    import jaden
    addr = "東京都港区六本木1─2─3"
    r = jaden.normalize(addr)
    assert r.canonical == "東京都港区六本木1丁目2番3号"
    assert r.components.chome == 1
    assert r.components.ban == 2
    assert r.components.go == 3
    assert jaden.validate(addr).status == "ACCEPTED"


def test_kanji_numeral_dashes_normalization():
    import jaden
    addr1 = "東京都港区六本木三ー二ー一"
    r1 = jaden.normalize(addr1)
    assert r1.canonical == "東京都港区六本木3丁目2番1号"
    assert r1.components.town == "六本木"
    assert r1.components.chome == 3
    assert r1.components.ban == 2
    assert r1.components.go == 1
    assert jaden.validate(addr1).status == "ACCEPTED"

    addr2 = "東京都港区六本木三-二-一"
    r2 = jaden.normalize(addr2)
    assert r2.canonical == "東京都港区六本木3丁目2番1号"
    assert r2.components.town == "六本木"
    assert r2.components.chome == 3
    assert r2.components.ban == 2
    assert r2.components.go == 1
    assert jaden.validate(addr2).status == "ACCEPTED"

    addr3 = "東京都千代田区三番町三-二-一"
    r3 = jaden.normalize(addr3)
    assert r3.canonical == "東京都千代田区三番町3丁目2番1号"
    assert r3.components.town == "三番町"
    assert r3.components.chome == 3


def test_embedded_newline_normalization():
    import jaden
    addr1 = "東京都港区六本木6-10-1\n改行"
    r1 = jaden.normalize(addr1)
    assert r1.canonical == "東京都港区六本木6丁目10番1号 改行"
    assert r1.components.town == "六本木"
    assert r1.components.chome == 6
    assert r1.components.ban == 10
    assert r1.components.go == 1
    assert r1.components.building == "改行"

    addr2 = "東京都\n港区\r\n六本木6-10-1"
    r2 = jaden.normalize(addr2)
    assert r2.canonical == "東京都港区六本木6丁目10番1号"
