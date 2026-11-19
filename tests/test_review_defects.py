"""Defects found by independent reviews of v0.3 (18 Nov 2026), each pinned by the input that showed it."""

import time

import pytest

import jaden
from jaden.engine import MAX_INPUT_CHARS


@pytest.mark.parametrize("text", ["9" * 20000, "一" * 5000, "東京都港区芝公園" + "4" * 4400])
def test_overlong_input_is_rejected_quickly_without_crashing(text: str) -> None:
    start = time.perf_counter()
    v = jaden.validate(text)
    res = jaden.normalize(text)
    assert time.perf_counter() - start < 1.0
    assert v.status == "MALFORMED" and "at most" in v.message
    assert res.canonical == "" and res.confidence_score == 0.0
    assert jaden.match_key(text) is None


def test_input_at_the_limit_is_still_read() -> None:
    address = "東京都港区芝公園4-2-8"
    padded = address + " " * (MAX_INPUT_CHARS - len(address))
    assert jaden.validate(padded).status == "ACCEPTED"


@pytest.mark.parametrize("address", [
    "徳島県板野郡松茂町中喜来字前原西一番越14",       # a town name holding 一番: 14番地 is still the lot
    "東京都港区芝公園4-2-8",
    "東京都港区麻布十番1-2-3",
])
def test_canonical_form_is_stable(address: str) -> None:
    once = jaden.normalize(address).canonical
    assert jaden.normalize(once).canonical == once


def test_number_after_a_name_with_ichiban_is_the_lot() -> None:
    c = jaden.normalize("徳島県板野郡松茂町中喜来字前原西一番越14番地").components
    assert c.banchi == 14 and c.building is None


@pytest.mark.parametrize("address", ["東京都千代田区丸の内0-0-0", "東京都千代田区丸の内1-0-1", "東京都港区芝公園4丁目2番0号"])
def test_zero_block_numbers_are_rejected(address: str) -> None:
    v = jaden.validate(address)
    assert v.status == "MALFORMED" and "numbered 0" in v.message


@pytest.mark.parametrize("text", ["東京都23区", "東京府東京市麹町区永田町1丁目"])
def test_unresolved_text_is_returned_as_written(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == text
    assert any("not interpreted" in n for n in res.notes)


@pytest.mark.parametrize("text, unit", [
    ("東京都港区芝公園4-2-8に送って下さい", None),
    ("東京都港区芝公園4-2-8 ハイツ田中101号室までお願いします", "101号室"),
    ("東京都港区芝公園4-2-8 芝ビル3階 宛", None),
])
def test_a_sentence_after_the_address_is_not_a_building(text: str, unit: object) -> None:
    c = jaden.normalize(text).components
    assert c.building in (None, "ハイツ田中", "芝ビル")
    assert c.unit == unit
    assert jaden.validate(text).status == "ACCEPTED"


def test_building_names_with_hiragana_are_kept() -> None:
    assert jaden.normalize("東京都港区芝公園4-2-8 グランデ芝101").components.building == "グランデ芝"


def test_unregistered_town_says_only_the_municipality_was_verified() -> None:
    v = jaden.validate("東京都港区ほげほげ4-2-8")
    assert v.verification_level == "municipality"
    assert any("not registered" in w for w in v.warnings)
    assert jaden.validate("東京都港区ほげほげ4-2-8", strict=True).status != "ACCEPTED"


@pytest.mark.parametrize("address", ["三重県四日市市采女町100", "三重県四日市市釆女町100"])
def test_both_spellings_of_uneme_are_the_registered_town(address: str) -> None:
    v = jaden.validate(address)
    assert v.status == "ACCEPTED" and v.verification_level == "town"


@pytest.mark.parametrize("text, status, city", [
    ("鹿島市1-1", "AMBIGUOUS", None),             # Saga's 鹿島市, or Ibaraki's 鹿嶋市 written the usual way
    ("鹿嶋市1-1", "ACCEPTED", "鹿嶋市"),          # the variant spelling is only Ibaraki's
    ("鹿島市大字高津原1", "ACCEPTED", "鹿島市"),  # the town decides
    ("鹿島市平井1", "ACCEPTED", "鹿嶋市"),
    ("茨城県鹿島市平井1", "ACCEPTED", "鹿嶋市"),  # the prefecture decides
])
def test_kashima_needs_the_prefecture_or_the_town(text: str, status: str, city: object) -> None:
    v = jaden.validate(text)
    assert v.status == status
    if city:
        assert jaden.normalize(text).components.city == city
