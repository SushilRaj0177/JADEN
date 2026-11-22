"""Bugs found by the full audit of 22 November 2026 (docs/CHECKLIST.md), each pinned by its reproducing input."""

import time

import pytest

import jaden


# B1: reverse geocoding near the poles never returned
@pytest.mark.parametrize("lat, lon", [(90, 0), (-90, 0), (88, 0), (0, 0), (60, 10)])
def test_reverse_geocoding_far_from_japan_returns_at_once(lat: float, lon: float) -> None:
    start = time.perf_counter()
    assert jaden.reverse_geocode(lat, lon) == []
    assert time.perf_counter() - start < 1.0


def test_reverse_geocoding_still_reaches_the_edges_of_japan() -> None:
    assert jaden.reverse_geocode(24.4667, 153.9833)[0].address.startswith("東京都小笠原村")   # 南鳥島
    assert jaden.reverse_geocode(45.52, 141.94)[0].address.startswith("北海道稚内市")


@pytest.mark.parametrize("call", [lambda: jaden.reverse_geocode(35.0, 135.0, limit=0),
                                  lambda: jaden.suggest("東京都港区", limit=0)])
def test_limits_below_one_are_rejected(call) -> None:
    with pytest.raises(ValueError):
        call()


# B27: inputs that are not text
@pytest.mark.parametrize("value", [123, float("nan"), None])
def test_non_text_input_gives_an_empty_result_not_an_exception(value: object) -> None:
    assert jaden.validate(value).status == "MALFORMED"   # type: ignore[arg-type]
    assert jaden.match_key(value) is None                # type: ignore[arg-type]
    assert not jaden.resolve(value).answered             # type: ignore[arg-type]
    assert jaden.extract_addresses(value) == []          # type: ignore[arg-type]
    jaden.normalize(value)                               # type: ignore[arg-type]


def test_postal_lookup_accepts_an_integer() -> None:
    assert jaden.lookup_postal(1050011)[0].town == "芝公園"   # type: ignore[arg-type]


# B2: a contradicting postal code written with another dash
@pytest.mark.parametrize("dash", ["―", "‐", "–", "—", "-", "－"])
def test_contradicting_postal_code_is_caught_with_any_dash(dash: str) -> None:
    assert jaden.validate(f"〒100{dash}0001 東京都港区芝公園4-2-8").status == "MALFORMED"


# B3: postal codes without a hyphen or with spaces
@pytest.mark.parametrize("text", ["1050011 東京都港区芝公園4-2-8", "〒 105 - 0011 東京都港区芝公園4-2-8",
                                  "〒105 0011 東京都港区芝公園4-2-8", "東京都港区芝公園4-2-8 1050011"])
def test_postal_code_forms_are_read_and_removed(text: str) -> None:
    res = jaden.normalize(text)
    assert jaden.validate(text).status == "ACCEPTED"
    assert res.canonical == "東京都港区芝公園4丁目2番8号"
    assert res.components.postal_code == "105-0011"


def test_seven_digits_glued_to_the_address_are_still_a_lot_number() -> None:
    assert jaden.normalize("東京都小平市小川町２丁目1987102").components.postal_code != "198-7102"


# B4, B5: number forms around 丁目 and 番地
@pytest.mark.parametrize("text, canonical", [
    ("東京都港区芝公園4丁目-2-8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目ー2ー8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目の2の8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目2の8番地", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目2-8番地", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4 - 2 - 8", "東京都港区芝公園4丁目2番8号"),
    ("石川県輪島市門前町赤神10の1番地", "石川県輪島市門前町赤神10番地の1"),
    ("奈良県吉野郡大淀町下渕887の2番地", "奈良県吉野郡大淀町下渕887番地の2"),
    ("奈良県吉野郡大淀町下渕887-2番地", "奈良県吉野郡大淀町下渕887番地の2"),
])
def test_number_forms(text: str, canonical: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical
    assert res.components.building is None


# B24: invisible and control characters
@pytest.mark.parametrize("text", ["東​京都港区芝公園4-2-8", "東京都港区芝公園4​-2-8", "東京都港区芝公園4­-2-8",
                                  "東京都港区芝公園4 -2-8", "東京都港区芝公園4\x00-2-8", "東京都港区芝公園4⁃2⁃8",
                                  "﻿東京都港区芝公園4-2-8"])
def test_invisible_characters_are_removed(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == "東京都港区芝公園4丁目2番8号"
    assert "\x00" not in res.canonical


# B25: a phone number after the address
@pytest.mark.parametrize("text", ["東京都港区芝公園4-2-8 TEL 03-1234-5678", "東京都港区芝公園4-2-8 電話：03(1234)5678",
                                  "東京都港区芝公園4-2-8 FAX:03-1234-5679"])
def test_a_trailing_phone_number_is_not_the_building(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == "東京都港区芝公園4丁目2番8号" and res.components.building is None
