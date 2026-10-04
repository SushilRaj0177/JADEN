"""Unit tests for BuildingParser."""

from jaden.parsers.building import BuildingParser


def test_building_parser_floor():
    bldg, floor, unit = BuildingParser.parse("六本木ヒルズ森タワー 50F")
    assert bldg == "六本木ヒルズ森タワー"
    assert floor == "50F"
    assert unit is None


def test_building_parser_floor_cjk():
    bldg, floor, unit = BuildingParser.parse("森タワー50階")
    assert bldg == "森タワー"
    assert floor == "50階"


def test_building_parser_unit():
    bldg, floor, unit = BuildingParser.parse("メゾン早稲田 301号室")
    assert bldg == "メゾン早稲田"
    assert unit == "301号室"


def test_building_parser_floor_and_unit():
    bldg, floor, unit = BuildingParser.parse("グランドタワー 3階 302号室")
    assert bldg == "グランドタワー"
    assert floor == "3階"
    assert unit == "302号室"


def test_building_parser_basement():
    bldg, floor, unit = BuildingParser.parse("飲食プラザ B1F")
    assert bldg == "飲食プラザ"
    assert floor == "B1F"
