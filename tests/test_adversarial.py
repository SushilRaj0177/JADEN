"""Adversarial validation suite designed specifically to challenge JADEN.

Covers the complete 19-payload adversarial benchmark matrix documented in AUDIT.md:
- TC-01: Embedded proper noun numerals (四日市市三番町)
- TC-02: Town stem numeral protection (一番町)
- TC-03: Town stem commercial arcade protection (一番街)
- TC-04: Ambiguous ward collision detection (中央区 across 11 jurisdictions)
- TC-05: Duplicate city collision detection (府中市 Tokyo vs Hiroshima)
- TC-06: Newly ingested duplicate city detection (伊達市 Hokkaido vs Fukushima)
- TC-07: Building names with numbers and floor tags (第1森タワー50F)
- TC-08: Bare room unit extraction (田町タワー 301)
- TC-09: Kyoto street with cardinal character (東洞院 in 御池通東洞院東入)
- TC-10: Kyoto street with cardinal character (下立売 in 新町通下立売上る)
- TC-11: Hokkaido Jo-Chome grid with omitted prefecture
- TC-12: Cadastral lot decomposition & Oaza/Koaza (大字南長野字幅下692-2)
- TC-13: Cadastral lot decomposition & Oaza/Koaza (大字鮫町字日出町1-1)
- TC-14: Formal Kanji lot with Edaban (六本木三丁目10番地の1)
- TC-15: Statutory Gaiku with landmark building (芝公園4丁目2番8号東京タワー)
- TC-16: Basement floor notation (地下1階)
- TC-17: Subsurface alphanumeric floor tag (B2F)
- TC-18: Gibberish input validation rejection (ランダムな文字列12345)
- TC-19: Foreign non-Japanese input validation rejection (アメリカ合衆国ニューヨーク市)
"""

import pytest
from jaden.engine import AddressNormalizer


@pytest.fixture
def normalizer():
    return AddressNormalizer()


def test_adversarial_tc01_yokkaichi_sanbancho(normalizer):
    """TC-01: Verifies that proper nouns with embedded numbers are not corrupted."""
    res = normalizer.normalize("三重県四日市市三番町1-2")
    assert res.components.prefecture == "三重県"
    assert res.components.city == "四日市市"
    assert res.components.town == "三番町"
    assert res.components.ban == 1
    assert res.components.go == 2


def test_adversarial_tc02_ichibancho(normalizer):
    """TC-02: Verifies that '一番町' in Chiyoda-ku is preserved."""
    res = normalizer.normalize("東京都千代田区一番町1-1")
    assert res.components.town == "一番町"
    assert res.components.ban == 1
    assert res.components.go == 1


def test_adversarial_tc03_ichibangai(normalizer):
    """TC-03: Verifies that '一番街' is preserved and NOT corrupted to '1番 街'."""
    res = normalizer.normalize("東京都港区一番街1-1")
    assert res.components.town == "一番街"
    assert res.components.ban == 1
    assert res.components.go == 1


def test_adversarial_tc04_ambiguous_chuo_ku(normalizer):
    """TC-04: Verifies that ambiguous '中央区' returns is_ambiguous=True without guessing."""
    res = normalizer.normalize("中央区銀座4-1-2")
    assert res.components.is_ambiguous is True
    assert len(res.components.ambiguous_candidates) == 11
    assert res.components.city == "中央区"
    assert res.components.town == "銀座"
    assert res.components.chome == 4
    assert res.components.ban == 1
    assert res.components.go == 2
    assert res.confidence_score <= 0.60


def test_adversarial_tc05_ambiguous_fuchu_shi(normalizer):
    """TC-05: Verifies that duplicate city '府中市' returns is_ambiguous=True."""
    res = normalizer.normalize("府中市宮西町2-24")
    assert res.components.is_ambiguous is True
    assert len(res.components.ambiguous_candidates) == 2
    assert "東京都府中市 (132063)" in res.components.ambiguous_candidates
    assert "広島県府中市 (342084)" in res.components.ambiguous_candidates
    assert res.components.city == "府中市"
    assert res.components.town == "宮西町"
    assert res.components.ban == 2
    assert res.components.go == 24
    assert res.confidence_score <= 0.60


def test_adversarial_tc06_ambiguous_date_shi(normalizer):
    """TC-06: Verifies that duplicate city '伊達市' returns is_ambiguous=True."""
    res = normalizer.normalize("伊達市鹿島町20-1")
    assert res.components.is_ambiguous is True
    assert len(res.components.ambiguous_candidates) == 2
    assert "北海道伊達市 (012335)" in res.components.ambiguous_candidates
    assert "福島県伊達市 (072133)" in res.components.ambiguous_candidates
    assert res.components.city == "伊達市"
    assert res.components.town == "鹿島町"
    assert res.components.ban == 20
    assert res.components.go == 1
    assert res.confidence_score <= 0.60


def test_adversarial_tc07_building_with_number(normalizer):
    """TC-07: Verifies that building names containing numbers are preserved."""
    res = normalizer.normalize("東京都港区六本木6-10-1第1森タワー50F")
    assert res.components.chome == 6
    assert res.components.ban == 10
    assert res.components.go == 1
    assert res.components.building == "第1森タワー"
    assert res.components.floor == "50F"


def test_adversarial_tc08_bare_room_number(normalizer):
    """TC-08: Verifies that bare room numbers without '号室' are extracted."""
    res = normalizer.normalize("東京都港区芝浦3-1-1 田町タワー 301")
    assert res.components.building == "田町タワー"
    assert res.components.unit == "301"


def test_adversarial_tc09_kyoto_higashinotoin(normalizer):
    """TC-09: Verifies that Kyoto street '東洞院' with cardinal character parses cleanly."""
    res = normalizer.normalize("京都府中京区御池通東洞院東入笹屋町436")
    assert res.components.kyoto_direction is not None
    assert res.components.kyoto_direction.street_1 == "御池通"
    assert res.components.kyoto_direction.street_2 == "東洞院"
    assert res.components.kyoto_direction.direction == "東入"
    assert res.components.kyoto_direction.cardinal == "east"
    assert res.components.town == "笹屋町"
    assert res.components.banchi == 436


def test_adversarial_tc10_kyoto_shimotachuri(normalizer):
    """TC-10: Verifies that Kyoto street '下立売' with cardinal character parses cleanly."""
    res = normalizer.normalize("京都府京都市上京区新町通下立売上る薮ノ内町")
    assert res.components.kyoto_direction is not None
    assert res.components.kyoto_direction.street_1 == "新町通"
    assert res.components.kyoto_direction.street_2 == "下立売"
    assert res.components.kyoto_direction.direction == "上る"
    assert res.components.kyoto_direction.cardinal == "north"
    assert res.components.town == "薮ノ内町"


def test_adversarial_tc11_hokkaido_grid_omitted_prefecture(normalizer):
    """TC-11: Verifies that Hokkaido Jo-Chome grid resolves even when prefecture is omitted."""
    res = normalizer.normalize("札幌市中央区北1条西2丁目1番地")
    assert res.components.prefecture == "北海道"
    assert res.components.prefecture_inferred is True
    assert res.components.city == "札幌市"
    assert res.components.ward == "中央区"
    assert res.components.hokkaido_grid is not None
    assert res.components.hokkaido_grid.jo == 1
    assert res.components.hokkaido_grid.chome == 2
    assert res.components.banchi == 1


def test_adversarial_tc12_chiban_nagano_oaza_koaza(normalizer):
    """TC-12: Verifies that rural cadastral lot numbers parse as banchi/edaban, NOT ban/go."""
    res = normalizer.normalize("長野県長野市大字南長野字幅下692-2")
    assert res.components.oaza == "南長野"
    assert res.components.koaza == "幅下"
    assert res.components.banchi == 692
    assert res.components.edaban == 2
    assert res.components.ban is None
    assert res.components.go is None
    assert res.components.address_regime == "chiban"


def test_adversarial_tc13_chiban_hachinohe_aza(normalizer):
    """TC-13: Verifies Oaza/Koaza segmentation in Aomori Hachinohe."""
    res = normalizer.normalize("青森県八戸市大字鮫町字日出町1-1")
    assert res.components.oaza == "鮫町"
    assert res.components.koaza == "日出町"
    assert res.components.banchi == 1
    assert res.components.edaban == 1
    assert res.components.ban is None
    assert res.components.go is None
    assert res.components.address_regime == "chiban"


def test_adversarial_tc14_kanji_banchi_edaban(normalizer):
    """TC-14: Verifies formal Kanji numeral lot with Edaban."""
    res = normalizer.normalize("東京都港区六本木三丁目10番地の1")
    assert res.components.chome == 3
    assert res.components.banchi == 10
    assert res.components.edaban == 1
    assert res.components.address_regime == "chiban"


def test_adversarial_tc15_kanji_chome_ban_go_tokyo_tower(normalizer):
    """TC-15: Verifies residential Gaiku with landmark building."""
    res = normalizer.normalize("東京都港区芝公園4丁目2番8号東京タワー")
    assert res.components.town == "芝公園"
    assert res.components.chome == 4
    assert res.components.ban == 2
    assert res.components.go == 8
    assert res.components.building == "東京タワー"
    assert res.components.address_regime == "gaiku_hoshiki"


def test_adversarial_tc16_basement_floor(normalizer):
    """TC-16: Verifies that basement floor '地下1階' is extracted."""
    res = normalizer.normalize("大阪府大阪市北区梅田3丁目1番1号JR大阪駅地下1階")
    assert res.components.floor == "地下1階"


def test_adversarial_tc17_subsurface_floor_b2f(normalizer):
    """TC-17: Verifies that alphanumeric basement tag 'B2F' is extracted."""
    res = normalizer.normalize("東京都千代田区大手町1-1-1大手町ビルB2F")
    assert res.components.floor == "B2F"


def test_adversarial_tc18_random_gibberish_rejected(normalizer):
    """TC-18: Verifies that pure gibberish is rejected with confidence 0.0."""
    res = normalizer.normalize("ランダムな文字列12345")
    assert res.confidence_score == 0.0
    assert res.components.prefecture is None
    assert res.components.city is None


def test_adversarial_tc19_foreign_address_rejected(normalizer):
    """TC-19: Verifies that foreign non-Japanese addresses are rejected with confidence 0.0."""
    res = normalizer.normalize("アメリカ合衆国ニューヨーク市")
    assert res.confidence_score == 0.0
    assert res.components.prefecture is None
    assert res.components.city is None
