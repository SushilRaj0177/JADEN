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


def test_hyphenated_kanji_numerals():
    assert normalize_kanji_numerals_in_blocks("六本木三-二-一") == "六本木3-2-1"
    assert normalize_kanji_numerals_in_blocks("六本木三-二") == "六本木3-2"
    assert normalize_kanji_numerals_in_blocks("六本木3-二-1") == "六本木3-2-1"
    assert normalize_kanji_numerals_in_blocks("四日市市諏訪町三-五") == "四日市市諏訪町3-5"


def test_hyphenated_kanji_proper_noun_safety():
    assert normalize_kanji_numerals_in_blocks("千代田区三番町三-二-一") == "千代田区三番町3-2-1"
    assert normalize_kanji_numerals_in_blocks("千代田区一番町一-二") == "千代田区一番町1-2"
    assert normalize_kanji_numerals_in_blocks("港区麻布十番一-一") == "港区麻布十番1-1"
    assert normalize_kanji_numerals_in_blocks("港区麻布十番1-1") == "港区麻布十番1-1"
    assert normalize_kanji_numerals_in_blocks("中央区八重洲二-一") == "中央区八重洲2-1"
    assert normalize_kanji_numerals_in_blocks("北区十条仲原一-二-三") == "北区十条仲原1-2-3"


def test_building_name_kanji_numeral_preservation():
    # Building names like 第一-3ビル must not have their kanji numbers rewritten
    assert normalize_kanji_numerals_in_blocks("第一-3ビル") == "第一-3ビル"
    assert normalize_kanji_numerals_in_blocks("第二-5ビル") == "第二-5ビル"
    assert normalize_kanji_numerals_in_blocks("六本木三-二-一 第一-3ビル") == "六本木3-2-1 第一-3ビル"
