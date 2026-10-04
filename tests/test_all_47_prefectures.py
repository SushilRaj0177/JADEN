"""Systematic coverage test suite across all 47 Japanese prefectures (JIS X 0401)."""

import pytest
from jaden.engine import AddressNormalizer

# Ground-truth test addresses covering prefectural capitals across all 47 prefectures
PREFECTURE_TEST_CASES = [
    ("01", "北海道", "北海道札幌市中央区北1条西2丁目"),
    ("02", "青森県", "青森県青森市新町1-1"),
    ("03", "岩手県", "岩手県盛岡市内丸1-1"),
    ("04", "宮城県", "宮城県仙台市青葉区本町3-8-1"),
    ("05", "秋田県", "秋田県秋田市山王4-1-1"),
    ("06", "山形県", "山形県山形市松波2-8-1"),
    ("07", "福島県", "福島県福島市杉妻町2-16"),
    ("08", "茨城県", "茨城県水戸市笠原町978-6"),
    ("09", "栃木県", "栃木県宇都宮市塙田1-1-20"),
    ("10", "群馬県", "群馬県前橋市大手町1-1-1"),
    ("11", "埼玉県", "埼玉県さいたま市浦和区高砂3-15-1"),
    ("12", "千葉県", "千葉県千葉市中央区市場町1-1"),
    ("13", "東京都", "東京都新宿区西新宿2丁目8番1号"),
    ("14", "神奈川県", "神奈川県横浜市中区日本大通1"),
    ("15", "新潟県", "新潟県新潟市中央区新光町4-1"),
    ("16", "富山県", "富山県富山市新総曲輪1-7"),
    ("17", "石川県", "石川県金沢市鞍月1-1"),
    ("18", "福井県", "福井県福井市大手3-17-1"),
    ("19", "山梨県", "山梨県甲府市丸の内1-6-1"),
    ("20", "長野県", "長野県長野市大字南長野字幅下692-2"),
    ("21", "岐阜県", "岐阜県岐阜市薮田南2-1-1"),
    ("22", "静岡県", "静岡県静岡市葵区追手町9-6"),
    ("23", "愛知県", "愛知県名古屋市中区三の丸3-1-2"),
    ("24", "三重県", "三重県津市広明町13"),
    ("25", "滋賀県", "滋賀県大津市京町4-1-1"),
    ("26", "京都府", "京都府京都市上京区下立売通新町西入薮ノ内町"),
    ("27", "大阪府", "大阪府大阪市中央区大手前2丁目"),
    ("28", "兵庫県", "兵庫県神戸市中央区下山手通5-10-1"),
    ("29", "奈良県", "奈良県奈良市登大路町30"),
    ("30", "和歌山県", "和歌山県和歌山市小松原通1-1"),
    ("31", "鳥取県", "鳥取県鳥取市東町1-220"),
    ("32", "島根県", "島根県松江市殿町1"),
    ("33", "岡山県", "岡山県岡山市北区内山下2-4-6"),
    ("34", "広島県", "広島県広島市中区基町10-52"),
    ("35", "山口県", "山口県山口市滝町1-1"),
    ("36", "徳島県", "徳島県徳島市万代町1-1"),
    ("37", "香川県", "香川県高松市番町4-1-10"),
    ("38", "愛媛県", "愛媛県松山市一番町4-4-2"),
    ("39", "高知県", "高知県高知市丸ノ内1-2-20"),
    ("40", "福岡県", "福岡県福岡市博多区東公園7-7"),
    ("41", "佐賀県", "佐賀県佐賀市城内1-1-59"),
    ("42", "長崎県", "長崎県長崎市尾上町3-1"),
    ("43", "熊本県", "熊本県熊本市中央区水前寺6-18-1"),
    ("44", "大分県", "大分県大分市大手町3-1-1"),
    ("45", "宮崎県", "宮崎県宮崎市橘通東2-10-1"),
    ("46", "鹿児島県", "鹿児島県鹿児島市鴨池新町10-1"),
    ("47", "沖縄県", "沖縄県那覇市泉崎1-2-2"),
]


@pytest.mark.parametrize("expected_pref_code,expected_pref_name,address_str", PREFECTURE_TEST_CASES)
def test_all_47_prefectures_resolution(expected_pref_code, expected_pref_name, address_str):
    normalizer = AddressNormalizer()
    res = normalizer.normalize(address_str)

    assert res.components.prefecture_code == expected_pref_code, (
        f"Expected code {expected_pref_code} for {address_str}, got {res.components.prefecture_code}"
    )
    assert res.components.prefecture == expected_pref_name, (
        f"Expected {expected_pref_name} for {address_str}, got {res.components.prefecture}"
    )
    assert res.confidence_score >= 0.70
