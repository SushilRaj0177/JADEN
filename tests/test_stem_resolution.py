"""Tests for prefecture stem prefix collision prevention (Finding B-1).

Verifies that bare prefecture stems (e.g. 京都, 大阪, 愛知, 長野, 福島, 福岡, 広島, 宮城, 神奈川)
do not hijack municipal, county, or ward entities starting with identical prefixes.
"""

import pytest
from jaden import normalize, parse


def test_stem_collision_shiga_aichi_gun():
    """愛知郡愛荘町愛知川1 must resolve to Shiga Prefecture (254258), not Aichi Prefecture."""
    res = normalize("愛知郡愛荘町愛知川1")
    comp = res.components
    assert comp.prefecture == "滋賀県"
    assert comp.prefecture_code == "25"
    assert comp.county == "愛知郡"
    assert comp.city == "愛荘町"
    assert comp.lg_code == "254258"
    assert comp.town == "愛知川"
    assert comp.banchi == 1 or comp.ban == 1


def test_stem_collision_aichi_aichi_gun():
    """愛知郡東郷町 belongs to Aichi Prefecture (233021)."""
    res = normalize("愛知郡東郷町")
    comp = res.components
    assert comp.prefecture == "愛知県"
    assert comp.prefecture_code == "23"
    assert comp.county == "愛知郡"
    assert comp.city == "東郷町"
    assert comp.lg_code == "233021"


def test_stem_collision_fukushima_cho_hokkaido():
    """福島町 must resolve to Hokkaido (013323), not Fukushima Prefecture."""
    res = normalize("福島町")
    comp = res.components
    assert comp.prefecture == "北海道"
    assert comp.prefecture_code == "01"
    assert comp.city == "福島町"
    assert comp.lg_code == "013323"


def test_stem_collision_fukushima_ku_osaka():
    """福島区 must resolve to Osaka Prefecture (271039), not Fukushima Prefecture."""
    res = normalize("福島区")
    comp = res.components
    assert comp.prefecture == "大阪府"
    assert comp.prefecture_code == "27"
    assert comp.ward == "福島区"
    assert comp.lg_code == "271039"


def test_stem_collision_naganohara_gunma():
    """長野原町大字長野原1 must resolve to Gunma Prefecture (104248), not Nagano Prefecture."""
    res = normalize("長野原町大字長野原1")
    comp = res.components
    assert comp.prefecture == "群馬県"
    assert comp.prefecture_code == "10"
    assert comp.city == "長野原町"
    assert comp.lg_code == "104248"


def test_stem_collision_miyako_gun_fukuoka():
    """京都郡苅田町 must resolve to Fukuoka Prefecture (406210), not Kyoto Prefecture."""
    res = normalize("京都郡苅田町")
    comp = res.components
    assert comp.prefecture == "福岡県"
    assert comp.prefecture_code == "40"
    assert comp.county == "京都郡"
    assert comp.city == "苅田町"
    assert comp.lg_code == "406210"


def test_stem_collision_kyoto_city_intersection():
    """京都市中京区寺町通御池上る上本能寺前町488 must resolve to Kyoto (261041) with Kyoto clause."""
    res = normalize("京都市中京区寺町通御池上る上本能寺前町488")
    comp = res.components
    assert comp.prefecture == "京都府"
    assert comp.prefecture_code == "26"
    assert comp.city == "京都市"
    assert comp.ward == "中京区"
    assert comp.lg_code == "261041"
    assert comp.kyoto_direction is not None
    assert comp.kyoto_direction.raw_clause == "寺町通御池上る"
    assert comp.town == "上本能寺前町"
    assert comp.banchi == 488


def test_stem_collision_osaka_city():
    """大阪市北区梅田3-1-1 must resolve to Osaka City (271276)."""
    res = normalize("大阪市北区梅田3-1-1")
    comp = res.components
    assert comp.prefecture == "大阪府"
    assert comp.prefecture_code == "27"
    assert comp.city == "大阪市"
    assert comp.ward == "北区"
    assert comp.lg_code == "271276"
    assert comp.town == "梅田"


def test_stem_collision_hiroshima_city():
    """広島市中区基町10-52 must resolve to Hiroshima City (341011)."""
    res = normalize("広島市中区基町10-52")
    comp = res.components
    assert comp.prefecture == "広島県"
    assert comp.prefecture_code == "34"
    assert comp.city == "広島市"
    assert comp.ward == "中区"
    assert comp.lg_code == "341011"
    assert comp.town == "基町"


def test_stem_collision_fukuoka_city():
    """福岡市博多区博多駅中央街1-1 must resolve to Fukuoka City (401323)."""
    res = normalize("福岡市博多区博多駅中央街1-1")
    comp = res.components
    assert comp.prefecture == "福岡県"
    assert comp.prefecture_code == "40"
    assert comp.city == "福岡市"
    assert comp.ward == "博多区"
    assert comp.lg_code == "401323"


def test_stem_collision_kanagawa_ku():
    """神奈川区 must resolve to Yokohama Kanagawa-ku (141020)."""
    res = normalize("神奈川区")
    comp = res.components
    assert comp.prefecture == "神奈川県"
    assert comp.prefecture_code == "14"
    assert comp.ward == "神奈川区"
    assert comp.lg_code == "141020"


def test_stem_collision_miyagino_ku():
    """宮城野区 must resolve to Sendai Miyagino-ku (041025)."""
    res = normalize("宮城野区")
    comp = res.components
    assert comp.prefecture == "宮城県"
    assert comp.prefecture_code == "04"
    assert comp.ward == "宮城野区"
    assert comp.lg_code == "041025"


def test_stem_collision_explicit_prefecture_preserved():
    """Explicit prefecture inputs must continue resolving without regression."""
    res1 = normalize("滋賀県愛知郡愛荘町愛知川1")
    assert res1.components.prefecture == "滋賀県"
    assert res1.components.lg_code == "254258"

    res2 = normalize("愛知県愛知郡東郷町")
    assert res2.components.prefecture == "愛知県"
    assert res2.components.lg_code == "233021"

    res3 = normalize("京都府京都市中京区寺町通御池上る上本能寺前町488")
    assert res3.components.prefecture == "京都府"
    assert res3.components.lg_code == "261041"


def test_all_stem_colliding_entities_in_registry():
    """Data-driven verification across all 1,918 official municipalities.

    Dynamically iterates through every municipality name, ward name, and
    county-prefixed name that starts with any JIS X 0401 prefecture stem.
    Asserts that every entity either:
    1. Unambiguously resolves to its statutory prefecture and local government code, OR
    2. Correctly flags AMBIGUOUS with candidate list containing its legitimate statutory targets.
    """
    from jaden.data.loader import get_registry

    reg = get_registry()
    stems = {p.stem: p for p in reg.list_all_prefectures() if len(p.stem) >= 2}

    tested_count = 0
    for muni in reg._municipalities_by_code.values():
        targets = []
        if any(muni.name.startswith(s) for s in stems):
            targets.append((muni.name, muni))
        if muni.ward and any(muni.ward.startswith(s) for s in stems):
            targets.append((muni.ward, muni))
        if muni.county and any(f"{muni.county}{muni.name}".startswith(s) for s in stems):
            targets.append((f"{muni.county}{muni.name}", muni))

        for target_str, target_muni in targets:
            res = normalize(target_str)
            comp = res.components
            if comp.is_ambiguous:
                # Must list candidates and not crash or misattribute
                assert len(comp.ambiguous_candidates) > 1
                assert any(target_muni.lg_code in c for c in comp.ambiguous_candidates)
            else:
                assert comp.prefecture_code == target_muni.prefecture_code, (
                    f"Entity '{target_str}' ({target_muni.prefecture_name}) misattributed to "
                    f"'{comp.prefecture}' (prefecture_code={comp.prefecture_code})"
                )
                assert comp.lg_code == target_muni.lg_code, (
                    f"Entity '{target_str}' expected lg_code={target_muni.lg_code}, got {comp.lg_code}"
                )
            tested_count += 1

    assert tested_count > 50, f"Expected >50 stem-colliding entities, verified {tested_count}"

