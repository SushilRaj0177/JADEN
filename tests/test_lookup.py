"""Postal lookup, autocomplete and reverse geocoding."""

import json

import pytest

import jaden
from jaden.cli import main
from jaden.lookup import lookup_postal, reverse_geocode, suggest


# ------------------------------------------------------------------ postal
@pytest.mark.parametrize("code", ["105-0011", "1050011", "〒105-0011", "１０５－００１１"])
def test_lookup_postal_formats(code):
    (found,) = lookup_postal(code)
    assert found.postal_code == "105-0011"
    assert found.address == "東京都港区芝公園"
    assert (found.prefecture, found.municipality, found.town, found.lg_code) == ("東京都", "港区", "芝公園", "131032")
    assert found.kana == "トウキョウトミナトクシバコウエン"
    assert found.romaji == "Shibakoen, Minato-ku, Tokyo"


def test_lookup_postal_building_code_separates_town_and_building():
    (found,) = lookup_postal("106-6150")
    assert found.kind == "building"
    assert (found.town, found.building) == ("六本木", "六本木ヒルズ森タワー")
    assert found.address == "東京都港区六本木"


def test_lookup_postal_code_shared_by_two_municipalities():
    found = lookup_postal("498-0000")
    assert {p.address for p in found} == {"愛知県弥富市", "三重県桑名郡木曽岬町"}
    assert all(p.kind == "municipality" for p in found)


def test_lookup_postal_unknown_or_malformed():
    assert lookup_postal("999-9999") == []
    assert lookup_postal("12345") == []
    assert lookup_postal("") == []


# ----------------------------------------------------------------- suggest
def test_suggest_towns_by_prefix_and_by_reading():
    by_text = [s.text for s in suggest("東京都港区芝")]
    assert by_text[:4] == ["東京都港区芝", "東京都港区芝浦", "東京都港区芝公園", "東京都港区芝大門"]
    by_reading = [s.text for s in suggest("東京都港区しば")]
    assert set(by_text[:4]) == set(by_reading)


def test_suggest_chome_after_a_complete_town():
    found = suggest("東京都港区芝公園")
    assert [s.text for s in found] == [f"東京都港区芝公園{n}丁目" for n in (1, 2, 3, 4)]
    assert all(s.kind == "chome" and s.postal_code == "105-0011" for s in found)
    assert [s.text for s in suggest("東京都港区芝公園4")] == ["東京都港区芝公園4丁目"]


def test_suggest_municipalities():
    assert "東京都港区" in [s.text for s in suggest("東京都み")]
    assert [s.text for s in suggest("とうきょう")] == ["東京都"]
    assert {s.text for s in suggest("みなとく")} == {"東京都港区", "愛知県名古屋市港区", "大阪府大阪市港区"}
    wards = [s.text for s in suggest("京都市", limit=20)]
    assert len(wards) == 11 and all(w.startswith("京都府京都市") for w in wards)


def test_suggest_without_municipality():
    assert [s.text for s in suggest("港区芝公")] == ["東京都港区芝公園"]
    assert "東京都中央区銀座" in [s.text for s in suggest("銀座", limit=20)]
    assert [s.text for s in suggest("ろっぽんぎ")] == ["東京都港区六本木"]


def test_suggest_postal_prefix():
    found = suggest("105-00")
    assert found[0].kind == "postal" and found[0].postal_code == "105-0000"
    assert any(s.text == "東京都港区芝公園" and s.postal_code == "105-0011" for s in suggest("105-001"))


def test_suggest_limit_and_empty():
    assert len(suggest("東京都", limit=3)) == 3
    assert suggest("") == [] and suggest("   ") == []


def test_every_suggestion_is_a_valid_address_prefix():
    for s in suggest("東京都港区芝公園"):
        assert jaden.validate(s.text).status == "ACCEPTED"


# ----------------------------------------------------------------- reverse
def test_reverse_geocode_nearest_town():
    (hit,) = reverse_geocode(35.0116, 135.7681)
    assert hit.address == "京都府京都市中京区上本能寺前町"
    assert hit.lg_code == "261041" and hit.level == "town" and hit.distance_m < 50
    assert hit.postal_code == "604-0925"


def test_reverse_geocode_chome_and_limit():
    hits = reverse_geocode(43.0628, 141.3544, limit=3)
    assert hits[0].address == "北海道札幌市中央区北一条西2丁目" and hits[0].level == "chome"
    assert len(hits) == 3
    assert [h.distance_m for h in hits] == sorted(h.distance_m for h in hits)


def test_reverse_geocode_outside_japan_and_bad_input():
    assert reverse_geocode(30.0, 150.0) == []
    with pytest.raises(ValueError):
        reverse_geocode(95.0, 139.0)


def test_reverse_geocode_agrees_with_offline_geocoding():
    res = jaden.normalize("東京都港区芝公園4-2-8")
    (hit,) = reverse_geocode(res.latitude, res.longitude)
    assert hit.address == "東京都港区芝公園4丁目" and hit.distance_m < 1


# --------------------------------------------------------------------- CLI
def test_lookup_commands(capsys):
    assert main(["postal", "105-0011", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)[0]["address"] == "東京都港区芝公園"
    assert main(["postal", "999-9999"]) == 1
    capsys.readouterr()
    assert main(["suggest", "港区しば", "--limit", "2"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 2
    assert main(["reverse", "35.0116", "135.7681"]) == 0
    assert "上本能寺前町" in capsys.readouterr().out
