"""Unit tests for Kanji numeral conversion and proper noun collision safety."""

from jaden.core.kanji_numerals import parse_kanji_number, normalize_kanji_numerals_in_blocks


def test_parse_kanji_number_positional():
    assert parse_kanji_number("一") == 1
    assert parse_kanji_number("十") == 10
    assert parse_kanji_number("十二") == 12
    assert parse_kanji_number("二十") == 20
    assert parse_kanji_number("二十三") == 23
    assert parse_kanji_number("百") == 100
    assert parse_kanji_number("百五") == 105
    assert parse_kanji_number("百二十三") == 123
    assert parse_kanji_number("四百八十八") == 488
    assert parse_kanji_number("千二百三十四") == 1234


def test_parse_kanji_number_direct_sequence():
    assert parse_kanji_number("一二三") == 123
    assert parse_kanji_number("〇") == 0
    assert parse_kanji_number("零") == 0


def test_parse_kanji_number_daiji():
    assert parse_kanji_number("壱") == 1
    assert parse_kanji_number("弐") == 2
    assert parse_kanji_number("参") == 3
    assert parse_kanji_number("拾") == 10
    assert parse_kanji_number("拾弐") == 12


def test_proper_noun_collision_protection():
    # Crucial test: Famous places with embedded numbers must NOT be modified
    assert normalize_kanji_numerals_in_blocks("港区六本木三丁目") == "港区六本木3丁目"
    assert normalize_kanji_numerals_in_blocks("八王子市明神町") == "八王子市明神町"
    assert normalize_kanji_numerals_in_blocks("四日市市三番町1-2") == "四日市市三番町1-2"
    assert normalize_kanji_numerals_in_blocks("品川区五反田一丁目") == "品川区五反田1丁目"
    assert normalize_kanji_numerals_in_blocks("北区十条仲原二丁目") == "北区十条仲原2丁目"
    assert normalize_kanji_numerals_in_blocks("千代田区九段南") == "千代田区九段南"
    assert normalize_kanji_numerals_in_blocks("世田谷区二子玉川") == "世田谷区二子玉川"
    assert normalize_kanji_numerals_in_blocks("港区一番街1-1") == "港区一番街1-1"
    assert normalize_kanji_numerals_in_blocks("港区麻布十番1-1") == "港区麻布十番1-1"
    assert normalize_kanji_numerals_in_blocks("千代田区一番町一番館301") == "千代田区一番町一番館301"


def test_block_kanji_numerals_normalization():
    assert normalize_kanji_numerals_in_blocks("六丁目10番1号") == "6丁目10番1号"
    assert normalize_kanji_numerals_in_blocks("488番地") == "488番地"
    assert normalize_kanji_numerals_in_blocks("四百八十八番地") == "488番地"
    assert normalize_kanji_numerals_in_blocks("十二丁目五番") == "12丁目5番"
