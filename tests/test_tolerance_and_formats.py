"""Kana town names, typo suggestions and autocorrect, precision levels, output formats."""

import pytest

import jaden
from jaden.core.townkey import is_kana, kana_key, one_edit_apart
from jaden.engine import AddressNormalizer


# ------------------------------------------------------------------- kana
def test_kana_key_folds_scripts_and_small_kana():
    assert kana_key("しばこうえん") == kana_key("シバコウエン") == kana_key("ｼﾊﾞｺｳｴﾝ")
    assert kana_key("キョウト") == kana_key("キヨウト")
    assert is_kana("しばこうえん") and not is_kana("芝こうえん") and not is_kana("123")


@pytest.mark.parametrize("raw, canonical", [
    ("東京都港区しばこうえん4-2-8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区シバコウエン4-2-8", "東京都港区芝公園4丁目2番8号"),
    ("港区ろっぽんぎ6-10-1", "東京都港区六本木6丁目10番1号"),
    ("東京都千代田区かすみがせき1-2-1", "東京都千代田区霞が関1丁目2番1号"),
    ("大阪市北区うめだ3-1-1", "大阪府大阪市北区梅田3丁目1番1号"),
])
def test_town_written_by_its_reading(raw, canonical):
    res = jaden.normalize(raw)
    assert res.canonical == canonical
    assert res.components.town_verified is True
    assert any("by its reading" in n for n in res.notes)


def test_kana_town_still_checks_chome():
    assert jaden.validate("東京都港区しばこうえん9-2-8").status == "MALFORMED"


def test_registered_kana_town_is_untouched():
    res = jaden.normalize("横浜市西区みなとみらい2-2-1")
    assert res.components.town == "みなとみらい" and not res.notes


# ------------------------------------------------------------------ typos
def test_one_edit_apart():
    assert one_edit_apart("芝公演", "芝公園")      # substitution
    assert one_edit_apart("芝公", "芝公園")        # deletion
    assert one_edit_apart("公芝園", "芝公園")      # swap
    assert not one_edit_apart("芝公園", "芝公園")
    assert not one_edit_apart("芝浦", "六本木")


def test_typo_is_suggested_not_applied_by_default():
    res = jaden.normalize("東京都港区芝公演4-2-8")
    assert res.components.town == "芝公演"
    assert res.components.town_verified is False
    assert res.suggestions == ("東京都港区芝公園4丁目2番8号",)
    val = jaden.validate("東京都港区芝公演4-2-8")
    assert val.suggestions == res.suggestions
    assert val.verification_level == "municipality"


def test_autocorrect_applies_a_unique_correction_and_keeps_the_original():
    res = jaden.normalize("東京都港区六本気6-10-1 森タワー", autocorrect=True)
    assert res.canonical == "東京都港区六本木6丁目10番1号 森タワー"
    assert res.components.town_corrected_from == "六本気"
    assert res.input_raw == "東京都港区六本気6-10-1 森タワー"
    assert any("corrected town" in n for n in res.notes)
    assert jaden.validate("東京都港区六本気6-10-1", autocorrect=True).verification_level == "chome"


def test_autocorrect_does_not_choose_between_two_candidates():
    # 南長里 is one character from both 南長野 and 南長池
    res = jaden.normalize("長野県長野市南長里692-2", autocorrect=True)
    assert res.components.town == "南長里"
    assert len(res.suggestions) == 2


def test_autocorrect_leaves_two_character_towns_as_suggestions():
    res = jaden.normalize("福岡市中央区天人1-8-1", autocorrect=True)
    assert res.components.town == "天人"
    assert res.suggestions == ("福岡県福岡市中央区天神1丁目8番1号",)


def test_numbered_towns_are_never_corrected_to_another_number():
    assert jaden.normalize("東京都港区存在しない町1-1").suggestions == ()
    engine = AddressNormalizer(autocorrect=True)
    assert engine.normalize("札幌市中央区北9条西99丁目").components.town_corrected_from is None


# -------------------------------------------------------------- precision
@pytest.mark.parametrize("raw, precision", [
    ("東京都港区芝公園4-2-8 101号室", "unit"),
    ("東京都港区芝公園4-2-8", "house"),
    ("長野県長野市大字南長野字幅下692-2", "house"),
    ("岩手県盛岡市西見前20-113-1", "house"),
    ("東京都港区芝公園4-2", "block"),
    ("東京都港区芝公園4", "chome"),
    ("東京都港区芝公園", "town"),
    ("東京都港区", "municipality"),
])
def test_precision(raw, precision):
    assert jaden.normalize(raw).precision == precision
    assert jaden.validate(raw).precision == precision


def test_area_only_address_gets_a_warning():
    val = jaden.validate("東京都港区芝公園")
    assert val.status == "ACCEPTED"
    assert any("not a building" in w for w in val.warnings)
    assert not any("not a building" in w for w in jaden.validate("東京都港区芝公園4-2-8").warnings)


# ---------------------------------------------------------------- formats
def test_formats():
    res = jaden.normalize("東京都港区芝公園4丁目2番8号 グランドメゾン芝公園 302号室")
    assert res.format("hyphen") == "東京都港区芝公園4-2-8 グランドメゾン芝公園 302号室"
    assert res.format("en") == "グランドメゾン芝公園 #302, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011"
    assert res.lines() == ("〒105-0011", "東京都港区芝公園4丁目2番8号", "グランドメゾン芝公園 302号室")
    assert res.to_dict()["hyphenated"] == res.format("hyphen")
    with pytest.raises(ValueError):
        res.format("nope")


@pytest.mark.parametrize("raw", [
    "札幌市中央区北1条西2丁目1-1", "岩手県盛岡市西見前20-113-1", "長野県長野市大字南長野字幅下692-2",
    "群馬県桐生市相生町1-乙394", "京都市中京区寺町通御池上る上本能寺前町488", "東京都千代田区一番町1",
    "埼玉県春日部市大字上大増新田140", "北海道河西郡芽室町字北明西7線18", "東京都港区芝公園4",
])
def test_hyphen_form_round_trips(raw):
    res = jaden.normalize(raw)
    assert jaden.normalize(res.format("hyphen")).canonical == res.canonical


def test_written_oaza_is_kept():
    # 上大増新田 is registered without 大字; the input's 大字 is kept and marks the lot as 地番
    assert jaden.normalize("埼玉県春日部市大字上大増新田140").canonical == "埼玉県春日部市大字上大増新田140番地"
