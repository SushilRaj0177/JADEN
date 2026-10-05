"""Unit tests for Hokkaido cardinal Jo-Chome grid parser."""

from jaden.parsers.hokkaido import HokkaidoParser


def test_hokkaido_parser_arabic():
    clause, rem = HokkaidoParser.parse("北1条西2丁目1番地")
    assert clause is not None
    assert clause.cardinal_ns == "北"
    assert clause.jo == 1
    assert clause.cardinal_ew == "西"
    assert clause.chome == 2
    assert clause.raw_clause == "北1条西2丁目"
    assert rem == "1番地"


def test_hokkaido_parser_kanji():
    clause, rem = HokkaidoParser.parse("南三条東四丁目5番")
    assert clause is not None
    assert clause.cardinal_ns == "南"
    assert clause.jo == 3
    assert clause.cardinal_ew == "東"
    assert clause.chome == 4
    assert rem == "5番"


def test_hokkaido_parser_non_grid():
    clause, rem = HokkaidoParser.parse("函館市本町1-1")
    assert clause is None
    assert rem == "函館市本町1-1"


def test_osaka_non_hokkaido_grid_retention():
    import jaden
    addr = "大阪府大阪市北区南森町北1条西2丁目"
    res = jaden.normalize(addr)
    assert res.components.hokkaido_grid is None
    assert "南森町" in res.canonical
    assert "南森町" in (res.components.town or "")
    assert res.canonical == "大阪府大阪市北区南森町北1条西2丁目"


def test_ambiguous_ward_with_grid():
    import jaden
    addr = "北区北7条西5丁目"
    res = jaden.normalize(addr)
    val = jaden.validate(addr)
    assert res.components.prefecture is None
    assert val.status == "AMBIGUOUS"
    assert val.valid is False
    assert any("011029" in c for c in val.ambiguous_candidates)
    assert any("131172" in c for c in val.ambiguous_candidates)


def test_chuo_ku_sapporo_disambiguation():
    import jaden
    addr = "中央区南1条西2丁目"
    res = jaden.normalize(addr)
    val = jaden.validate(addr)
    assert res.components.prefecture == "北海道"
    assert res.components.city == "札幌市"
    assert res.components.ward == "中央区"
    assert res.components.lg_code == "011011"
    assert val.status == "ACCEPTED"
    assert val.valid is True
    assert res.confidence_score == 0.85


def test_sapporo_control():
    import jaden
    addr = "北海道札幌市北区北7条西5丁目"
    res = jaden.normalize(addr)
    val = jaden.validate(addr)
    assert res.components.lg_code == "011029"
    assert res.components.hokkaido_grid is not None
    assert res.components.hokkaido_grid.jo == 7
    assert res.components.hokkaido_grid.chome == 5
    assert val.status == "ACCEPTED"
    assert val.valid is True
