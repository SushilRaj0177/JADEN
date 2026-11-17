"""Cases found by running JADEN on real public datasets (benchmarks/realdata).

Every address here was typed by a care office (Ministry of Health, Labour and Welfare open data)
or is registered for a corporation (National Tax Agency), and was wrong before the fix it guards.
"""

import pytest

import jaden


def _lg(address):
    return jaden.normalize(address).components.lg_code


# --- municipality names in variant spellings ---------------------------------------------------

@pytest.mark.parametrize("address, lg_code, canonical", [
    ("神奈川県茅ケ崎市赤松町13－16", "142077", "神奈川県茅ヶ崎市赤松町13番16号"),          # ケ for ヶ
    ("茅が崎市赤松町13-16", "142077", "神奈川県茅ヶ崎市赤松町13番16号"),                   # が, no prefecture
    ("神奈川県横浜市保土ヶ谷区峰岡町2-118", "141062", "神奈川県横浜市保土ケ谷区峰岡町2丁目118番"),
    ("福岡県糟屋郡須惠町大字植木１６８番地１", "403440", "福岡県糟屋郡須恵町大字植木168番地の1"),   # old kanji
    ("宮城県塩釜市錦町7番10号", "042030", "宮城県塩竈市錦町7番10号"),
    ("長崎県諌早市小長井町井崎1406", "422045", "長崎県諫早市小長井町井崎1406番"),
    ("群馬県伊勢﨑市韮塚町394-1", "102041", "群馬県伊勢崎市韮塚町394番1号"),
    ("千葉県鎌ヶ谷市中央1-1-32", "122246", "千葉県鎌ケ谷市中央1丁目1番32号"),
    ("茨城県龍ヶ崎市小柴1丁目2-5", "082082", "茨城県龍ケ崎市小柴1丁目2番5号"),
])
def test_municipality_variant_spellings(address, lg_code, canonical):
    res = jaden.normalize(address)
    assert res.components.lg_code == lg_code
    assert res.canonical == canonical
    assert jaden.validate(address).status == "ACCEPTED"


def test_variant_fold_keeps_the_rest_of_the_address_as_written():
    res = jaden.normalize("神奈川県茅ケ崎市浜見平11-1BRANCH茅ヶ崎　2－Ⅾ")
    assert res.components.building == "BRANCH茅ヶ崎 2-D"


def test_kashima_cities_stay_apart():
    # 鹿嶋市 (Ibaraki) and 鹿島市 (Saga) differ only by a kanji variant: the spelling as written decides
    assert _lg("鹿嶋市宮中伏見4448-5") == "082228"
    assert _lg("鹿島市大字高津原1-1") == "412074"
    assert jaden.validate("佐賀県鹿嶋市浜津賀457-6").status == "MALFORMED"


@pytest.mark.parametrize("address, lg_code", [
    ("東京都八丈島八丈町大賀郷１４２１番地", "134015"),          # registry notation of the Izu islands
    ("東京都三宅島三宅村阿古２１６４番地", "133817"),
    ("福岡県粕屋郡篠栗町大字金出3553", "403423"),               # 粕屋郡 for 糟屋郡
    ("北海道河西群芽室町東3条4丁目1番地５", "016373"),           # 群 for 郡
    ("和歌山県　西牟婁郡　白浜町　日置１９７－１", "304018"),      # spaces between the parts
    ("三重県三重県津市渋見町357-5", "242012"),                  # prefecture typed twice
    ("北海道札幌市札幌市南区石山８３７番地４６", "011061"),        # city typed twice
    ("神奈川県横浜市横浜市金沢区富岡西２－３－1", "141089"),
    ("茨城県龍ヶ崎市龍ケ崎市貝原塚町3689", "082082"),
])
def test_administrative_head_is_repaired(address, lg_code):
    assert _lg(address) == lg_code
    assert jaden.validate(address).status == "ACCEPTED"


# --- the block number comes before the building ------------------------------------------------

@pytest.mark.parametrize("address, canonical, building, floor, unit", [
    ("埼玉県三郷市谷口212堀切マンション101号室", "埼玉県三郷市谷口212番 堀切マンション 101号室", "堀切マンション", None, "101号室"),
    ("神奈川県川崎市多摩区登戸1664河興ビル2-2", "神奈川県川崎市多摩区登戸1664番 河興ビル2-2", "河興ビル2-2", None, None),
    ("千葉県千葉市稲毛区柏台1稲毛ファミリーハイツ5-1", "千葉県千葉市稲毛区柏台1番 稲毛ファミリーハイツ5-1", "稲毛ファミリーハイツ5-1", None, None),
    ("愛知県豊田市広川町7-91-11広川町7丁目事務所102号室", "愛知県豊田市広川町7丁目91番11号 広川町7丁目事務所 102号室",
     "広川町7丁目事務所", None, "102号室"),
    ("神奈川県横浜市旭区南希望が丘６８三輪ビル　1階1号室", "神奈川県横浜市旭区南希望が丘68番 三輪ビル 1階 1号室", "三輪ビル", "1階", "1号室"),
    ("東京都八王子市松が谷11医療施設1号棟103号", "東京都八王子市松が谷11番 医療施設1号棟 103号", "医療施設1号棟", None, "103号"),
])
def test_first_number_after_the_town_is_the_block(address, canonical, building, floor, unit):
    res = jaden.normalize(address)
    c = res.components
    assert res.canonical == canonical
    assert (c.building, c.floor, c.unit) == (building, floor, unit)


def test_numbered_town_names_are_not_cut_at_their_number():
    assert jaden.normalize("北海道旭川市忠和1条2丁目3-4").canonical == "北海道旭川市忠和一条2丁目3番4号"


@pytest.mark.parametrize("address, canonical", [
    ("兵庫県三田市川除６７５番地三田市総合福祉保健センター", "兵庫県三田市川除675番地 三田市総合福祉保健センター"),
    ("北海道二海郡八雲町熊石根崎町１１６番地八雲町役場熊石総合支所内", "北海道二海郡八雲町熊石根崎町116番地 八雲町役場熊石総合支所内"),
    ("徳島県徳島市幸町3丁目77番地一般社団法人徳島市医師会", "徳島県徳島市幸町3丁目77番地 一般社団法人徳島市医師会"),
    ("東京都新宿区西新宿2丁目8番地三号", "東京都新宿区西新宿2丁目8番地の3"),      # a marked kanji numeral is still a number
])
def test_kanji_numeral_after_banchi_needs_a_mark(address, canonical):
    assert jaden.normalize(address).canonical == canonical


@pytest.mark.parametrize("address, canonical", [
    ("沖縄県那覇市具志２－４－１３階", "沖縄県那覇市具志2丁目4番1号 3階"),
    ("東京都墨田区京島1-47-172F", "東京都墨田区京島1丁目47番17号 2F"),
    ("千葉県習志野市津田沼7-1-103階", "千葉県習志野市津田沼7丁目1番10号 3階"),
    ("沖縄県浦添市前田997番地1階", "沖縄県浦添市前田997番地 1階"),
    ("埼玉県さいたま市岩槻区上野2-9-4103号", "埼玉県さいたま市岩槻区上野2丁目9番4号 103号"),
    ("北海道札幌市西区宮の沢1条4丁目13-1105号", "北海道札幌市西区宮の沢一条4丁目13番1号 105号"),
    ("愛知県岡崎市上六名町木ノ座20番地１２号室", "愛知県岡崎市上六名町木ノ座20番地 12号室"),
])
def test_floor_or_room_glued_to_the_house_number(address, canonical):
    assert jaden.normalize(address).canonical == canonical


def test_plain_house_numbers_are_untouched():
    assert jaden.normalize("東京都港区芝公園4-2-8").canonical == "東京都港区芝公園4丁目2番8号"
    assert jaden.normalize("大阪府大阪市中央区難波5丁目1番60号").canonical == "大阪府大阪市中央区難波5丁目1番60号"
    assert jaden.normalize("鹿児島県鹿児島市山田町2174番地6号").canonical == "鹿児島県鹿児島市山田町2174番地の6"


# --- a 丁目 the registry does not list -----------------------------------------------------------

@pytest.mark.parametrize("address", [
    "愛知県岡崎市城南町三丁目9-2",            # 丁目 recorded as 字 names
    "福島県伊達市保原町七丁目33番地３",
    "鹿児島県鹿児島市吉野3丁目5番8号",         # the registry has 1–2丁目
    "大分県別府市東荘園5丁目8番26号",          # the registry has 8–9丁目
])
def test_plausible_unlisted_chome_is_accepted_with_a_warning(address):
    res = jaden.normalize(address)
    val = jaden.validate(address)
    assert val.status == "ACCEPTED"
    assert res.components.chome_unlisted is True
    assert res.components.chome_verified is None
    assert val.verification_level == "town"
    assert any("not in the registry" in w for w in val.warnings)
    assert jaden.validate(address, strict=True).status == "UNSUPPORTED"


@pytest.mark.parametrize("address", [
    "東京都港区芝公園9-2-8",                  # 芝公園 has 1–4丁目
    "東京都港区芝公園99丁目2番8号",
    "沖縄県那覇市長田11-10-20　1階",           # 長田 has 1–2丁目
])
def test_impossible_chome_is_still_rejected(address):
    val = jaden.validate(address)
    assert val.status == "MALFORMED"
    assert "does not exist" in val.message
    assert jaden.normalize(address).components.chome_unlisted is False


def test_town_without_machi_is_chosen_when_only_it_has_the_chome():
    # 二日市町 has no 丁目; 二日市 has 1–5丁目
    res = jaden.normalize("石川県野々市市二日市町4丁目102番地ガレリアコルテ106号室")
    assert res.components.town == "二日市"
    assert res.components.chome_verified is True


def test_registered_chome_beats_an_unlisted_one_among_candidates():
    # 芝公園4丁目 is registered only in 東京都港区; the other 港区 do not gain it as a 'new' 丁目
    assert _lg("港区芝公園4-2-8") == "131032"


# --- speed -----------------------------------------------------------------------------------

def test_postal_lookup_uses_the_index():
    from jaden.engine import get_engine
    gaz = get_engine().gazetteer
    assert [r.town for r in gaz.postal_records("105-0011")] == ["芝公園"]
    assert gaz.postal_records("9999999") == []
    assert gaz.postal_records("abc") == []
