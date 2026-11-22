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


# B6: town names written with 壱 / a 壱丁目 inside a building name
@pytest.mark.parametrize("text, canonical, building", [
    ("埼玉県上尾市壱丁目北24-17", "埼玉県上尾市壱丁目北24番17号", None),
    ("埼玉県上尾市壱丁目北24-17壱丁目ビル303", "埼玉県上尾市壱丁目北24番17号 壱丁目ビル 303", "壱丁目ビル"),
])
def test_ichi_chome_town_names(text: str, canonical: str, building: object) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical and res.components.building == building
    assert jaden.validate(text).verification_level == "town"


# B7: Sapporo grid followed by 番 and a lot
def test_sapporo_grid_with_ban_and_hyphen() -> None:
    c = jaden.normalize("北海道札幌市北区北29条西4丁目2番1-158").components
    assert (c.town, c.ban, c.go, c.unit) == (None, 2, 1, "158")


# B8: a town whose name holds a number, without the municipality
def test_furumachi_without_the_municipality() -> None:
    res = jaden.normalize("古町通6番町976")
    assert res.canonical == "新潟県新潟市中央区古町通六番町976番"
    assert res.components.building is None and res.components.unit is None


# B9-B11: resolver guards
def test_resolver_does_not_answer_text_without_numbers() -> None:
    for text in ("大泉町立北小学校", "南部町"):
        assert not jaden.resolve(text).answered


def test_tokyo_does_not_mention_kyoto() -> None:
    from jaden.resolve import mentions_prefecture
    assert not mentions_prefecture("京都府", "東京都立第一高校")
    assert mentions_prefecture("東京都", "東京都立第一高校")
    assert mentions_prefecture("京都府", "京都市立高校")


def test_an_answer_is_always_in_its_candidate_set() -> None:
    r = jaden.resolve("下伊那郡喬木村1396-2")
    assert r.answered and r.lg_code in r.candidate_set


# B12: an address and its canonical form get the same key
def test_dedupe_and_compare_agree_on_chome_ban() -> None:
    pair = ["埼玉県北本市本町6-232", "埼玉県北本市本町6丁目232番"]
    assert jaden.find_duplicates(pair) == [1, 1]
    assert jaden.compare(*pair).verdict == "same"


# B13: rooms with letters, wings, kanji floors
B = "東京都港区芝公園4-2-8"


def test_lettered_rooms_are_different_flats() -> None:
    assert jaden.find_duplicates([B + " A-302", B + " B-302", B]) == [1, 2, 3]
    assert jaden.compare(B + " A棟101", B + " B棟101").verdict != "same"
    assert jaden.compare(B + " 302号室", B + "-302").verdict == "same"


@pytest.mark.parametrize("tail, unit", [("A-302", "A-302"), ("302-A", "302-A"), ("2-302", "2-302"), (" 1", "1")])
def test_rooms_on_their_own(tail: str, unit: str) -> None:
    sep = "" if tail.startswith(" ") else " "
    c = jaden.normalize(B + sep + tail).components
    assert c.unit == unit and c.building is None


def test_kanji_floor() -> None:
    assert jaden.normalize(B + " 三階").components.floor == "3階"


def test_two_floors_stay_in_the_building() -> None:
    c = jaden.normalize(B + " 百道ふれあい館 2階・3階").components
    assert c.floor is None and "2階・3階" in (c.building or "")


# B14, B21-B23: canonical and hyphen forms are fixed points
@pytest.mark.parametrize("text", ["小中野3-9-26", "南3条東1-2-1", "宮城野2-4-1", "静岡県中央区日本橋兜町15-18"])
def test_unresolved_or_contradicted_input_is_returned_as_written(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == res.input_sanitized
    assert jaden.validate(res.canonical).status == jaden.validate(text).status


@pytest.mark.parametrize("text", [
    "千葉県市原市万田野732番地6", "福井県大野市春日三丁目１７１８", "沖縄県宜野湾市宇地泊１丁目20番7号",
    "北海道札幌市中央区南6条西11丁目1284番地4", "福井県勝山市片瀬第１５号２２番地", "熊本県八代市田中北町7号1番",
    "宮城県石巻市井内字三番113-2", "神奈川県茅ヶ崎市甘沼2723階", "宮崎県日南市大堂津1-13-16-1",
])
def test_canonical_and_hyphen_forms_read_back(text: str) -> None:
    res = jaden.normalize(text)
    assert jaden.normalize(res.canonical).canonical == res.canonical
    assert jaden.normalize(res.format("hyphen")).canonical == res.canonical
    assert jaden.match_key(text) == jaden.match_key(res.canonical)


# B15: offline geocoding follows validation
@pytest.mark.parametrize("text", ["東京都港区芝公園9-2-8", "東京都港区芝公園0-0-0", "〒100-0001 東京都港区芝公園4-2-8"])
def test_offline_geocoding_does_not_succeed_for_rejected_addresses(text: str) -> None:
    g = jaden.geocode(text, provider="offline")
    assert g.status == "NO_MATCH" and g.metadata["validation"] == "MALFORMED"


# B16, B17: extraction
def test_a_phone_number_is_not_a_postal_code() -> None:
    found = jaden.extract_addresses("電話03-1234-5678 東京都港区芝公園4-2-8")
    assert [e.text for e in found] == ["東京都港区芝公園4-2-8"]


@pytest.mark.parametrize("text", ["本社：東京都港区芝公園4-2-8 支社：大阪府大阪市北区梅田3-1-1",
                                  "東京都港区芝公園4-2-8と大阪府大阪市北区梅田3-1-1",
                                  "旧住所：東京都港区芝公園4-2-8→新住所:大阪府大阪市北区梅田3-1-1"])
def test_two_addresses_are_two_spans(text: str) -> None:
    assert [e.text for e in jaden.extract_addresses(text)] == ["東京都港区芝公園4-2-8", "大阪府大阪市北区梅田3-1-1"]


def test_normalize_stops_at_a_second_address_but_not_at_a_building_named_after_a_prefecture() -> None:
    res = jaden.normalize("東京都港区芝公園4-2-8 支社：大阪府大阪市北区梅田3-1-1")
    assert res.canonical == "東京都港区芝公園4丁目2番8号" and res.components.building is None
    assert jaden.normalize("東京都新宿区西新宿2-8-1東京都庁 第一本庁舎").components.building == "東京都庁 第一本庁舎"


# B18: the romaji table is published only once complete (checked by many threads at once)
def test_romaji_under_threads() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from jaden.romaji import _index
    _index()._towns.clear()
    inputs = ["7-2 Horencho, Nara-shi, Nara", "4-2-8 Shibakoen, Minato-ku, Tokyo"] * 200
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda t: jaden.normalize(t).canonical, inputs))
    assert set(results) == {"奈良県奈良市法蓮町7番2号", "東京都港区芝公園4丁目2番8号"}


# B19: a romaji town the registry does not hold
def test_unmatched_romaji_town_stays_in_place() -> None:
    res = jaden.normalize("158-2 Arata Kamikomata, Hirakawa-shi, Aomori")
    assert res.canonical == "青森県平川市Arata Kamikomata158番2号"
    assert jaden.validate("158-2 Arata Kamikomata, Hirakawa-shi, Aomori").verification_level == "municipality"
