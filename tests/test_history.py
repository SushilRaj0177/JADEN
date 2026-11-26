"""Municipal history: retired codes and the municipality an address belonged to in 2000."""

import jaden
from jaden.history import code_change, current_codes, former_municipality


def test_a_current_code_stands_for_itself() -> None:
    assert current_codes("131032") == ("131032",)
    assert current_codes("13103") == ("131032",)          # five digits get their check digit


def test_a_merged_municipality_maps_to_its_successor_with_the_date() -> None:
    change = code_change("112267")                          # 鳩ヶ谷市, merged into 川口市
    assert change is not None
    assert change.successors == ("112038",) and change.date == "2011-10-11" and "川口市" in change.reason
    assert current_codes("112267") == ("112038",)


def test_the_2024_hamamatsu_ward_codes() -> None:
    assert current_codes("221317") == ("221384",)           # 中区 -> 中央区
    assert set(current_codes("221350")) == {"221384", "221392"}  # 北区 was split
    assert current_codes("221376") == ("221406",)           # 天竜区 kept its name, got a new code
    assert code_change("221376").date == "2024-01-01"


def test_a_code_that_never_existed() -> None:
    assert current_codes("999999") == ()
    assert code_change("999999") is None


def test_former_municipality_of_a_current_address() -> None:
    f = former_municipality("岐阜県多治見市笠原町2950")
    assert f is not None and f.name == "笠原町" and f.abolished == "2006-01-23"
    assert f.successors == ("212041",)
    urawa = former_municipality(jaden.normalize("埼玉県さいたま市浦和区高砂3-15-1"))
    assert urawa is not None and urawa.name == "浦和市"


def test_an_unchanged_municipality_has_no_former_one() -> None:
    assert former_municipality("東京都港区芝公園4-2-8") is None
    assert former_municipality("あいうえお") is None
