"""Real-life input patterns: rooms, buildings, form labels, Sapporo shorthand, numbered towns."""

import pytest

import jaden


@pytest.mark.parametrize("raw, building, floor, unit", [
    ("東京都港区芝公園4-2-8-101", None, None, "101"),
    ("東京都港区芝公園4-2-8 101号室", None, None, "101号室"),
    ("東京都港区芝公園4丁目2-8 グランドメゾン芝公園302", "グランドメゾン芝公園", None, "302"),
    ("東京都港区芝公園4-2-8グランドメゾン芝公園302号", "グランドメゾン芝公園", None, "302号"),
    ("東京都港区芝公園4-2-8 #302", None, None, "302"),
    ("東京都港区芝公園4-2-8 Apt 302", None, None, "302"),
    ("東京都港区芝公園4-2-8 B棟305号室", "B棟", None, "305号室"),
    ("東京都港区芝公園4-2-8 コーポ田中-101", "コーポ田中", None, "101"),
    ("大阪府大阪市北区梅田3-1-1-5F", None, "5F", None),
    ("東京都新宿区西新宿2-8-1 東京都庁第一本庁舎 32階", "東京都庁第一本庁舎", "32階", None),
    ("北海道網走市潮見188 703号室", None, None, "703号室"),
    ("東京都千代田区神田錦町1-1 第一-3ビル", "第一-3ビル", None, None),
])
def test_building_floor_unit(raw, building, floor, unit):
    c = jaden.normalize(raw).components
    assert (c.building, c.floor, c.unit) == (building, floor, unit)


@pytest.mark.parametrize("raw", [
    "日本 東京都港区芝公園4-2-8",
    "日本、〒105-0011 東京都港区芝公園4-2-8",
    "郵便番号105-0011 東京都港区芝公園4-2-8",
    "住所：東京都港区芝公園4-2-8",
    "Japan 東京都港区芝公園4-2-8",
    "東京都 港区 芝公園 4-2-8",
    "東京都港区芝公園4丁目 2番 8号",
    "東京都港区芝公園４－２－８",
])
def test_form_noise_does_not_change_the_address(raw):
    assert jaden.normalize(raw).canonical == "東京都港区芝公園4丁目2番8号"


def test_nihonbashi_is_not_a_country_prefix():
    assert jaden.normalize("東京都中央区日本橋1-1-1").components.town == "日本橋"


@pytest.mark.parametrize("raw, canonical", [
    ("北海道札幌市中央区南3西4", "北海道札幌市中央区南3条西4丁目"),
    ("札幌市中央区北1条西2", "北海道札幌市中央区北1条西2丁目"),
    ("札幌市中央区南1西4-5-2", "北海道札幌市中央区南1条西4丁目5番2号"),
    ("北海道札幌市北区北7西5", "北海道札幌市北区北7条西5丁目"),
])
def test_sapporo_shorthand(raw, canonical):
    assert jaden.normalize(raw).canonical == canonical


def test_sapporo_grid_with_room():
    c = jaden.normalize("北海道上川郡東神楽町南3条東1-2-1-305").components
    assert (c.ban, c.go, c.unit) == (2, 1, "305")


@pytest.mark.parametrize("raw, town", [
    ("北海道旭川市忠和1条4 201号室", "忠和一条"),
    ("北海道河西郡芽室町芽室南2線30", "芽室南二線"),
    ("新潟県新潟市西区五十嵐3の町9952", "五十嵐三の町"),
    ("新潟県新潟市中央区古町通6番町976", "古町通六番町"),
])
def test_numbered_town_names(raw, town):
    assert jaden.normalize(raw).components.town == town


@pytest.mark.parametrize("raw, canonical", [
    ("岩手県盛岡市下飯岡8地割99-3", "岩手県盛岡市下飯岡8地割99番地の3"),
    ("石川県白山市横江町土地区画整理事業施行地区内8街区2", "石川県白山市横江町土地区画整理事業施行地区内8街区2番地"),
    ("群馬県桐生市相生町1-乙394", "群馬県桐生市相生町1丁目乙394"),
    ("高知県香美市大栃1800-イ", "高知県香美市大栃1800-イ"),
])
def test_lot_number_conventions(raw, canonical):
    assert jaden.normalize(raw).canonical == canonical


def test_parenthesized_note_is_kept_out_of_the_numbers():
    c = jaden.normalize("長野県佐久市臼田751(佐久平総合技術高等学校臼田キャンパス内) 203号室").components
    assert c.unit == "203号室"
    assert "(佐久平総合技術高等学校臼田キャンパス内)" in c.building


def test_kyoto_clause_with_street_chome():
    c = jaden.normalize("京都府京都市東山区鞘町五条下ル2丁目大阪町378").components
    assert c.town == "大阪町"
    assert c.banchi == 378
    assert c.kyoto_direction.raw_clause == "鞘町五条下ル2丁目"


# ------------------------------------------------------- former municipality names
@pytest.mark.parametrize("raw, lg_code, canonical", [
    ("埼玉県浦和市高砂3-15-1", "111074", "埼玉県さいたま市浦和区高砂3丁目15番1号"),
    ("浦和市高砂3-15-1", "111074", "埼玉県さいたま市浦和区高砂3丁目15番1号"),
    ("静岡県清水市旭町6-8", "221031", "静岡県静岡市清水区旭町6番8号"),
    ("静岡県浜松市中区元城町103-2", "221384", "静岡県浜松市中央区元城町103番2号"),
    ("浜松市北区細江町気賀305", "221392", "静岡県浜松市浜名区細江町気賀305番"),
    ("岐阜県土岐郡笠原町2950", "212041", "岐阜県多治見市笠原町2950番"),
    ("兵庫県篠山市北新町41", "282219", "兵庫県丹波篠山市北新町41番"),
])
def test_former_municipality_names(raw, lg_code, canonical):
    res = jaden.normalize(raw)
    assert res.components.lg_code == lg_code
    assert res.canonical == canonical
    assert res.components.former_municipality is not None
    assert jaden.validate(raw).status == "ACCEPTED"


def test_former_name_without_town_is_ambiguous():
    # 浦和市 became four wards; without a town there is nothing to choose by
    assert jaden.validate("埼玉県浦和市").status == "AMBIGUOUS"
