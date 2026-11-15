"""Address matching: match_key, compare, find_duplicates, and the compare / dedupe commands."""

import csv
import io

import pytest

from jaden.batch import run_dedupe
from jaden.cli import main
from jaden.matching import compare, find_duplicates, match_key


@pytest.mark.parametrize("a, b", [
    ("東京都港区芝公園4-2-8 グランドメゾン芝公園302", "港区芝公園４丁目２番８号　グランドメゾン芝公園　３０２号室"),
    ("東京都港区芝公園4-2-8", "〒105-0011 港区しばこうえん四丁目2番8号"),
    ("埼玉県浦和市高砂3-15-1", "さいたま市浦和区高砂3丁目15番1号"),
    ("4-2-8 Shibakoen, Minato-ku, Tokyo", "東京都港区芝公園4-2-8"),
    ("札幌市中央区南3西4-1-1", "北海道札幌市中央区南3条西4丁目1番1号"),
    ("東京都西多摩郡日の出町平井2780", "西多摩郡日の出町大字平井2780番地"),
    ("長野県長野市大字南長野字幅下692-2", "長野市南長野幅下692-2"),
    ("京都市中京区寺町通御池上る上本能寺前町488", "京都府京都市中京区上本能寺前町488番地"),
])
def test_same_place_written_differently(a, b):
    result = compare(a, b)
    assert result.verdict == "same" and result.same
    assert match_key(a) == match_key(b) is not None


@pytest.mark.parametrize("a, b, conflict", [
    ("東京都港区芝公園4-2-8", "東京都港区芝公園4-2-9", "house"),
    ("東京都港区芝公園4-2-8", "東京都港区芝公園4-3-8", "block"),
    ("東京都港区芝公園4-2-8", "東京都港区芝公園3-2-8", "chome"),
    ("東京都港区芝公園4-2-8", "東京都港区六本木4-2-8", "town"),
    ("東京都港区芝公園4-2-8", "東京都新宿区西新宿2-8-1", "municipality"),
    ("東京都港区芝公園4-2-8", "大阪市港区築港4-2-8", "prefecture"),
    ("宮城県遠田郡涌谷町涌谷字八方谷1", "宮城県遠田郡涌谷町涌谷字小人町1", "koaza"),
])
def test_different_places(a, b, conflict):
    result = compare(a, b)
    assert result.verdict == "different"
    assert result.conflict == conflict
    assert match_key(a) != match_key(b)


def test_rooms():
    same_room = compare("東京都港区芝公園4-2-8-101", "東京都港区芝公園4-2-8 101号室")
    assert same_room.verdict == "same" and same_room.level == "unit"
    other_room = compare("東京都港区芝公園4-2-8 101", "東京都港区芝公園4-2-8 102号室")
    assert other_room.verdict == "same_building" and other_room.conflict == "unit"
    no_room = compare("東京都港区芝公園4-2-8", "東京都港区芝公園4-2-8 102号室")
    assert no_room.verdict == "same_building" and no_room.missing == ("unit",)


def test_floor_counts_as_unit_and_building_names_do_not_decide():
    result = compare("東京都港区六本木6-10-1 六本木ヒルズ森タワー 50F", "港区六本木6丁目10番1号 森タワー50階")
    assert result.verdict == "same"
    assert "building names differ" in result.notes


def test_less_specific_or_ambiguous_is_possibly_same():
    assert compare("東京都港区芝公園4-2-8", "東京都港区芝公園").verdict == "possibly_same"
    ambiguous = compare("府中市1-1", "東京都府中市1-1")
    assert ambiguous.verdict == "possibly_same" and "municipality" in ambiguous.missing
    assert compare("府中市1-1", "大阪市北区梅田1-1").verdict == "different"
    # A 字 written on one side only is not proof: lot numbers can repeat between 字
    koaza = compare("長野県長野市大字南長野字幅下692-2", "長野市南長野692-2")
    assert koaza.verdict == "possibly_same" and "koaza" in koaza.missing


def test_not_an_address_is_undetermined():
    assert compare("東京タワー", "東京都港区芝公園4-2-8").verdict == "undetermined"


def test_match_key_levels():
    a = "港区芝公園４丁目２番８号 ３０２号室"
    assert match_key(a) == "131032|芝公園|4|2|8|302"
    assert match_key(a, "house") == "131032|芝公園|4|2|8"
    assert match_key(a, "block") == "131032|芝公園|4|2"
    assert match_key(a, "chome") == "131032|芝公園|4"
    assert match_key(a, "town") == "131032|芝公園"
    assert match_key("東京都港区芝公園") is None           # no house number
    assert match_key("東京都港区芝公園", "town") == "131032|芝公園"
    assert match_key("府中市1-1") is None                  # ambiguous municipality
    assert match_key("東京タワー") is None
    with pytest.raises(ValueError):
        match_key(a, "galaxy")


def test_find_duplicates():
    groups = find_duplicates([
        "東京都港区芝公園4-2-8", "港区芝公園４－２－８", "東京都港区芝公園4-2-8 101",
        "東京タワー", "港区しばこうえん4丁目2番8号 101号室",
    ])
    assert groups == [1, 1, 2, None, 2]
    assert find_duplicates(["東京都港区芝公園4-2-8", "東京都港区芝公園4-2-8 101"], level="house") == [1, 1]


def test_dedupe_file(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(
        "id,住所\n1,東京都港区芝公園4-2-8 101号室\n2,港区芝公園４丁目２番８号　１０１\n"
        "3,埼玉県浦和市高砂3-15-1\n4,さいたま市浦和区高砂3丁目15番1号\n5,東京タワー\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    summary = run_dedupe(src, out, log=io.StringIO())
    rows = list(csv.DictReader(io.StringIO(out.read_text(encoding="utf-8"))))
    assert [r["jaden_group"] for r in rows] == ["1", "1", "2", "2", ""]
    assert rows[0]["jaden_group_size"] == "2"
    assert summary == {"rows": 5, "groups": 2, "duplicate_groups": 2, "rows_in_duplicate_groups": 4, "unkeyed_rows": 1}


def test_compare_command_exit_codes(capsys):
    assert main(["compare", "東京都港区芝公園4-2-8", "港区芝公園４－２－８"]) == 0
    assert main(["compare", "東京都港区芝公園4-2-8", "東京都港区芝公園4-2-9"]) == 1
    assert main(["compare", "東京都港区芝公園4-2-8", "東京都港区芝公園4-2-8 101"]) == 2
    assert main(["compare", "東京タワー", "東京都港区芝公園4-2-8", "--json"]) == 3
    assert '"verdict": "undetermined"' in capsys.readouterr().out
