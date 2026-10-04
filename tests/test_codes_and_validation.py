"""Unit tests for official JIS X 0401/0402 codes and Modulus 11 validation."""

import pytest
from jaden.models.codes import (
    calculate_modulus11_check_digit,
    PrefectureRecord,
    LocalGovernmentCode,
)
from jaden.data.loader import get_registry


def test_modulus11_check_digit_official_samples():
    # Official test vectors:
    # 01100 -> Sapporo-shi (Check 2 -> 011002)
    # 13101 -> Chiyoda-ku (Check 6 -> 131016)
    # 13102 -> Chuo-ku (Check 4 -> 131024)
    # 13103 -> Minato-ku (Check 2 -> 131032)
    # 13104 -> Shinjuku-ku (Check 1 -> 131041)
    # 26100 -> Kyoto-shi (Check 9 -> 261009)
    # 27100 -> Osaka-shi (Check 4 -> 271004)
    test_cases = [
        ("01100", "2"),
        ("13101", "6"),
        ("13102", "4"),
        ("13103", "2"),
        ("13104", "1"),
        ("26100", "9"),
        ("27100", "4"),
    ]
    for d5, expected_cd in test_cases:
        assert calculate_modulus11_check_digit(d5) == expected_cd


def test_local_government_code_validation():
    valid_code = LocalGovernmentCode("131016")
    assert valid_code.prefecture_code == "13"
    assert valid_code.municipality_base_code == "13101"
    assert valid_code.check_digit == "6"
    assert valid_code.is_valid_checksum() is True

    # Bad length
    with pytest.raises(ValueError):
        LocalGovernmentCode("13101")

    # Bad digits
    with pytest.raises(ValueError):
        LocalGovernmentCode("13101A")


def test_prefecture_records_jis_x_0401():
    reg = get_registry()
    prefs = reg.list_all_prefectures()
    assert len(prefs) == 47

    # Verify Hokkaido
    hokkaido = reg.get_prefecture_by_code("01")
    assert hokkaido is not None
    assert hokkaido.name == "北海道"
    assert hokkaido.stem == "北海"
    assert hokkaido.suffix == "道"

    # Verify Tokyo
    tokyo = reg.get_prefecture_by_code("13")
    assert tokyo is not None
    assert tokyo.name == "東京都"
    assert tokyo.stem == "東京"
    assert tokyo.suffix == "都"

    # Verify Okinawa
    okinawa = reg.get_prefecture_by_code("47")
    assert okinawa is not None
    assert okinawa.name == "沖縄県"
