"""Unit tests for PrefixTrie and AdministrativeParser."""

from jaden.core.trie import PrefixTrie
from jaden.parsers.administrative import AdministrativeParser


def test_prefix_trie_longest_match():
    trie: PrefixTrie[str] = PrefixTrie()
    trie.insert("東京", "stem")
    trie.insert("東京都", "full")
    trie.insert("東京都港区", "ward")

    match = trie.longest_prefix("東京都港区六本木")
    assert match is not None
    matched_key, val, next_idx = match
    assert matched_key == "東京都港区"
    assert val == "ward"
    assert next_idx == 5


def test_administrative_parser_full_address():
    parser = AdministrativeParser()
    pref, muni, rem, inferred = parser.parse("東京都港区六本木6-10-1")
    assert pref is not None
    assert pref.code == "13"
    assert pref.name == "東京都"
    assert muni is not None
    assert muni.city == "港区"
    assert muni.lg_code == "131032"
    assert rem == "六本木6-10-1"
    assert inferred is False


def test_administrative_parser_omitted_prefecture():
    parser = AdministrativeParser()
    # User omitted '東京都'
    pref, muni, rem, inferred = parser.parse("新宿区西新宿2-8-1")
    assert pref is not None
    assert pref.code == "13"
    assert pref.name == "東京都"
    assert muni is not None
    assert muni.city == "新宿区"
    assert muni.lg_code == "131041"
    assert rem == "西新宿2-8-1"
    assert inferred is True


def test_administrative_parser_designated_city_omitted():
    parser = AdministrativeParser()
    # User wrote '京都府中京区...' omitting '京都市'
    pref, muni, rem, inferred = parser.parse("京都府中京区寺町通御池上る")
    assert pref is not None
    assert pref.code == "26"
    assert muni is not None
    assert muni.city == "京都市"
    assert muni.ward == "中京区"
    assert muni.lg_code == "261041"
    assert rem == "寺町通御池上る"
    assert inferred is False
