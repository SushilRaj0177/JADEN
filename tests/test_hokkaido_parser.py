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
