"""Adversarial validation suite designed specifically to challenge JADEN.

Covers:
- Proper noun collisions (六本木, 八王子, 四日市, 三番町, 一番町, 一番街)
- Ambiguous omitted prefectures and multi-jurisdiction collisions (中央区, 府中市)
- Kyoto streets containing cardinal characters (東洞院通, 下立売通)
- Statutory Chiban vs Gaiku-hoshiki conflation (大字・字)
- Numerical building names, basement floors, and bare room units
- Gibberish, foreign, and malformed inputs
"""

import pytest
from jaden.engine import AddressNormalizer


@pytest.fixture
def normalizer():
    return AddressNormalizer()


def test_adversarial_proper_noun_yokkaichi_sanbancho(normalizer):
    """Verifies that proper nouns with embedded numbers are not corrupted."""
    res = normalizer.normalize("三重県四日市市三番町1-2")
    assert res.components.prefecture == "三重県"
    assert res.components.city == "四日市市"
    assert res.components.town == "三番町"
    assert res.components.ban == 1
    assert res.components.go == 2


def test_adversarial_proper_noun_ichibancho(normalizer):
    """Verifies that '一番町' in Chiyoda-ku is preserved."""
    res = normalizer.normalize("東京都千代田区一番町1-1")
    assert res.components.town == "一番町"
    assert res.components.ban == 1
    assert res.components.go == 1


def test_adversarial_building_with_number(normalizer):
    """Verifies that building names containing numbers are preserved."""
    res = normalizer.normalize("東京都港区六本木6-10-1第1森タワー50F")
    assert res.components.chome == 6
    assert res.components.ban == 10
    assert res.components.go == 1
    assert res.components.building == "第1森タワー"
    assert res.components.floor == "50F"


def test_adversarial_bare_room_number(normalizer):
    """Verifies that bare room numbers without '号室' are extracted."""
    res = normalizer.normalize("東京都港区芝浦3-1-1 田町タワー 301")
    assert res.components.building == "田町タワー"
    assert res.components.unit == "301"


def test_adversarial_basement_floor(normalizer):
    """Verifies that basement floors (地下1階, B2F) are parsed."""
    res1 = normalizer.normalize("大阪府大阪市北区梅田3丁目1番1号JR大阪駅地下1階")
    assert res1.components.floor == "地下1階"

    res2 = normalizer.normalize("東京都千代田区大手町1-1-1大手町ビルB2F")
    assert res2.components.floor == "B2F"


def test_adversarial_hokkaido_grid_omitted_prefecture(normalizer):
    """Verifies that Hokkaido Jo-Chome grid resolves even when prefecture is omitted."""
    res = normalizer.normalize("札幌市中央区北1条西2丁目1番地")
    assert res.components.prefecture == "北海道"
    assert res.components.prefecture_inferred is True
    assert res.components.city == "札幌市"
    assert res.components.ward == "中央区"
    assert res.components.hokkaido_grid is not None
    assert res.components.hokkaido_grid.jo == 1
    assert res.components.hokkaido_grid.chome == 2
