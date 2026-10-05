"""Systematic coverage test suite across all 47 Japanese prefectures (JIS X 0401).

Asserts full decomposition: prefecture, city, ward, town/oaza/koaza, and block numbers
across all 47 prefectural administrative headquarters.
"""

import pytest
from jaden.engine import AddressNormalizer

# Ground-truth test addresses covering all 47 prefectures with full expected decomposition
# Ground-truth test addresses covering all 47 prefectures with full expected decomposition
# Format: (code, pref, address_str, expected_city, expected_ward, expected_town, chome, ban, go, banchi, edaban)
PREFECTURE_TEST_CASES = [
    ("01", "北海道", "北海道札幌市中央区北1条西2丁目", "札幌市", "中央区", None, 2, None, None, None, None),
    ("02", "青森県", "青森県青森市新町1-1", "青森市", None, "新町", None, 1, 1, None, None),
    ("03", "岩手県", "岩手県盛岡市内丸1-1", "盛岡市", None, "内丸", None, 1, 1, None, None),
    ("04", "宮城県", "宮城県仙台市青葉区本町3-8-1", "仙台市", "青葉区", "本町", 3, 8, 1, None, None),
    ("05", "秋田県", "秋田県秋田市山王4-1-1", "秋田市", None, "山王", 4, 1, 1, None, None),
    ("06", "山形県", "山形県山形市松波2-8-1", "山形市", None, "松波", 2, 8, 1, None, None),
    ("07", "福島県", "福島県福島市杉妻町2-16", "福島市", None, "杉妻町", None, 2, 16, None, None),
    ("08", "茨城県", "茨城県水戸市笠原町978-6", "水戸市", None, "笠原町", None, 978, 6, None, None),
    ("09", "栃木県", "栃木県宇都宮市塙田1-1-20", "宇都宮市", None, "塙田", 1, 1, 20, None, None),
    ("10", "群馬県", "群馬県前橋市大手町1-1-1", "前橋市", None, "大手町", 1, 1, 1, None, None),
    ("11", "埼玉県", "埼玉県さいたま市浦和区高砂3-15-1", "さいたま市", "浦和区", "高砂", 3, 15, 1, None, None),
    ("12", "千葉県", "千葉県千葉市中央区市場町1-1", "千葉市", "中央区", "市場町", None, 1, 1, None, None),
    ("13", "東京都", "東京都新宿区西新宿2丁目8番1号", "新宿区", None, "西新宿", 2, 8, 1, None, None),
    ("14", "神奈川県", "神奈川県横浜市中区日本大通1", "横浜市", "中区", "日本大通", None, 1, None, None, None),
    ("15", "新潟県", "新潟県新潟市中央区新光町4-1", "新潟市", "中央区", "新光町", None, 4, 1, None, None),
    ("16", "富山県", "富山県富山市新総曲輪1-7", "富山市", None, "新総曲輪", None, 1, 7, None, None),
    ("17", "石川県", "石川県金沢市鞍月1-1", "金沢市", None, "鞍月", None, 1, 1, None, None),
    ("18", "福井県", "福井県福井市大手3-17-1", "福井市", None, "大手", 3, 17, 1, None, None),
    ("19", "山梨県", "山梨県甲府市丸の内1-6-1", "甲府市", None, "丸の内", 1, 6, 1, None, None),
    ("20", "長野県", "長野県長野市大字南長野字幅下692-2", "長野市", None, "大字南長野字幅下", None, None, None, 692, 2),
    ("21", "岐阜県", "岐阜県岐阜市薮田南2-1-1", "岐阜市", None, "薮田南", 2, 1, 1, None, None),
    ("22", "静岡県", "静岡県静岡市葵区追手町9-6", "静岡市", "葵区", "追手町", None, 9, 6, None, None),
    ("23", "愛知県", "愛知県名古屋市中区三の丸3-1-2", "名古屋市", "中区", "三の丸", 3, 1, 2, None, None),
    ("24", "三重県", "三重県津市広明町13", "津市", None, "広明町", None, 13, None, None, None),
    ("25", "滋賀県", "滋賀県大津市京町4-1-1", "大津市", None, "京町", 4, 1, 1, None, None),
    ("26", "京都府", "京都府京都市上京区下立売通新町西入薮ノ内町", "京都市", "上京区", "薮ノ内町", None, None, None, None, None),
    ("27", "大阪府", "大阪府大阪市中央区大手前2丁目", "大阪市", "中央区", "大手前", 2, None, None, None, None),
    ("28", "兵庫県", "兵庫県神戸市中央区下山手通5-10-1", "神戸市", "中央区", "下山手通", 5, 10, 1, None, None),
    ("29", "奈良県", "奈良県奈良市登大路町30", "奈良市", None, "登大路町", None, 30, None, None, None),
    ("30", "和歌山県", "和歌山県和歌山市小松原通1-1", "和歌山市", None, "小松原通", None, 1, 1, None, None),
    ("31", "鳥取県", "鳥取県鳥取市東町1-220", "鳥取市", None, "東町", None, 1, 220, None, None),
    ("32", "島根県", "島根県松江市殿町1", "松江市", None, "殿町", None, 1, None, None, None),
    ("33", "岡山県", "岡山県岡山市北区内山下2-4-6", "岡山市", "北区", "内山下", 2, 4, 6, None, None),
    ("34", "広島県", "広島県広島市中区基町10-52", "広島市", "中区", "基町", None, 10, 52, None, None),
    ("35", "山口県", "山口県山口市滝町1-1", "山口市", None, "滝町", None, 1, 1, None, None),
    ("36", "徳島県", "徳島県徳島市万代町1-1", "徳島市", None, "万代町", None, 1, 1, None, None),
    ("37", "香川県", "香川県高松市番町4-1-10", "高松市", None, "番町", 4, 1, 10, None, None),
    ("38", "愛媛県", "愛媛県松山市一番町4-4-2", "松山市", None, "一番町", 4, 4, 2, None, None),
    ("39", "高知県", "高知県高知市丸ノ内1-2-20", "高知市", None, "丸ノ内", 1, 2, 20, None, None),
    ("40", "福岡県", "福岡県福岡市博多区東公園7-7", "福岡市", "博多区", "東公園", None, 7, 7, None, None),
    ("41", "佐賀県", "佐賀県佐賀市城内1-1-59", "佐賀市", None, "城内", 1, 1, 59, None, None),
    ("42", "長崎県", "長崎県長崎市尾上町3-1", "長崎市", None, "尾上町", None, 3, 1, None, None),
    ("43", "熊本県", "熊本県熊本市中央区水前寺6-18-1", "熊本市", "中央区", "水前寺", 6, 18, 1, None, None),
    ("44", "大分県", "大分県大分市大手町3-1-1", "大分市", None, "大手町", 3, 1, 1, None, None),
    ("45", "宮崎県", "宮崎県宮崎市橘通東2-10-1", "宮崎市", None, "橘通東", 2, 10, 1, None, None),
    ("46", "鹿児島県", "鹿児島県鹿児島市鴨池新町10-1", "鹿児島市", None, "鴨池新町", None, 10, 1, None, None),
    ("47", "沖縄県", "沖縄県那覇市泉崎1-2-2", "那覇市", None, "泉崎", 1, 2, 2, None, None),
]


@pytest.mark.parametrize(
    "expected_pref_code,expected_pref_name,address_str,expected_city,expected_ward,expected_town,expected_chome,expected_ban,expected_go,expected_banchi,expected_edaban",
    PREFECTURE_TEST_CASES
)
def test_all_47_prefectures_full_decomposition(
    expected_pref_code,
    expected_pref_name,
    address_str,
    expected_city,
    expected_ward,
    expected_town,
    expected_chome,
    expected_ban,
    expected_go,
    expected_banchi,
    expected_edaban
):
    normalizer = AddressNormalizer()
    res = normalizer.normalize(address_str)

    # 1. Prefecture assertion
    assert res.components.prefecture_code == expected_pref_code, (
        f"Expected code {expected_pref_code} for {address_str}, got {res.components.prefecture_code}"
    )
    assert res.components.prefecture == expected_pref_name, (
        f"Expected {expected_pref_name} for {address_str}, got {res.components.prefecture}"
    )

    # 2. Municipality assertion
    assert res.components.city == expected_city, (
        f"Expected city {expected_city} for {address_str}, got {res.components.city}"
    )
    assert res.components.ward == expected_ward, (
        f"Expected ward {expected_ward} for {address_str}, got {res.components.ward}"
    )

    # 3. Town assertion
    if expected_town is not None:
        assert res.components.town == expected_town, (
            f"Expected town {expected_town} for {address_str}, got {res.components.town}"
        )

    # 4. Granular block-level decomposition assertions
    assert res.components.chome == expected_chome, (
        f"Expected chome {expected_chome} for {address_str}, got {res.components.chome}"
    )
    assert res.components.ban == expected_ban, (
        f"Expected ban {expected_ban} for {address_str}, got {res.components.ban}"
    )
    assert res.components.go == expected_go, (
        f"Expected go {expected_go} for {address_str}, got {res.components.go}"
    )
    assert res.components.banchi == expected_banchi, (
        f"Expected banchi {expected_banchi} for {address_str}, got {res.components.banchi}"
    )
    assert res.components.edaban == expected_edaban, (
        f"Expected edaban {expected_edaban} for {address_str}, got {res.components.edaban}"
    )

    # 5. Regional conventions
    if expected_pref_code == "01":
        assert res.components.hokkaido_grid is not None
        assert res.components.hokkaido_grid.jo == 1
        assert res.components.hokkaido_grid.chome == 2
    elif expected_pref_code == "20":
        assert res.components.oaza == "南長野"
        assert res.components.koaza == "幅下"
        assert res.components.banchi == 692
        assert res.components.edaban == 2
        assert res.components.address_regime == "chiban"
    elif expected_pref_code == "26":
        assert res.components.kyoto_direction is not None
        assert res.components.kyoto_direction.street_1 == "下立売通"
        assert res.components.kyoto_direction.street_2 == "新町"
        assert res.components.kyoto_direction.direction == "西入"

    # 6. Statutory code and confidence
    assert res.components.lg_code is not None
    assert res.confidence_score >= 0.70


# Dedicated representative county (郡) test cases covering multiple prefectures and both 町 and 村
COUNTY_TEST_CASES = [
    # (address_str, expected_pref, expected_county, expected_city, expected_town, expected_ban, expected_banchi, expected_lg_code)
    ("神奈川県中郡大磯町大磯1392", "神奈川県", "中郡", "大磯町", "大磯", 1392, None, "143413"),
    ("東京都西多摩郡日の出町平井2780", "東京都", "西多摩郡", "日の出町", "平井", 2780, None, "133051"),
    ("北海道石狩郡当別町白樺町200", "北海道", "石狩郡", "当別町", "白樺町", 200, None, "013030"),
    ("埼玉県入間郡三芳町藤久保1100", "埼玉県", "入間郡", "三芳町", "藤久保", 1100, None, "113247"),
    ("長野県下高井郡野沢温泉村大字豊郷9817", "長野県", "下高井郡", "野沢温泉村", "大字豊郷", None, 9817, "205630"),
    ("沖縄県国頭郡国頭村字辺土名121", "沖縄県", "国頭郡", "国頭村", "字辺土名", None, 121, "473014"),
    ("北海道二海郡八雲町本町110", "北海道", "二海郡", "八雲町", "本町", 110, None, "013463"),
]


@pytest.mark.parametrize(
    "address_str,expected_pref,expected_county,expected_city,expected_town,expected_ban,expected_banchi,expected_lg_code",
    COUNTY_TEST_CASES
)
def test_county_municipalities_decomposition(
    address_str,
    expected_pref,
    expected_county,
    expected_city,
    expected_town,
    expected_ban,
    expected_banchi,
    expected_lg_code
):
    normalizer = AddressNormalizer()
    res = normalizer.normalize(address_str)

    assert res.components.prefecture == expected_pref
    assert res.components.county == expected_county
    assert res.components.city == expected_city
    assert res.components.town == expected_town
    assert res.components.lg_code == expected_lg_code
    if expected_ban is not None:
        assert res.components.ban == expected_ban
    if expected_banchi is not None:
        assert res.components.banchi == expected_banchi
    assert res.confidence_score >= 0.70
    assert "county" in res.tier_map


def test_county_omitted_prefecture_inference():
    normalizer = AddressNormalizer()
    # Omitted prefecture with county: should resolve unambiguously and not be rejected by guard
    res_kanagawa = normalizer.normalize("中郡大磯町大磯1392")
    assert res_kanagawa.components.prefecture == "神奈川県"
    assert res_kanagawa.components.prefecture_inferred is True
    assert res_kanagawa.components.county == "中郡"
    assert res_kanagawa.components.city == "大磯町"
    assert res_kanagawa.components.lg_code == "143413"
    assert res_kanagawa.confidence_score >= 0.70

    res_tokyo = normalizer.normalize("西多摩郡日の出町平井2780")
    assert res_tokyo.components.prefecture == "東京都"
    assert res_tokyo.components.prefecture_inferred is True
    assert res_tokyo.components.county == "西多摩郡"
    assert res_tokyo.components.city == "日の出町"
    assert res_tokyo.components.lg_code == "133051"
    assert res_tokyo.confidence_score >= 0.70

