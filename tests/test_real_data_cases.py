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


# --- postal code filled in for the town ------------------------------------------------------

@pytest.mark.parametrize("address, postal_code", [
    ("沖縄県宮古島市平良字久貝１０４７番地２１", "906-0015"),     # Japan Post lists the 字 as a town: 平良久貝
    ("秋田県秋田市泉字金ノ町３３番地の５", "010-0816"),           # the 字 belongs to the town 泉
    ("青森県平川市八幡崎宮本８８番地", "036-0241"),
    ("京都府舞鶴市字浜１２０番地３", "625-0036"),                # '字浜' is 浜
    ("東京都新宿区西早稲田３丁目３１番８号", "169-0051"),          # 162-0051 covers only part of 2丁目
    ("東京都江戸川区江戸川６丁目７番地５", "134-0013"),            # 132-0013 is 1–3丁目 and part of 4丁目
    ("北海道札幌市中央区北1条西2丁目1-1", "060-0001"),            # 1–19丁目
    ("北海道札幌市中央区北1条西22丁目1-1", "064-0821"),           # 20–28丁目
    ("東京都港区芝公園4-2-8", "105-0011"),
])
def test_postal_code_filled_in(address, postal_code):
    assert jaden.normalize(address).components.postal_code == postal_code


def test_postal_code_left_empty_when_the_town_is_split_and_the_chome_does_not_decide():
    # 2丁目 of 西早稲田 is divided between two postal codes by block
    assert jaden.normalize("東京都新宿区西早稲田２丁目５番１６号").components.postal_code is None


def test_japan_post_chome_notes_are_parsed():
    from jaden.data.build_gazetteer import _postal_chomes
    assert _postal_chomes("北一条西（１〜１９丁目）") == "1-19"
    assert _postal_chomes("Ｘ（２、３丁目）") == "2,3"
    assert _postal_chomes("西早稲田（２丁目１番１〜２３号、２番）") == "~2"
    assert _postal_chomes("江戸川（１〜３丁目、４丁目１〜１４番）") == "1-3,~4"
    assert _postal_chomes("Ｘ（丁目）") == "*"
    assert _postal_chomes("Ｘ（その他）") == "-"
    assert _postal_chomes("六本木（次のビルを除く）") == "?"
    assert _postal_chomes("芝公園") == ""


# --- one town, several spellings -------------------------------------------------------------

def test_aza_marker_inside_a_town_name_is_optional():
    # MLIT registers 高木瀬町大字長瀬; Japan Post and the office write 高木瀬町長瀬
    a = jaden.match_key("佐賀県佐賀市高木瀬町長瀬1307番地")
    b = jaden.match_key("佐賀市高木瀬町大字長瀬1307番地")
    assert a == b and a is not None
    assert jaden.compare("佐賀県佐賀市高木瀬町長瀬1307番地", "佐賀市高木瀬町大字長瀬1307番地").verdict == "same"


def test_thousands_separator_in_a_lot_number():
    assert jaden.normalize("東京都西多摩郡奥多摩町氷川1,111").canonical == jaden.normalize("東京都西多摩郡奥多摩町氷川１１１１").canonical


def test_numbered_town_written_with_chome_keeps_its_lot_number():
    res = jaden.normalize("名張市鴻之台１丁目７２番地")
    assert res.canonical == "三重県名張市鴻之台一番町72番地"


# --- data build ------------------------------------------------------------------------------

def test_romaji_is_hepburn_whatever_the_source_file_spells():
    from jaden.data.build_gazetteer import _hepburn, _spells_long_vowels
    # Japan Post's file switched to letter-by-letter transliteration; mail uses Hepburn
    assert _hepburn("SHIBAKOUEN", "シバコウエン") == "SHIBAKOEN"
    assert _hepburn("CHUUOU", "チュウオウ") == "CHUO"
    assert _hepburn("SHINMINATOCHOU", "シンミナトチョウ") == "SHIMMINATOCHO"
    assert _hepburn("HACCHOUDAIRA", "ハッチョウダイラ") == "HATCHODAIRA"
    assert _hepburn("RYUUTSUUSENTAA", "リュウツウセンター") == "RYUTSUSENTA"
    assert _hepburn("KITAAIZUMACHI", "キタアイヅマチ") == "KITAAIZUMACHI"
    old_style = [["1050011", "東京都", "港区", "芝公園", "TOKYO TO", "MINATO KU", "SHIBAKOEN"]] * 10
    new_style = [["1050011", "東京都", "港区", "芝公園", "TOKYO TO", "MINATO KU", "SHIBAKOUEN"]] * 10
    assert not _spells_long_vowels(old_style)
    assert _spells_long_vowels(new_style)
    assert jaden.normalize("東京都港区芝公園4-2-8").romaji == "4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011"


# --- the municipality written wrongly --------------------------------------------------------

@pytest.mark.parametrize("address, lg_code, canonical", [
    ("大阪府東大阪岩田町4丁目15-13", "272272", "大阪府東大阪市岩田町4丁目15番13号"),          # 市 left out
    ("東京都府中白糸台1丁目63-1", "132063", "東京都府中市白糸台1丁目63番1号"),
    ("東京都練馬田柄3-6-18", "131202", "東京都練馬区田柄3丁目6番18号"),                       # 区 left out
    ("愛知県名古屋中川区千音寺二丁目1513番地", "231100", "愛知県名古屋市中川区千音寺2丁目1513番地"),
    ("静岡県浜松市中央小池町３８番地の1", "221384", "静岡県浜松市中央区小池町38番地の1"),    # ward without 区
    ("宮城県仙台市青葉上杉5丁目6-3", "041017", "宮城県仙台市青葉区上杉5丁目6番3号"),
    ("鳥取県烏取市古海693-1", "312011", "鳥取県鳥取市古海693番1号"),                          # one character off
    ("福岡県大宰府市大字向佐野515番地", "402214", "福岡県太宰府市大字向佐野515番地"),
    ("愛知県清洲市清洲1111-1", "232335", "愛知県清須市清洲1111番1号"),
    ("熊本県熊本市通央区水前寺5丁目8番15号", "431010", "熊本県熊本市中央区水前寺5丁目8番15号"),
    ("大坂府堺市北区黒土町3002番地5", "271462", "大阪府堺市北区黒土町3002番地の5"),           # prefecture off
    ("ｼ静岡県浜松市中央区中山町4番地", "221384", "静岡県浜松市中央区中山町4番地"),              # stray character
    ("京都府京都市下京区下京区西七条南衣田町11番地", "261068", "京都府京都市下京区西七条南衣田町11番地"),
])
def test_mistyped_municipality_is_read_when_the_town_proves_it(address, lg_code, canonical):
    res = jaden.normalize(address)
    assert res.components.lg_code == lg_code
    assert res.canonical == canonical
    assert jaden.validate(address).status == "ACCEPTED"


def test_mistyped_municipality_repair_says_what_it_did():
    assert any("烏取市" in n and "鳥取市" in n for n in jaden.normalize("鳥取県烏取市古海693-1").notes)


def test_former_ward_keeps_its_explanation():
    notes = jaden.normalize("静岡県浜松市中区小豆餅2-9-13").notes
    assert any("no longer exists" in n for n in notes)


def test_a_bare_town_is_not_read_as_a_shortened_municipality():
    # 栄町 is a town name in many places; it is not a shortened 東栄町
    assert jaden.normalize("愛知県栄町1-1").components.lg_code != "235628"


# --- registered towns with a number or 丁目 inside their name -----------------------------------

def test_sapporo_towns_with_chome_inside_the_name():
    res = jaden.normalize("札幌市白石区平和通7丁目南５－１")
    assert res.canonical == "北海道札幌市白石区平和通七丁目南5番1号"
    assert res.components.town_verified is True


@pytest.mark.parametrize("address, canonical", [
    ("大阪府堺市西区北条町1-2-31", "大阪府堺市西区北条町一丁2番31号"),
    ("大阪府堺市西区北条町1丁2番31号", "大阪府堺市西区北条町一丁2番31号"),
    ("大阪府堺市中区深阪１丁13-83", "大阪府堺市中区深阪一丁13番83号"),
])
def test_sakai_towns_registered_as_n_cho(address, canonical):
    assert jaden.normalize(address).canonical == canonical


# --- separators ------------------------------------------------------------------------------

@pytest.mark.parametrize("address, canonical", [
    ("和光市丸山台２丁目－11番－１号", "埼玉県和光市丸山台2丁目11番1号"),
    ("徳島県吉野川市鴨島町上下島421番地ー1", "徳島県吉野川市鴨島町上下島421番地の1"),
])
def test_hyphen_after_a_block_marker(address, canonical):
    assert jaden.normalize(address).canonical == canonical


# --- places without a lot number, facilities -------------------------------------------------

@pytest.mark.parametrize("address, lot", [
    ("北海道千歳市支笏湖温泉番外地", "番外地"),
    ("神奈川県横須賀市田浦港町無番地", "無番地"),
    ("滋賀県高島市マキノ町海津官有地無番地", "官有地無番地"),
])
def test_unnumbered_lot_is_an_address(address, lot):
    res = jaden.normalize(address)
    assert jaden.validate(address).status == "ACCEPTED"
    assert res.components.lot_number == lot
    assert res.precision == "town"


def test_facility_after_the_town():
    res = jaden.normalize("愛媛県四国中央市村松町愛媛製紙株式会社内")
    assert jaden.validate("愛媛県四国中央市村松町愛媛製紙株式会社内").status == "ACCEPTED"
    assert res.components.town == "村松町"
    assert res.components.building == "愛媛製紙株式会社内"


# --- Kyoto ----------------------------------------------------------------------------------

@pytest.mark.parametrize("address, town", [
    ("京都府京都市上京区今出川通七本松東入上る突抜町５０１番地", "突抜町"),
    ("京都府京都市上京区下立売通千本東入下る中務町４８６－１８", "中務町"),
    ("京都府京都市東山区大仏南門通大和大路東入三丁目下ル本瓦町６６０番地の６", "本瓦町"),
    ("京都府京都市上京区荒神口上がる東入る宮垣町９１", "宮垣町"),
])
def test_kyoto_clause_with_several_turns(address, town):
    res = jaden.normalize(address)
    assert res.components.town == town
    assert res.components.town_verified is True


# --- town spellings ------------------------------------------------------------------------------

@pytest.mark.parametrize("address, canonical", [
    ("東京都新宿区市ヶ谷加賀町二丁目４番１６号", "東京都新宿区市谷加賀町2丁目4番16号"),   # registered without ヶ
    ("東京都中央区小舟町１５番４号", "東京都中央区日本橋小舟町15番4号"),                  # area name in front
    ("東京都新宿区本塩町２１番地", "東京都新宿区四谷本塩町21番地"),
    ("千葉県旭市ニの２７４０番地", "千葉県旭市ニ2740番地"),                              # の joins the town to the lot
    ("秋田県大館市花岡字姥沢２４番地", "秋田県大館市花岡町字姥沢24番地"),                  # 町 before its 字
])
def test_town_spelling_variants(address, canonical):
    res = jaden.normalize(address)
    assert res.canonical == canonical
    assert res.components.town_verified is True


def test_one_character_town_before_aza():
    res = jaden.normalize("福島県いわき市平字三町目１０番地の１")
    assert res.components.town_verified is True
    assert res.components.lg_code == "072044"


@pytest.mark.parametrize("address, lg_code", [
    ("福福島県本宮市白岩字堤崎494-22", "072141"),        # doubled first character
    ("な名古屋市北区金城町4丁目47番地の2", "231037"),     # stray character before the city
    ("北九州若松区西園町11-28", "401030"),              # city without 市 and no prefecture, ward follows
])
def test_damaged_head_is_read(address, lg_code):
    assert _lg(address) == lg_code


@pytest.mark.parametrize("address, lg_code, town", [
    ("大分県長島町3－11－13", "442054", "長島町"),         # 長島町 is a municipality of 鹿児島県, a town of 佐伯市
    ("富山県長柄町3-6-6", "162019", "長柄町"),            # 長柄町 is a municipality of 千葉県, a town of 富山市
])
def test_town_named_like_a_municipality_of_another_prefecture(address, lg_code, town):
    res = jaden.normalize(address)
    assert res.components.lg_code == lg_code
    assert res.components.town == town
    assert jaden.validate(address).status == "ACCEPTED"


def test_wrong_prefecture_is_still_a_contradiction():
    assert jaden.validate("滋賀県弘前市末広3-2-1").status == "MALFORMED"


def test_town_written_without_its_ke():
    res = jaden.normalize("熊本県熊本市武蔵丘1-2-30")
    assert res.components.lg_code == "431052"
    assert res.components.town == "武蔵ケ丘"


# --- a 字 written straight after its 大字, county without its municipality ----------------------

@pytest.mark.parametrize("address, lg_code", [
    ("吉良町中野郷中74番地2", "232131"),            # 西尾市 吉良町中野 + 郷中
    ("勿来町窪田万谷41－5", "072044"),              # いわき市 勿来町 + 窪田万谷
    ("金木町中柏木鎧石342番地2", "022055"),          # 五所川原市 金木町中柏木 + 鎧石
    ("愛知県加納町向井山9番1", "232114"),            # 豊田市 加納町 + 向井山
    ("徳島県名西郡浦庄字上浦524-10", "363413"),       # 名西郡 + town of 石井町
    ("山形県最上郡真室川大字木ノ下字片渕山1125-286", "063649"),   # 真室川 = 真室川町
    ("静岡県周智郡草ケ谷391-1", "224618"),           # 周智郡 has one municipality with 草ケ谷: 森町
])
def test_unmarked_koaza_and_county_readings(address, lg_code):
    assert _lg(address) == lg_code


def test_unmarked_koaza_does_not_turn_facility_names_into_addresses():
    assert jaden.validate("高崎市立国府小学校").status == "UNSUPPORTED"


@pytest.mark.parametrize("address, lg_code", [
    ("宮崎駅東三丁目９番１０", "452017"),            # '宮崎' is part of the town, not the prefecture
    ("兵庫塚町281番地1", "092011"),
])
def test_prefecture_stem_inside_a_town_name(address, lg_code):
    assert _lg(address) == lg_code


def test_prefecture_with_town_in_several_municipalities_is_ambiguous():
    val = jaden.validate("埼玉県狭山台1ｰ10ｰ12")
    assert val.status == "AMBIGUOUS"
    assert any("112259" in c for c in val.ambiguous_candidates)


def test_everyday_kanji_does_not_pick_between_old_and_new_forms():
    # 昭和区 registers 檀溪通 (old form), 瑞穂区 registers 檀渓通
    assert jaden.validate("檀渓通5丁目26番地").status == "AMBIGUOUS"
    assert _lg("檀溪通5丁目26番地") == "231070"


@pytest.mark.parametrize("address, lg_code", [
    ("北23条東16丁目4-27", "011037"),                # Sapporo grid without city or prefecture
    ("御車道通清和院口上る東側梶井町457-1", "261025"), # Kyoto clause ending in 東側
    ("千葉県葉市中央区院内2丁目15番13号", "121011"),   # 千 dropped from 千葉市
    ("愛媛県今治阿方甲407-1", "382027"),             # 市 left out, lot series after the town
    ("神奈川県中郡ニ宮町ニ宮109番地", "143421"),      # katakana ニ typed for 二
])
def test_more_damaged_heads(address, lg_code):
    assert _lg(address) == lg_code


@pytest.mark.parametrize("address, lg_code", [
    ("新潟県新潟市燕市東太田2863-2", "152137"),
    ("熊本市阿蘇市黒川1484番地", "432148"),
    ("大阪府大阪市吹田市藤白台２丁目９番１－１１５号", "272051"),
    ("岐阜県岐阜市関市稲口776-1", "212059"),
    ("神奈川区横浜市緑区北八朔町1597-4", "141135"),
])
def test_second_municipality_wins_when_only_its_town_is_registered(address, lg_code):
    res = jaden.normalize(address)
    assert res.components.lg_code == lg_code
    assert res.components.town_verified is True


@pytest.mark.parametrize("address", [
    "六地蔵町並39番地",          # '六地蔵町' + one character is not enough to pick 岡崎市 over 宇治市
    "宇治山本25-2",
    "上福井西ノ口61-1",
    "神明石塚25-21",
])
def test_town_only_inputs_without_enough_evidence_abstain(address):
    assert jaden.validate(address).status != "ACCEPTED"


# --- name typed twice, or a town of the same name ---------------------------------------------

@pytest.mark.parametrize("address, lg_code", [
    ("北海道札幌市札幌市南区石山８３７番地４６", "011061"),
    ("神奈川県横浜市横浜市金沢区富岡西２－３－1", "141089"),
    ("神奈川区横浜市緑区北八朔町1597-4", "141135"),
])
def test_city_typed_twice_then_its_ward(address, lg_code):
    res = jaden.normalize(address)
    assert res.components.lg_code == lg_code
    assert res.components.town_verified is True


@pytest.mark.parametrize("address, town", [
    ("群馬県吾妻郡中之条町中之条町1395-1", "中之条町"),    # 大字中之条町 of 中之条町
    ("山形県最上郡金山町金山1", "金山"),
])
def test_town_with_the_municipality_name_is_not_a_repetition(address, town):
    res = jaden.normalize(address)
    assert res.components.town == town
    assert res.components.town_verified is True


def test_typo_one_character_from_two_towns_is_not_autocorrected():
    # '石崎町' is one character from 石松町 and from 石井町 (大字石井 written with 町)
    res = jaden.normalize("大分県日田市石崎町3-1244-1", autocorrect=True)
    assert res.components.town_corrected_from is None
    assert len(res.suggestions) == 2


def test_typo_in_a_town_registered_with_an_inner_oaza():
    # registered 浪岡大字本郷; the typo '崎岡本郷' is one character from 浪岡本郷
    assert jaden.normalize("青森県青森市崎岡本郷字岸田17-2").suggestions


def test_trailing_machi_is_the_same_town_in_match_keys():
    assert jaden.match_key("栃木県宇都宮市若草町2-2-46") == jaden.match_key("栃木県宇都宮市若草2-2-46")


def test_inner_oaza_written_or_not_reads_back_the_same():
    for address in ("広島県福山市新市町戸手1244", "宮崎県日南市南郷町大字中村乙7101-390"):
        res = jaden.normalize(address)
        assert jaden.normalize(res.format("hyphen")).canonical == res.canonical


def test_block_file_from_an_older_version_is_still_used(tmp_path, monkeypatch):
    import gzip
    import json
    from jaden.data.gazetteer import Gazetteer
    blocks = tmp_path / "jaden" / "blocks"
    blocks.mkdir(parents=True)
    with gzip.open(blocks / "13.tsv.gz", "wt", encoding="utf-8") as f:
        f.write("lg_code\tkey\tchome\tblock\tlat\tlon\tjukyo\n131032\t芝公園\t4\t2\t35.6586\t139.7454\t1\n")
    (blocks / "13.json").write_text(json.dumps({"town_key_version": 2}), encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    gaz = Gazetteer()
    point = gaz.block_point("131032", "芝公園", 4, 2)
    assert point is not None and abs(point.latitude - 35.6586) < 1e-6
    assert gaz.stale_block_prefectures() == ["13"]
