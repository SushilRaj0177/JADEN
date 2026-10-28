"""Tests for town-level verification against the MLIT / Japan Post gazetteer (v0.2)."""

import gzip
import json

import pytest

import jaden
from jaden.core.townkey import town_key, split_chome
from jaden.data.gazetteer import Gazetteer, get_gazetteer
from jaden.engine import AddressNormalizer, extract_postal_code
from jaden.models.validation import ValidationStatus


@pytest.fixture(scope="module")
def gaz() -> Gazetteer:
    g = get_gazetteer()
    assert g.available, "bundled towns.tsv.gz is missing"
    return g


# --------------------------------------------------------------------- keys
@pytest.mark.parametrize("a, b", [
    ("霞が関", "霞ヶ関"), ("霞が関", "霞ケ関"), ("一の宮", "一ノ宮"),
    ("北一条西", "北1条西"), ("大字南長野", "南長野"), ("芝公園", "芝 公園"),
])
def test_town_key_folds_spelling_variants(a, b):
    assert town_key(a) == town_key(b)


def test_town_key_keeps_distinct_names_apart():
    assert town_key("六本木") != town_key("八本木")
    assert town_key("南長野") != town_key("北長野")


def test_split_chome():
    assert split_chome("芝公園四丁目") == ("芝公園", 4)
    assert split_chome("北一条西十二丁目") == ("北一条西", 12)
    assert split_chome("大字南長野") == ("大字南長野", None)


# ---------------------------------------------------------------- gazetteer
def test_gazetteer_town_and_chomes(gaz):
    m = gaz.match_town("131032", "芝公園")
    assert m is not None and m.exact
    assert m.entry.chomes == (1, 2, 3, 4)
    assert m.entry.kana == "シバコウエン"
    assert m.entry.romaji == "SHIBAKOEN"


def test_gazetteer_prefix_match_leaves_koaza(gaz):
    m = gaz.match_town("202011", "大字南長野字幅下")
    assert m is not None and not m.exact
    assert m.entry.name == "大字南長野"
    assert "大字南長野字幅下"[m.consumed:] == "字幅下"


def test_gazetteer_postal_lookup(gaz):
    recs = gaz.postal_records("105-0011")
    assert [(r.lg_code, r.town) for r in recs] == [("131032", "芝公園")]
    assert gaz.postal_codes_for("131032", "芝公園") == ["1050011"]


def test_gazetteer_provenance_records_sources(gaz):
    prov = gaz.provenance()
    assert prov["towns"]["records"] > 180_000
    assert "国土交通省" in prov["towns"]["attribution"]
    assert all(len(s["sha256"]) == 64 for s in prov["sources"])
    assert any("japanpost" in s["url"] for s in prov["sources"])


def test_bundled_town_codes_all_exist_in_mic_registry(gaz):
    registry = jaden.get_registry()
    with gzip.open(gaz.data_dir / "towns.tsv.gz", "rt", encoding="utf-8") as f:
        next(f)
        codes = {line.split("\t", 1)[0] for line in f}
    missing = [c for c in codes if registry.get_municipality_by_code(c) is None]
    assert missing == []


# ------------------------------------------------------- ambiguity resolution
@pytest.mark.parametrize("address, lg_code", [
    ("港区芝公園4-2-8", "131032"),           # 港区: Tokyo, Nagoya, Osaka
    ("中央区銀座4-6-16", "131024"),          # 中央区: 11 cities
    ("府中市宮西町2-24", "132063"),          # 府中市: Tokyo, Hiroshima
    ("伊達市鹿島町20-1", "012335"),          # 伊達市: Hokkaido, Fukushima
    ("大阪府北区梅田1-1-1", "271276"),        # 北区 inside Osaka prefecture: Osaka, Sakai
    ("中央区北1条西2丁目", "011011"),          # Sapporo grid
    ("寺町通御池上る上本能寺前町488", "261041"),  # Kyoto, ward omitted
])
def test_town_resolves_ambiguous_municipality(address, lg_code):
    res = jaden.normalize(address)
    assert res.components.is_ambiguous is False
    assert res.components.lg_code == lg_code
    assert res.components.municipality_inferred is True
    assert jaden.validate(address).status == ValidationStatus.ACCEPTED.value


def test_ambiguity_kept_when_town_cannot_decide():
    # No town at all: nothing to decide by
    val = jaden.validate("府中市1-1")
    assert val.status == ValidationStatus.AMBIGUOUS.value
    assert len(val.ambiguous_candidates) == 2


def test_town_alone_narrows_but_does_not_guess():
    res = jaden.normalize("銀座4-6-16")
    assert res.components.is_ambiguous is True
    assert 1 < len(res.components.ambiguous_candidates) <= 30
    assert any("131024" in c for c in res.components.ambiguous_candidates)


def test_town_unique_in_japan_is_deduced():
    res = jaden.normalize("芝公園4-2-8")
    assert res.components.lg_code == "131032"
    assert res.components.prefecture_inferred is True
    assert any("only match in Japan" in n for n in res.notes)


def test_prefecture_with_municipality_omitted():
    res = jaden.normalize("東京都六本木6-10-1")
    assert res.components.lg_code == "131032"
    assert res.components.prefecture_inferred is False


def test_not_an_address_still_rejected():
    assert jaden.validate("東京タワー").status != ValidationStatus.ACCEPTED.value
    assert jaden.validate("〒106-0032").status != ValidationStatus.ACCEPTED.value
    assert jaden.validate("hello world").status == ValidationStatus.MALFORMED.value


# --------------------------------------------------------------- verification
def test_nonexistent_chome_is_malformed():
    val = jaden.validate("東京都港区芝公園9-2-8")
    assert val.status == ValidationStatus.MALFORMED.value
    assert "1–4丁目" in val.message


def test_unregistered_town_is_a_warning_not_an_error():
    val = jaden.validate("東京都港区存在しない町1-1")
    assert val.status == ValidationStatus.ACCEPTED.value
    assert val.verification_level == "municipality"
    assert any("not registered" in w for w in val.warnings)


def test_strict_mode_requires_town():
    assert jaden.validate("東京都港区存在しない町1-1", strict=True).status == ValidationStatus.UNSUPPORTED.value
    assert jaden.validate("東京都港区芝公園4-2-8", strict=True).status == ValidationStatus.ACCEPTED.value


def test_verification_levels():
    assert jaden.validate("東京都港区芝公園4-2-8").verification_level == "chome"
    assert jaden.validate("長野県長野市大字南長野字幅下692-2").verification_level == "town"


def test_registered_spelling_is_canonical():
    assert jaden.normalize("東京都千代田区霞ヶ関1-2-1").canonical == "東京都千代田区霞が関1丁目2番1号"


# ---------------------------------------------------------------- postal code
@pytest.mark.parametrize("raw, expected", [
    ("〒105-0011 東京都港区芝公園4-2-8", "105-0011"),
    ("〒1050011東京都港区芝公園4-2-8", "105-0011"),
    ("105-0011 東京都港区芝公園4-2-8", "105-0011"),
    ("東京都港区芝公園4-2-8 〒105-0011", "105-0011"),
    ("東京都港区芝公園4-2-8", None),
    ("東京都港区芝公園4-2-8-105", None),
])
def test_extract_postal_code(raw, expected):
    assert extract_postal_code(raw) == expected


def test_postal_code_resolves_municipality():
    res = jaden.normalize("〒105-0011 港区芝公園4-2-8")
    assert res.components.lg_code == "131032"
    assert res.components.postal_code_consistent is True


def test_wrong_postal_code_is_malformed():
    val = jaden.validate("〒100-0001 東京都港区芝公園4-2-8")
    assert val.status == ValidationStatus.MALFORMED.value
    assert "千代田区" in val.message


def test_postal_code_filled_in_when_unique():
    assert jaden.normalize("東京都港区芝公園4-2-8").components.postal_code == "105-0011"


# ------------------------------------------------------- structure from data
def test_chome_town_reads_two_numbers_as_chome_ban():
    c = jaden.normalize("東京都港区六本木6-10").components
    assert (c.chome, c.ban, c.go) == (6, 10, None)


def test_registered_oaza_is_cadastral():
    c = jaden.normalize("長野市南長野692-2").components
    assert (c.banchi, c.edaban, c.address_regime) == (692, 2, "chiban")


def test_obihiro_grid_verified():
    res = jaden.normalize("北海道帯広市西5条南10丁目")
    assert res.components.town_verified is True
    assert res.components.chome == 10
    assert res.components.chome_verified is True


# --------------------------------------------------------- readings & location
def test_kana_and_romaji():
    res = jaden.normalize("東京都港区芝公園4-2-8")
    assert res.kana == "トウキョウトミナトクシバコウエン"
    assert res.romaji == "4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011"


def test_romaji_orders_ward_before_city():
    res = jaden.normalize("福岡市中央区天神1-8-1")
    assert res.romaji == "1-8-1 Tenjin, Chuo-ku, Fukuoka-shi, Fukuoka 810-0001"


def test_county_romaji_uses_its_own_municipality():
    # Postal codes shared between neighbouring municipalities must not leak readings
    res = jaden.normalize("東京都西多摩郡日の出町平井2780")
    assert res.romaji.endswith("Hinode-machi, Nishitama-gun, Tokyo 190-0182")


def test_offline_location():
    res = jaden.normalize("東京都港区芝公園4-2-8")
    assert res.location_level in ("chome", "block")
    assert abs(res.latitude - 35.6586) < 0.01 and abs(res.longitude - 139.7454) < 0.01


def test_offline_geocoder():
    r = jaden.geocode("東京都港区芝公園4-2-8", provider="offline")
    assert r.status == "SUCCESS"
    assert r.provider == "offline"
    assert r.metadata["machiaza_id"] == "131030002004"
    assert jaden.geocode("府中市1-1", provider="offline").status == "AMBIGUOUS"
    assert jaden.geocode("東京都港区存在しない町1-1", provider="offline").status == "NO_MATCH"


# ------------------------------------------------------------------- toggles
def test_gazetteer_can_be_disabled():
    engine = AddressNormalizer(use_gazetteer=False)
    res = engine.normalize("港区芝公園4-2-8")
    assert res.components.is_ambiguous is True
    assert res.components.town_verified is None
    assert res.kana is None


def test_block_level_data(tmp_path, monkeypatch):
    """Block points installed by `jaden data fetch-blocks` are used for location and regime."""
    blocks = tmp_path / "jaden" / "blocks"
    blocks.mkdir(parents=True)
    with gzip.open(blocks / "13.tsv.gz", "wt", encoding="utf-8") as f:
        f.write("lg_code\tkey\tchome\tblock\tlat\tlon\tjukyo\n")
        f.write(f"131032\t{town_key('芝公園')}\t4\t2\t35.658648\t139.745467\t1\n")
        f.write(f"131016\t{town_key('一番町')}\t\t1\t35.687135\t139.743964\t0\n")
    from jaden.core.townkey import TOWN_KEY_VERSION
    (blocks / "13.json").write_text(json.dumps({"town_key_version": TOWN_KEY_VERSION}), encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))

    engine = AddressNormalizer(gazetteer=Gazetteer())
    res = engine.normalize("東京都港区芝公園4-2-8")
    assert res.location_level == "block"
    assert res.components.block_verified is True
    assert res.latitude == 35.658648

    # The block data says 一番町 1 is a 地番 block
    c = engine.normalize("東京都千代田区一番町1").components
    assert (c.banchi, c.ban, c.address_regime) == (1, None, "chiban")

    assert engine.normalize("東京都港区芝公園4-99-1").components.block_verified is False
