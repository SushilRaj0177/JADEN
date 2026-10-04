"""Unit tests for Kyoto street-intersection navigation parser."""

from jaden.parsers.kyoto import KyotoParser


def test_kyoto_parser_agaru():
    clause, rem = KyotoParser.parse("寺町通御池上る上本能寺前町488番地")
    assert clause is not None
    assert clause.street_1 == "寺町通"
    assert clause.street_2 == "御池"
    assert clause.direction == "上る"
    assert clause.cardinal == "north"
    assert clause.raw_clause == "寺町通御池上る"
    assert rem == "上本能寺前町488番地"


def test_kyoto_parser_sagaru_katakana():
    # Test '下ル'
    clause, rem = KyotoParser.parse("烏丸通七条下ル東塩小路町721-1")
    assert clause is not None
    assert clause.street_1 == "烏丸通"
    assert clause.street_2 == "七条"
    assert clause.direction == "下ル"
    assert clause.cardinal == "south"
    assert rem == "東塩小路町721-1"


def test_kyoto_parser_higashi_iru():
    clause, rem = KyotoParser.parse("河原町通四条東入真町68")
    assert clause is not None
    assert clause.street_1 == "河原町通"
    assert clause.street_2 == "四条"
    assert clause.direction == "東入"
    assert clause.cardinal == "east"
    assert rem == "真町68"


def test_kyoto_parser_nishi_iru():
    clause, rem = KyotoParser.parse("御池通烏丸西入る西横町123")
    assert clause is not None
    assert clause.street_1 == "御池通"
    assert clause.street_2 == "烏丸"
    assert clause.direction == "西入る"
    assert clause.cardinal == "west"
    assert rem == "西横町123"


def test_non_kyoto_text():
    clause, rem = KyotoParser.parse("六本木6-10-1")
    assert clause is None
    assert rem == "六本木6-10-1"
