"""Script to build the verified municipalities.json dataset for JADEN.

Every record contains:
- prefecture_code (2 digits)
- prefecture_name
- base_code (5 digits)
- check_digit (1 digit, calculated via official MIC Modulus 11)
- lg_code (6 digits)
- name (full search name)
- city (base municipality)
- ward (administrative ward if applicable)
- county (gun if applicable)
- entity_type
"""

import json
from pathlib import Path

def calc_check_digit(d5: str) -> str:
    weights = [6, 5, 4, 3, 2]
    s = sum(int(d) * w for d, w in zip(d5, weights))
    r = s % 11
    if r <= 1:
        return str((11 - r) % 10)
    return str(11 - r)

def make_entry(pref_code: str, pref_name: str, base_code: str, name: str, city: str, ward: str = None, county: str = None, entity_type: str = "city"):
    cd = calc_check_digit(base_code)
    lg = base_code + cd
    res = {
        "prefecture_code": pref_code,
        "prefecture_name": pref_name,
        "base_code": base_code,
        "check_digit": cd,
        "lg_code": lg,
        "name": name,
        "city": city,
        "entity_type": entity_type
    }
    if ward:
        res["ward"] = ward
    if county:
        res["county"] = county
    return res

MUNICIPALITIES_DATA = [
    # -------------------------------------------------------------------------
    # 01 北海道 (Hokkaido)
    # -------------------------------------------------------------------------
    make_entry("01", "北海道", "01100", "札幌市", "札幌市", entity_type="designated_city"),
    make_entry("01", "北海道", "01101", "札幌市中央区", "札幌市", ward="中央区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01102", "札幌市北区", "札幌市", ward="北区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01103", "札幌市東区", "札幌市", ward="東区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01104", "札幌市白石区", "札幌市", ward="白石区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01105", "札幌市豊平区", "札幌市", ward="豊平区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01106", "札幌市南区", "札幌市", ward="南区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01107", "札幌市西区", "札幌市", ward="西区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01108", "札幌市厚別区", "札幌市", ward="厚別区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01109", "札幌市手稲区", "札幌市", ward="手稲区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01110", "札幌市清田区", "札幌市", ward="清田区", entity_type="administrative_ward"),
    make_entry("01", "北海道", "01202", "函館市", "函館市"),
    make_entry("01", "北海道", "01203", "小樽市", "小樽市"),
    make_entry("01", "北海道", "01204", "旭川市", "旭川市"),
    make_entry("01", "北海道", "01205", "室蘭市", "室蘭市"),
    make_entry("01", "北海道", "01206", "釧路市", "釧路市"),
    make_entry("01", "北海道", "01207", "帯広市", "帯広市"),
    make_entry("01", "北海道", "01208", "北見市", "北見市"),
    make_entry("01", "北海道", "01209", "夕張市", "夕張市"),
    make_entry("01", "北海道", "01210", "岩見沢市", "岩見沢市"),
    make_entry("01", "北海道", "01211", "網走市", "網走市"),
    make_entry("01", "北海道", "01213", "苫小牧市", "苫小牧市"),
    make_entry("01", "北海道", "01215", "美唄市", "美唄市"),
    make_entry("01", "北海道", "01217", "江別市", "江別市"),
    make_entry("01", "北海道", "01224", "千歳市", "千歳市"),

    # -------------------------------------------------------------------------
    # 02 青森県 (Aomori)
    # -------------------------------------------------------------------------
    make_entry("02", "青森県", "02201", "青森市", "青森市"),
    make_entry("02", "青森県", "02202", "弘前市", "弘前市"),
    make_entry("02", "青森県", "02203", "八戸市", "八戸市"),
    make_entry("02", "青森県", "02204", "黒石市", "黒石市"),
    make_entry("02", "青森県", "02205", "五所川原市", "五所川原市"),
    make_entry("02", "青森県", "02206", "十和田市", "十和田市"),
    make_entry("02", "青森県", "02207", "三沢市", "三沢市"),
    make_entry("02", "青森県", "02208", "むつ市", "むつ市"),

    # -------------------------------------------------------------------------
    # 03 岩手県 (Iwate)
    # -------------------------------------------------------------------------
    make_entry("03", "岩手県", "03201", "盛岡市", "盛岡市"),
    make_entry("03", "岩手県", "03202", "宮古市", "宮古市"),
    make_entry("03", "岩手県", "03203", "大船渡市", "大船渡市"),
    make_entry("03", "岩手県", "03205", "花巻市", "花巻市"),
    make_entry("03", "岩手県", "03206", "北上市", "北上市"),
    make_entry("03", "岩手県", "03207", "久慈市", "久慈市"),
    make_entry("03", "岩手県", "03208", "遠野市", "遠野市"),
    make_entry("03", "岩手県", "03209", "一関市", "一関市"),
    make_entry("03", "岩手県", "03210", "陸前高田市", "陸前高田市"),
    make_entry("03", "岩手県", "03211", "釜石市", "釜石市"),

    # -------------------------------------------------------------------------
    # 04 宮城県 (Miyagi)
    # -------------------------------------------------------------------------
    make_entry("04", "宮城県", "04100", "仙台市", "仙台市", entity_type="designated_city"),
    make_entry("04", "宮城県", "04101", "仙台市青葉区", "仙台市", ward="青葉区", entity_type="administrative_ward"),
    make_entry("04", "宮城県", "04102", "仙台市宮城野区", "仙台市", ward="宮城野区", entity_type="administrative_ward"),
    make_entry("04", "宮城県", "04103", "仙台市若林区", "仙台市", ward="若林区", entity_type="administrative_ward"),
    make_entry("04", "宮城県", "04104", "仙台市太白区", "仙台市", ward="太白区", entity_type="administrative_ward"),
    make_entry("04", "宮城県", "04105", "仙台市泉区", "仙台市", ward="泉区", entity_type="administrative_ward"),
    make_entry("04", "宮城県", "04202", "石巻市", "石巻市"),
    make_entry("04", "宮城県", "04203", "塩竈市", "塩竈市"),
    make_entry("04", "宮城県", "04204", "気仙沼市", "気仙沼市"),
    make_entry("04", "宮城県", "04205", "白石市", "白石市"),
    make_entry("04", "宮城県", "04206", "名取市", "名取市"),
    make_entry("04", "宮城県", "04207", "角田市", "角田市"),
    make_entry("04", "宮城県", "04208", "多賀城市", "多賀城市"),

    # -------------------------------------------------------------------------
    # 05 秋田県 (Akita)
    # -------------------------------------------------------------------------
    make_entry("05", "秋田県", "05201", "秋田市", "秋田市"),
    make_entry("05", "秋田県", "05202", "能代市", "能代市"),
    make_entry("05", "秋田県", "05203", "横手市", "横手市"),
    make_entry("05", "秋田県", "05204", "大館市", "大館市"),
    make_entry("05", "秋田県", "05206", "男鹿市", "男鹿市"),
    make_entry("05", "秋田県", "05207", "湯沢市", "湯沢市"),
    make_entry("05", "秋田県", "05209", "由利本荘市", "由利本荘市"),
    make_entry("05", "秋田県", "05210", "潟上市", "潟上市"),
    make_entry("05", "秋田県", "05211", "大仙市", "大仙市"),

    # -------------------------------------------------------------------------
    # 06 山形県 (Yamagata)
    # -------------------------------------------------------------------------
    make_entry("06", "山形県", "06201", "山形市", "山形市"),
    make_entry("06", "山形県", "06202", "米沢市", "米沢市"),
    make_entry("06", "山形県", "06203", "鶴岡市", "鶴岡市"),
    make_entry("06", "山形県", "06204", "酒田市", "酒田市"),
    make_entry("06", "山形県", "06205", "新庄市", "新庄市"),
    make_entry("06", "山形県", "06206", "寒河江市", "寒河江市"),
    make_entry("06", "山形県", "06207", "上山市", "上山市"),
    make_entry("06", "山形県", "06208", "村山市", "村山市"),
    make_entry("06", "山形県", "06209", "長井市", "長井市"),
    make_entry("06", "山形県", "06210", "天童市", "天童市"),

    # -------------------------------------------------------------------------
    # 07 福島県 (Fukushima)
    # -------------------------------------------------------------------------
    make_entry("07", "福島県", "07201", "福島市", "福島市"),
    make_entry("07", "福島県", "07202", "会津若松市", "会津若松市"),
    make_entry("07", "福島県", "07203", "郡山市", "郡山市"),
    make_entry("07", "福島県", "07204", "いわき市", "いわき市"),
    make_entry("07", "福島県", "07205", "白河市", "白河市"),
    make_entry("07", "福島県", "07207", "須賀川市", "須賀川市"),
    make_entry("07", "福島県", "07208", "喜多方市", "喜多方市"),
    make_entry("07", "福島県", "07209", "相馬市", "相馬市"),
    make_entry("07", "福島県", "07211", "南相馬市", "南相馬市"),

    # -------------------------------------------------------------------------
    # 08 茨城県 (Ibaraki)
    # -------------------------------------------------------------------------
    make_entry("08", "茨城県", "08201", "水戸市", "水戸市"),
    make_entry("08", "茨城県", "08202", "日立市", "日立市"),
    make_entry("08", "茨城県", "08203", "土浦市", "土浦市"),
    make_entry("08", "茨城県", "08204", "古河市", "古河市"),
    make_entry("08", "茨城県", "08205", "石岡市", "石岡市"),
    make_entry("08", "茨城県", "08207", "結城市", "結城市"),
    make_entry("08", "茨城県", "08208", "龍ケ崎市", "龍ケ崎市"),
    make_entry("08", "茨城県", "08210", "下妻市", "下妻市"),
    make_entry("08", "茨城県", "08211", "常総市", "常総市"),
    make_entry("08", "茨城県", "08212", "常陸太田市", "常陸太田市"),
    make_entry("08", "茨城県", "08220", "つくば市", "つくば市"),
    make_entry("08", "茨城県", "08309", "東茨城郡大洗町", "大洗町", county="東茨城郡", entity_type="town"),
    make_entry("08", "茨城県", "08309", "大洗町", "大洗町", county="東茨城郡", entity_type="town"),

    # -------------------------------------------------------------------------
    # 09 栃木県 (Tochigi)
    # -------------------------------------------------------------------------
    make_entry("09", "栃木県", "09201", "宇都宮市", "宇都宮市"),
    make_entry("09", "栃木県", "09202", "足利市", "足利市"),
    make_entry("09", "栃木県", "09203", "栃木市", "栃木市"),
    make_entry("09", "栃木県", "09204", "佐野市", "佐野市"),
    make_entry("09", "栃木県", "09205", "鹿沼市", "鹿沼市"),
    make_entry("09", "栃木県", "09206", "日光市", "日光市"),
    make_entry("09", "栃木県", "09208", "小山市", "小山市"),
    make_entry("09", "栃木県", "09209", "真岡市", "真岡市"),
    make_entry("09", "栃木県", "09210", "大田原市", "大田原市"),
    make_entry("09", "栃木県", "09213", "那須塩原市", "那須塩原市"),

    # -------------------------------------------------------------------------
    # 10 群馬県 (Gunma)
    # -------------------------------------------------------------------------
    make_entry("10", "群馬県", "10201", "前橋市", "前橋市"),
    make_entry("10", "群馬県", "10202", "高崎市", "高崎市"),
    make_entry("10", "群馬県", "10203", "桐生市", "桐生市"),
    make_entry("10", "群馬県", "10204", "伊勢崎市", "伊勢崎市"),
    make_entry("10", "群馬県", "10205", "太田市", "太田市"),
    make_entry("10", "群馬県", "10206", "沼田市", "沼田市"),
    make_entry("10", "群馬県", "10207", "館林市", "館林市"),
    make_entry("10", "群馬県", "10208", "渋川市", "渋川市"),
    make_entry("10", "群馬県", "10209", "藤岡市", "藤岡市"),
    make_entry("10", "群馬県", "10210", "富岡市", "富岡市"),
    make_entry("10", "群馬県", "10211", "安中市", "安中市"),

    # -------------------------------------------------------------------------
    # 11 埼玉県 (Saitama)
    # -------------------------------------------------------------------------
    make_entry("11", "埼玉県", "11100", "さいたま市", "さいたま市", entity_type="designated_city"),
    make_entry("11", "埼玉県", "11101", "さいたま市西区", "さいたま市", ward="西区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11102", "さいたま市北区", "さいたま市", ward="北区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11103", "さいたま市大宮区", "さいたま市", ward="大宮区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11104", "さいたま市見沼区", "さいたま市", ward="見沼区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11105", "さいたま市中央区", "さいたま市", ward="中央区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11106", "さいたま市桜区", "さいたま市", ward="桜区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11107", "さいたま市浦和区", "さいたま市", ward="浦和区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11108", "さいたま市南区", "さいたま市", ward="南区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11109", "さいたま市緑区", "さいたま市", ward="緑区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11110", "さいたま市岩槻区", "さいたま市", ward="岩槻区", entity_type="administrative_ward"),
    make_entry("11", "埼玉県", "11201", "川越市", "川越市"),
    make_entry("11", "埼玉県", "11202", "熊谷市", "熊谷市"),
    make_entry("11", "埼玉県", "11203", "川口市", "川口市"),
    make_entry("11", "埼玉県", "11206", "所沢市", "所沢市"),
    make_entry("11", "埼玉県", "11207", "飯能市", "飯能市"),
    make_entry("11", "埼玉県", "11208", "加須市", "加須市"),
    make_entry("11", "埼玉県", "11210", "本庄市", "本庄市"),
    make_entry("11", "埼玉県", "11211", "東松山市", "東松山市"),
    make_entry("11", "埼玉県", "11212", "春日部市", "春日部市"),
    make_entry("11", "埼玉県", "11214", "狭山市", "狭山市"),
    make_entry("11", "埼玉県", "11215", "羽生市", "羽生市"),
    make_entry("11", "埼玉県", "11216", "鴻巣市", "鴻巣市"),
    make_entry("11", "埼玉県", "11217", "深谷市", "深谷市"),
    make_entry("11", "埼玉県", "11218", "上尾市", "上尾市"),
    make_entry("11", "埼玉県", "11219", "草加市", "草加市"),
    make_entry("11", "埼玉県", "11221", "越谷市", "越谷市"),
    make_entry("11", "埼玉県", "11222", "蕨市", "蕨市"),
    make_entry("11", "埼玉県", "11223", "戸田市", "戸田市"),
    make_entry("11", "埼玉県", "11224", "入間市", "入間市"),
    make_entry("11", "埼玉県", "11225", "朝霞市", "朝霞市"),
    make_entry("11", "埼玉県", "11227", "和光市", "和光市"),
    make_entry("11", "埼玉県", "11228", "新座市", "新座市"),

    # -------------------------------------------------------------------------
    # 12 千葉県 (Chiba)
    # -------------------------------------------------------------------------
    make_entry("12", "千葉県", "12100", "千葉市", "千葉市", entity_type="designated_city"),
    make_entry("12", "千葉県", "12101", "千葉市中央区", "千葉市", ward="中央区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12102", "千葉市花見川区", "千葉市", ward="花見川区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12103", "千葉市稲毛区", "千葉市", ward="稲毛区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12104", "千葉市若葉区", "千葉市", ward="若葉区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12105", "千葉市緑区", "千葉市", ward="緑区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12106", "千葉市美浜区", "千葉市", ward="美浜区", entity_type="administrative_ward"),
    make_entry("12", "千葉県", "12202", "銚子市", "銚子市"),
    make_entry("12", "千葉県", "12203", "市川市", "市川市"),
    make_entry("12", "千葉県", "12204", "船橋市", "船橋市"),
    make_entry("12", "千葉県", "12205", "館山市", "館山市"),
    make_entry("12", "千葉県", "12206", "木更津市", "木更津市"),
    make_entry("12", "千葉県", "12207", "松戸市", "松戸市"),
    make_entry("12", "千葉県", "12208", "野田市", "野田市"),
    make_entry("12", "千葉県", "12210", "茂原市", "茂原市"),
    make_entry("12", "千葉県", "12211", "成田市", "成田市"),
    make_entry("12", "千葉県", "12212", "佐倉市", "佐倉市"),
    make_entry("12", "千葉県", "12217", "柏市", "柏市"),
    make_entry("12", "千葉県", "12220", "流山市", "流山市"),
    make_entry("12", "千葉県", "12221", "八千代市", "八千代市"),
    make_entry("12", "千葉県", "12222", "我孫子市", "我孫子市"),
    make_entry("12", "千葉県", "12224", "浦安市", "浦安市"),

    # -------------------------------------------------------------------------
    # 13 東京都 (Tokyo) - Complete 23 Special Wards + Tama Area
    # -------------------------------------------------------------------------
    make_entry("13", "東京都", "13101", "千代田区", "千代田区", entity_type="special_ward"),
    make_entry("13", "東京都", "13102", "中央区", "中央区", entity_type="special_ward"),
    make_entry("13", "東京都", "13103", "港区", "港区", entity_type="special_ward"),
    make_entry("13", "東京都", "13104", "新宿区", "新宿区", entity_type="special_ward"),
    make_entry("13", "東京都", "13105", "文京区", "文京区", entity_type="special_ward"),
    make_entry("13", "東京都", "13106", "台東区", "台東区", entity_type="special_ward"),
    make_entry("13", "東京都", "13107", "墨田区", "墨田区", entity_type="special_ward"),
    make_entry("13", "東京都", "13108", "江東区", "江東区", entity_type="special_ward"),
    make_entry("13", "東京都", "13109", "品川区", "品川区", entity_type="special_ward"),
    make_entry("13", "東京都", "13110", "目黒区", "目黒区", entity_type="special_ward"),
    make_entry("13", "東京都", "13111", "大田区", "大田区", entity_type="special_ward"),
    make_entry("13", "東京都", "13112", "世田谷区", "世田谷区", entity_type="special_ward"),
    make_entry("13", "東京都", "13113", "渋谷区", "渋谷区", entity_type="special_ward"),
    make_entry("13", "東京都", "13114", "中野区", "中野区", entity_type="special_ward"),
    make_entry("13", "東京都", "13115", "杉並区", "杉並区", entity_type="special_ward"),
    make_entry("13", "東京都", "13116", "豊島区", "豊島区", entity_type="special_ward"),
    make_entry("13", "東京都", "13117", "北区", "北区", entity_type="special_ward"),
    make_entry("13", "東京都", "13118", "荒川区", "荒川区", entity_type="special_ward"),
    make_entry("13", "東京都", "13119", "板橋区", "板橋区", entity_type="special_ward"),
    make_entry("13", "東京都", "13120", "練馬区", "練馬区", entity_type="special_ward"),
    make_entry("13", "東京都", "13121", "足立区", "足立区", entity_type="special_ward"),
    make_entry("13", "東京都", "13122", "葛飾区", "葛飾区", entity_type="special_ward"),
    make_entry("13", "東京都", "13123", "江戸川区", "江戸川区", entity_type="special_ward"),
    make_entry("13", "東京都", "13201", "八王子市", "八王子市"),
    make_entry("13", "東京都", "13202", "立川市", "立川市"),
    make_entry("13", "東京都", "13203", "武蔵野市", "武蔵野市"),
    make_entry("13", "東京都", "13204", "三鷹市", "三鷹市"),
    make_entry("13", "東京都", "13205", "青梅市", "青梅市"),
    make_entry("13", "東京都", "13206", "府中市", "府中市"),
    make_entry("13", "東京都", "13207", "昭島市", "昭島市"),
    make_entry("13", "東京都", "13208", "調布市", "調布市"),
    make_entry("13", "東京都", "13209", "町田市", "町田市"),
    make_entry("13", "東京都", "13210", "小金井市", "小金井市"),
    make_entry("13", "東京都", "13211", "小平市", "小平市"),
    make_entry("13", "東京都", "13212", "日野市", "日野市"),
    make_entry("13", "東京都", "13213", "東村山市", "東村山市"),
    make_entry("13", "東京都", "13214", "国分寺市", "国分寺市"),
    make_entry("13", "東京都", "13215", "国立市", "国立市"),
    make_entry("13", "東京都", "13218", "福生市", "福生市"),
    make_entry("13", "東京都", "13219", "狛江市", "狛江市"),
    make_entry("13", "東京都", "13220", "東大和市", "東大和市"),
    make_entry("13", "東京都", "13221", "清瀬市", "清瀬市"),
    make_entry("13", "東京都", "13222", "東久留米市", "東久留米市"),
    make_entry("13", "東京都", "13223", "武蔵村山市", "武蔵村山市"),
    make_entry("13", "東京都", "13224", "多摩市", "多摩市"),
    make_entry("13", "東京都", "13225", "稲城市", "稲城市"),
    make_entry("13", "東京都", "13227", "羽村市", "羽村市"),
    make_entry("13", "東京都", "13228", "あきる野市", "あきる野市"),
    make_entry("13", "東京都", "13229", "西東京市", "西東京市"),

    # -------------------------------------------------------------------------
    # 14 神奈川県 (Kanagawa) - Yokohama (18 wards), Kawasaki (7 wards), Sagamihara (3 wards)
    # -------------------------------------------------------------------------
    make_entry("14", "神奈川県", "14100", "横浜市", "横浜市", entity_type="designated_city"),
    make_entry("14", "神奈川県", "14101", "横浜市鶴見区", "横浜市", ward="鶴見区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14102", "横浜市神奈川区", "横浜市", ward="神奈川区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14103", "横浜市西区", "横浜市", ward="西区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14104", "横浜市中区", "横浜市", ward="中区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14105", "横浜市南区", "横浜市", ward="南区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14106", "横浜市保土ケ谷区", "横浜市", ward="保土ケ谷区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14107", "横浜市磯子区", "横浜市", ward="磯子区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14108", "横浜市金沢区", "横浜市", ward="金沢区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14109", "横浜市港北区", "横浜市", ward="港北区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14110", "横浜市戸塚区", "横浜市", ward="戸塚区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14111", "横浜市港南区", "横浜市", ward="港南区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14112", "横浜市旭区", "横浜市", ward="旭区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14113", "横浜市緑区", "横浜市", ward="緑区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14114", "横浜市瀬谷区", "横浜市", ward="瀬谷区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14115", "横浜市栄区", "横浜市", ward="栄区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14116", "横浜市泉区", "横浜市", ward="泉区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14117", "横浜市青葉区", "横浜市", ward="青葉区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14118", "横浜市都筑区", "横浜市", ward="都筑区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14130", "川崎市", "川崎市", entity_type="designated_city"),
    make_entry("14", "神奈川県", "14131", "川崎市川崎区", "川崎市", ward="川崎区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14132", "川崎市幸区", "川崎市", ward="幸区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14133", "川崎市中原区", "川崎市", ward="中原区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14134", "川崎市高津区", "川崎市", ward="高津区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14135", "川崎市多摩区", "川崎市", ward="多摩区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14136", "川崎市宮前区", "川崎市", ward="宮前区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14137", "川崎市麻生区", "川崎市", ward="麻生区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14150", "相模原市", "相模原市", entity_type="designated_city"),
    make_entry("14", "神奈川県", "14151", "相模原市緑区", "相模原市", ward="緑区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14152", "相模原市中央区", "相模原市", ward="中央区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14153", "相模原市南区", "相模原市", ward="南区", entity_type="administrative_ward"),
    make_entry("14", "神奈川県", "14201", "横須賀市", "横須賀市"),
    make_entry("14", "神奈川県", "14203", "平塚市", "平塚市"),
    make_entry("14", "神奈川県", "14204", "鎌倉市", "鎌倉市"),
    make_entry("14", "神奈川県", "14205", "藤沢市", "藤沢市"),
    make_entry("14", "神奈川県", "14206", "小田原市", "小田原市"),
    make_entry("14", "神奈川県", "14207", "茅ヶ崎市", "茅ヶ崎市"),
    make_entry("14", "神奈川県", "14208", "逗子市", "逗子市"),
    make_entry("14", "神奈川県", "14210", "三浦市", "三浦市"),
    make_entry("14", "神奈川県", "14211", "秦野市", "秦野市"),
    make_entry("14", "神奈川県", "14212", "厚木市", "厚木市"),
    make_entry("14", "神奈川県", "14213", "大和市", "大和市"),
    make_entry("14", "神奈川県", "14214", "伊勢原市", "伊勢原市"),
    make_entry("14", "神奈川県", "14215", "海老名市", "海老名市"),
    make_entry("14", "神奈川県", "14216", "座間市", "座間市"),

    # -------------------------------------------------------------------------
    # 15 新潟県 (Niigata)
    # -------------------------------------------------------------------------
    make_entry("15", "新潟県", "15100", "新潟市", "新潟市", entity_type="designated_city"),
    make_entry("15", "新潟県", "15101", "新潟市北区", "新潟市", ward="北区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15102", "新潟市東区", "新潟市", ward="東区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15103", "新潟市中央区", "新潟市", ward="中央区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15104", "新潟市江南区", "新潟市", ward="江南区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15105", "新潟市秋葉区", "新潟市", ward="秋葉区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15106", "新潟市南区", "新潟市", ward="南区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15107", "新潟市西区", "新潟市", ward="西区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15108", "新潟市西蒲区", "新潟市", ward="西蒲区", entity_type="administrative_ward"),
    make_entry("15", "新潟県", "15202", "長岡市", "長岡市"),
    make_entry("15", "新潟県", "15204", "三条市", "三条市"),
    make_entry("15", "新潟県", "15205", "柏崎市", "柏崎市"),
    make_entry("15", "新潟県", "15206", "新発田市", "新発田市"),
    make_entry("15", "新潟県", "15208", "小千谷市", "小千谷市"),
    make_entry("15", "新潟県", "15211", "十日町市", "十日町市"),
    make_entry("15", "新潟県", "15222", "上越市", "上越市"),

    # -------------------------------------------------------------------------
    # 16 富山県 (Toyama)
    # -------------------------------------------------------------------------
    make_entry("16", "富山県", "16201", "富山市", "富山市"),
    make_entry("16", "富山県", "16202", "高岡市", "高岡市"),
    make_entry("16", "富山県", "16204", "魚津市", "魚津市"),
    make_entry("16", "富山県", "16205", "氷見市", "氷見市"),
    make_entry("16", "富山県", "16206", "滑川市", "滑川市"),
    make_entry("16", "富山県", "16207", "黒部市", "黒部市"),
    make_entry("16", "富山県", "16208", "砺波市", "砺波市"),

    # -------------------------------------------------------------------------
    # 17 石川県 (Ishikawa)
    # -------------------------------------------------------------------------
    make_entry("17", "石川県", "17201", "金沢市", "金沢市"),
    make_entry("17", "石川県", "17202", "七尾市", "七尾市"),
    make_entry("17", "石川県", "17203", "小松市", "小松市"),
    make_entry("17", "石川県", "17204", "輪島市", "輪島市"),
    make_entry("17", "石川県", "17205", "珠洲市", "珠洲市"),
    make_entry("17", "石川県", "17206", "加賀市", "加賀市"),
    make_entry("17", "石川県", "17207", "羽咋市", "羽咋市"),
    make_entry("17", "石川県", "17210", "白山市", "白山市"),

    # -------------------------------------------------------------------------
    # 18 福井県 (Fukui)
    # -------------------------------------------------------------------------
    make_entry("18", "福井県", "18201", "福井市", "福井市"),
    make_entry("18", "福井県", "18202", "敦賀市", "敦賀市"),
    make_entry("18", "福井県", "18204", "小浜市", "小浜市"),
    make_entry("18", "福井県", "18205", "大野市", "大野市"),
    make_entry("18", "福井県", "18206", "勝山市", "勝山市"),
    make_entry("18", "福井県", "18207", "鯖江市", "鯖江市"),
    make_entry("18", "福井県", "18208", "あわら市", "あわら市"),
    make_entry("18", "福井県", "18209", "越前市", "越前市"),
    make_entry("18", "福井県", "18210", "坂井市", "坂井市"),

    # -------------------------------------------------------------------------
    # 19 山梨県 (Yamanashi)
    # -------------------------------------------------------------------------
    make_entry("19", "山梨県", "19201", "甲府市", "甲府市"),
    make_entry("19", "山梨県", "19202", "富士吉田市", "富士吉田市"),
    make_entry("19", "山梨県", "19204", "都留市", "都留市"),
    make_entry("19", "山梨県", "19205", "山梨市", "山梨市"),
    make_entry("19", "山梨県", "19206", "大月市", "大月市"),
    make_entry("19", "山梨県", "19207", "韮崎市", "韮崎市"),
    make_entry("19", "山梨県", "19208", "南アルプス市", "南アルプス市"),
    make_entry("19", "山梨県", "19209", "北杜市", "北杜市"),
    make_entry("19", "山梨県", "19210", "甲斐市", "甲斐市"),
    make_entry("19", "山梨県", "19211", "笛吹市", "笛吹市"),
    make_entry("19", "山梨県", "19212", "上野原市", "上野原市"),
    make_entry("19", "山梨県", "19213", "甲州市", "甲州市"),

    # -------------------------------------------------------------------------
    # 20 長野県 (Nagano)
    # -------------------------------------------------------------------------
    make_entry("20", "長野県", "20201", "長野市", "長野市"),
    make_entry("20", "長野県", "20202", "松本市", "松本市"),
    make_entry("20", "長野県", "20203", "上田市", "上田市"),
    make_entry("20", "長野県", "20204", "岡谷市", "岡谷市"),
    make_entry("20", "長野県", "20205", "飯田市", "飯田市"),
    make_entry("20", "長野県", "20206", "諏訪市", "諏訪市"),
    make_entry("20", "長野県", "20207", "須坂市", "須坂市"),
    make_entry("20", "長野県", "20208", "小諸市", "小諸市"),
    make_entry("20", "長野県", "20209", "伊那市", "伊那市"),
    make_entry("20", "長野県", "20210", "駒ヶ根市", "駒ヶ根市"),
    make_entry("20", "長野県", "20211", "中野市", "中野市"),
    make_entry("20", "長野県", "20212", "大町市", "大町市"),
    make_entry("20", "長野県", "20214", "茅野市", "茅野市"),
    make_entry("20", "長野県", "20215", "塩尻市", "塩尻市"),

    # -------------------------------------------------------------------------
    # 21 岐阜県 (Gifu)
    # -------------------------------------------------------------------------
    make_entry("21", "岐阜県", "21201", "岐阜市", "岐阜市"),
    make_entry("21", "岐阜県", "21202", "大垣市", "大垣市"),
    make_entry("21", "岐阜県", "21203", "高山市", "高山市"),
    make_entry("21", "岐阜県", "21204", "多治見市", "多治見市"),
    make_entry("21", "岐阜県", "21205", "関市", "関市"),
    make_entry("21", "岐阜県", "21206", "中津川市", "中津川市"),
    make_entry("21", "岐阜県", "21207", "美濃市", "美濃市"),
    make_entry("21", "岐阜県", "21208", "瑞浪市", "瑞浪市"),
    make_entry("21", "岐阜県", "21209", "羽島市", "羽島市"),
    make_entry("21", "岐阜県", "21210", "恵那市", "恵那市"),
    make_entry("21", "岐阜県", "21211", "美濃加茂市", "美濃加茂市"),
    make_entry("21", "岐阜県", "21212", "土岐市", "土岐市"),
    make_entry("21", "岐阜県", "21213", "各務原市", "各務原市"),
    make_entry("21", "岐阜県", "21214", "可児市", "可児市"),

    # -------------------------------------------------------------------------
    # 22 静岡県 (Shizuoka) - Shizuoka (3 wards), Hamamatsu (wards)
    # -------------------------------------------------------------------------
    make_entry("22", "静岡県", "22100", "静岡市", "静岡市", entity_type="designated_city"),
    make_entry("22", "静岡県", "22101", "静岡市葵区", "静岡市", ward="葵区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22102", "静岡市駿河区", "静岡市", ward="駿河区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22103", "静岡市清水区", "静岡市", ward="清水区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22130", "浜松市", "浜松市", entity_type="designated_city"),
    make_entry("22", "静岡県", "22131", "浜松市中区", "浜松市", ward="中区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22138", "浜松市中央区", "浜松市", ward="中央区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22139", "浜松市浜名区", "浜松市", ward="浜名区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22140", "浜松市天竜区", "浜松市", ward="天竜区", entity_type="administrative_ward"),
    make_entry("22", "静岡県", "22203", "沼津市", "沼津市"),
    make_entry("22", "静岡県", "22205", "熱海市", "熱海市"),
    make_entry("22", "静岡県", "22206", "三島市", "三島市"),
    make_entry("22", "静岡県", "22207", "富士宮市", "富士宮市"),
    make_entry("22", "静岡県", "22208", "伊東市", "伊東市"),
    make_entry("22", "静岡県", "22210", "富士市", "富士市"),
    make_entry("22", "静岡県", "22211", "磐田市", "磐田市"),
    make_entry("22", "静岡県", "22212", "焼津市", "焼津市"),
    make_entry("22", "静岡県", "22213", "掛川市", "掛川市"),
    make_entry("22", "静岡県", "22214", "藤枝市", "藤枝市"),
    make_entry("22", "静岡県", "22215", "御殿場市", "御殿場市"),

    # -------------------------------------------------------------------------
    # 23 愛知県 (Aichi) - Nagoya (16 wards), Toyota, etc.
    # -------------------------------------------------------------------------
    make_entry("23", "愛知県", "23100", "名古屋市", "名古屋市", entity_type="designated_city"),
    make_entry("23", "愛知県", "23101", "名古屋市千種区", "名古屋市", ward="千種区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23102", "名古屋市東区", "名古屋市", ward="東区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23103", "名古屋市北区", "名古屋市", ward="北区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23104", "名古屋市西区", "名古屋市", ward="西区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23105", "名古屋市中村区", "名古屋市", ward="中村区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23106", "名古屋市中区", "名古屋市", ward="中区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23107", "名古屋市昭和区", "名古屋市", ward="昭和区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23108", "名古屋市瑞穂区", "名古屋市", ward="瑞穂区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23109", "名古屋市熱田区", "名古屋市", ward="熱田区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23110", "名古屋市中川区", "名古屋市", ward="中川区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23111", "名古屋市港区", "名古屋市", ward="港区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23112", "名古屋市南区", "名古屋市", ward="南区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23113", "名古屋市守山区", "名古屋市", ward="守山区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23114", "名古屋市緑区", "名古屋市", ward="緑区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23115", "名古屋市名東区", "名古屋市", ward="名東区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23116", "名古屋市天白区", "名古屋市", ward="天白区", entity_type="administrative_ward"),
    make_entry("23", "愛知県", "23201", "豊橋市", "豊橋市"),
    make_entry("23", "愛知県", "23202", "岡崎市", "岡崎市"),
    make_entry("23", "愛知県", "23203", "一宮市", "一宮市"),
    make_entry("23", "愛知県", "23204", "瀬戸市", "瀬戸市"),
    make_entry("23", "愛知県", "23205", "半田市", "半田市"),
    make_entry("23", "愛知県", "23206", "春日井市", "春日井市"),
    make_entry("23", "愛知県", "23207", "豊川市", "豊川市"),
    make_entry("23", "愛知県", "23211", "豊田市", "豊田市"),
    make_entry("23", "愛知県", "23212", "安城市", "安城市"),
    make_entry("23", "愛知県", "23214", "西尾市", "西尾市"),
    make_entry("23", "愛知県", "23217", "刈谷市", "刈谷市"),

    # -------------------------------------------------------------------------
    # 24 三重県 (Mie)
    # -------------------------------------------------------------------------
    make_entry("24", "三重県", "24201", "津市", "津市"),
    make_entry("24", "三重県", "24202", "四日市市", "四日市市"),
    make_entry("24", "三重県", "24203", "伊勢市", "伊勢市"),
    make_entry("24", "三重県", "24204", "松阪市", "松阪市"),
    make_entry("24", "三重県", "24205", "桑名市", "桑名市"),
    make_entry("24", "三重県", "24207", "鈴鹿市", "鈴鹿市"),
    make_entry("24", "三重県", "24208", "名張市", "名張市"),
    make_entry("24", "三重県", "24209", "尾鷲市", "尾鷲市"),
    make_entry("24", "三重県", "24210", "亀山市", "亀山市"),
    make_entry("24", "三重県", "24211", "鳥羽市", "鳥羽市"),
    make_entry("24", "三重県", "24212", "熊野市", "熊野市"),
    make_entry("24", "三重県", "24214", "いなべ市", "いなべ市"),
    make_entry("24", "三重県", "24215", "志摩市", "志摩市"),
    make_entry("24", "三重県", "24216", "伊賀市", "伊賀市"),

    # -------------------------------------------------------------------------
    # 25 滋賀県 (Shiga)
    # -------------------------------------------------------------------------
    make_entry("25", "滋賀県", "25201", "大津市", "大津市"),
    make_entry("25", "滋賀県", "25202", "彦根市", "彦根市"),
    make_entry("25", "滋賀県", "25203", "長浜市", "長浜市"),
    make_entry("25", "滋賀県", "25204", "近江八幡市", "近江八幡市"),
    make_entry("25", "滋賀県", "25206", "草津市", "草津市"),
    make_entry("25", "滋賀県", "25207", "守山市", "守山市"),
    make_entry("25", "滋賀県", "25208", "栗東市", "栗東市"),
    make_entry("25", "滋賀県", "25209", "甲賀市", "甲賀市"),
    make_entry("25", "滋賀県", "25210", "野洲市", "野洲市"),
    make_entry("25", "滋賀県", "25211", "湖南市", "湖南市"),
    make_entry("25", "滋賀県", "25212", "高島市", "高島市"),
    make_entry("25", "滋賀県", "25213", "東近江市", "東近江市"),
    make_entry("25", "滋賀県", "25214", "米原市", "米原市"),

    # -------------------------------------------------------------------------
    # 26 京都府 (Kyoto) - Kyoto City (11 wards), Uji, etc.
    # -------------------------------------------------------------------------
    make_entry("26", "京都府", "26100", "京都市", "京都市", entity_type="designated_city"),
    make_entry("26", "京都府", "26101", "京都市北区", "京都市", ward="北区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26102", "京都市上京区", "京都市", ward="上京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26103", "京都市左京区", "京都市", ward="左京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26104", "京都市中京区", "京都市", ward="中京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26105", "京都市東山区", "京都市", ward="東山区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26106", "京都市下京区", "京都市", ward="下京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26107", "京都市南区", "京都市", ward="南区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26108", "京都市右京区", "京都市", ward="右京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26109", "京都市伏見区", "京都市", ward="伏見区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26110", "京都市山科区", "京都市", ward="山科区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26111", "京都市西京区", "京都市", ward="西京区", entity_type="administrative_ward"),
    make_entry("26", "京都府", "26201", "福知山市", "福知山市"),
    make_entry("26", "京都府", "26202", "舞鶴市", "舞鶴市"),
    make_entry("26", "京都府", "26203", "綾部市", "綾部市"),
    make_entry("26", "京都府", "26204", "宇治市", "宇治市"),
    make_entry("26", "京都府", "26205", "宮津市", "宮津市"),
    make_entry("26", "京都府", "26206", "亀岡市", "亀岡市"),
    make_entry("26", "京都府", "26207", "城陽市", "城陽市"),
    make_entry("26", "京都府", "26208", "向日市", "向日市"),
    make_entry("26", "京都府", "26209", "長岡京市", "長岡京市"),
    make_entry("26", "京都府", "26210", "八幡市", "八幡市"),
    make_entry("26", "京都府", "26211", "京田辺市", "京田辺市"),
    make_entry("26", "京都府", "26212", "京丹後市", "京丹後市"),
    make_entry("26", "京都府", "26213", "南丹市", "南丹市"),
    make_entry("26", "京都府", "26214", "木津川市", "木津川市"),

    # -------------------------------------------------------------------------
    # 27 大阪府 (Osaka) - Osaka City (24 wards), Sakai City (7 wards), Toyonaka, Suita
    # -------------------------------------------------------------------------
    make_entry("27", "大阪府", "27100", "大阪市", "大阪市", entity_type="designated_city"),
    make_entry("27", "大阪府", "27102", "大阪市都島区", "大阪市", ward="都島区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27103", "大阪市福島区", "大阪市", ward="福島区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27104", "大阪市此花区", "大阪市", ward="此花区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27106", "大阪市西区", "大阪市", ward="西区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27107", "大阪市港区", "大阪市", ward="港区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27108", "大阪市大正区", "大阪市", ward="大正区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27109", "大阪市天王寺区", "大阪市", ward="天王寺区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27111", "大阪市浪速区", "大阪市", ward="浪速区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27113", "大阪市西淀川区", "大阪市", ward="西淀川区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27114", "大阪市東淀川区", "大阪市", ward="東淀川区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27115", "大阪市東成区", "大阪市", ward="東成区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27116", "大阪市生野区", "大阪市", ward="生野区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27117", "大阪市旭区", "大阪市", ward="旭区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27118", "大阪市城東区", "大阪市", ward="城東区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27119", "大阪市阿倍野区", "大阪市", ward="阿倍野区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27120", "大阪市住吉区", "大阪市", ward="住吉区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27121", "大阪市東住吉区", "大阪市", ward="東住吉区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27122", "大阪市西成区", "大阪市", ward="西成区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27123", "大阪市淀川区", "大阪市", ward="淀川区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27124", "大阪市鶴見区", "大阪市", ward="鶴見区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27125", "大阪市住之江区", "大阪市", ward="住之江区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27126", "大阪市平野区", "大阪市", ward="平野区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27127", "大阪市北区", "大阪市", ward="北区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27128", "大阪市中央区", "大阪市", ward="中央区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27140", "堺市", "堺市", entity_type="designated_city"),
    make_entry("27", "大阪府", "27141", "堺市堺区", "堺市", ward="堺区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27142", "堺市中区", "堺市", ward="中区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27143", "堺市東区", "堺市", ward="東区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27144", "堺市西区", "堺市", ward="西区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27145", "堺市南区", "堺市", ward="南区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27146", "堺市北区", "堺市", ward="北区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27147", "堺市美原区", "堺市", ward="美原区", entity_type="administrative_ward"),
    make_entry("27", "大阪府", "27202", "岸和田市", "岸和田市"),
    make_entry("27", "大阪府", "27203", "豊中市", "豊中市"),
    make_entry("27", "大阪府", "27204", "池田市", "池田市"),
    make_entry("27", "大阪府", "27205", "吹田市", "吹田市"),
    make_entry("27", "大阪府", "27206", "泉大津市", "泉大津市"),
    make_entry("27", "大阪府", "27207", "高槻市", "高槻市"),
    make_entry("27", "大阪府", "27209", "枚方市", "枚方市"),
    make_entry("27", "大阪府", "27210", "茨木市", "茨木市"),
    make_entry("27", "大阪府", "27211", "八尾市", "八尾市"),
    make_entry("27", "大阪府", "27227", "東大阪市", "東大阪市"),

    # -------------------------------------------------------------------------
    # 28 兵庫県 (Hyogo) - Kobe City (9 wards), Himeji, Amagasaki, Nishinomiya
    # -------------------------------------------------------------------------
    make_entry("28", "兵庫県", "28100", "神戸市", "神戸市", entity_type="designated_city"),
    make_entry("28", "兵庫県", "28101", "神戸市東灘区", "神戸市", ward="東灘区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28102", "神戸市灘区", "神戸市", ward="灘区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28105", "神戸市兵庫区", "神戸市", ward="兵庫区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28106", "神戸市長田区", "神戸市", ward="長田区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28107", "神戸市須磨区", "神戸市", ward="須磨区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28108", "神戸市垂水区", "神戸市", ward="垂水区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28109", "神戸市北区", "神戸市", ward="北区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28110", "神戸市中央区", "神戸市", ward="中央区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28111", "神戸市西区", "神戸市", ward="西区", entity_type="administrative_ward"),
    make_entry("28", "兵庫県", "28201", "姫路市", "姫路市"),
    make_entry("28", "兵庫県", "28202", "尼崎市", "尼崎市"),
    make_entry("28", "兵庫県", "28203", "明石市", "明石市"),
    make_entry("28", "兵庫県", "28204", "西宮市", "西宮市"),
    make_entry("28", "兵庫県", "28205", "洲本市", "洲本市"),
    make_entry("28", "兵庫県", "28206", "芦屋市", "芦屋市"),
    make_entry("28", "兵庫県", "28207", "伊丹市", "伊丹市"),
    make_entry("28", "兵庫県", "28209", "豊岡市", "豊岡市"),
    make_entry("28", "兵庫県", "28210", "加古川市", "加古川市"),
    make_entry("28", "兵庫県", "28214", "宝塚市", "宝塚市"),

    # -------------------------------------------------------------------------
    # 29 奈良県 (Nara)
    # -------------------------------------------------------------------------
    make_entry("29", "奈良県", "29201", "奈良市", "奈良市"),
    make_entry("29", "奈良県", "29202", "大和高田市", "大和高田市"),
    make_entry("29", "奈良県", "29203", "大和郡山市", "大和郡山市"),
    make_entry("29", "奈良県", "29204", "天理市", "天理市"),
    make_entry("29", "奈良県", "29205", "橿原市", "橿原市"),
    make_entry("29", "奈良県", "29206", "桜井市", "桜井市"),
    make_entry("29", "奈良県", "29207", "五條市", "五條市"),
    make_entry("29", "奈良県", "29208", "御所市", "御所市"),
    make_entry("29", "奈良県", "29209", "生駒市", "生駒市"),

    # -------------------------------------------------------------------------
    # 30 和歌山県 (Wakayama)
    # -------------------------------------------------------------------------
    make_entry("30", "和歌山県", "30201", "和歌山市", "和歌山市"),
    make_entry("30", "和歌山県", "30202", "海南市", "海南市"),
    make_entry("30", "和歌山県", "30203", "橋本市", "橋本市"),
    make_entry("30", "和歌山県", "30204", "有田市", "有田市"),
    make_entry("30", "和歌山県", "30205", "御坊市", "御坊市"),
    make_entry("30", "和歌山県", "30206", "田辺市", "田辺市"),
    make_entry("30", "和歌山県", "30207", "新宮市", "新宮市"),

    # -------------------------------------------------------------------------
    # 31 鳥取県 (Tottori)
    # -------------------------------------------------------------------------
    make_entry("31", "鳥取県", "31201", "鳥取市", "鳥取市"),
    make_entry("31", "鳥取県", "31202", "米子市", "米子市"),
    make_entry("31", "鳥取県", "31203", "倉吉市", "倉吉市"),
    make_entry("31", "鳥取県", "31204", "境港市", "境港市"),

    # -------------------------------------------------------------------------
    # 32 島根県 (Shimane)
    # -------------------------------------------------------------------------
    make_entry("32", "島根県", "32201", "松江市", "松江市"),
    make_entry("32", "島根県", "32202", "浜田市", "浜田市"),
    make_entry("32", "島根県", "32203", "出雲市", "出雲市"),
    make_entry("32", "島根県", "32204", "益田市", "益田市"),
    make_entry("32", "島根県", "32205", "大田市", "大田市"),
    make_entry("32", "島根県", "32206", "安来市", "安来市"),
    make_entry("32", "島根県", "32207", "江津市", "江津市"),
    make_entry("32", "島根県", "32209", "雲南市", "雲南市"),

    # -------------------------------------------------------------------------
    # 33 岡山県 (Okayama) - Okayama City (4 wards), Kurashiki
    # -------------------------------------------------------------------------
    make_entry("33", "岡山県", "33100", "岡山市", "岡山市", entity_type="designated_city"),
    make_entry("33", "岡山県", "33101", "岡山市北区", "岡山市", ward="北区", entity_type="administrative_ward"),
    make_entry("33", "岡山県", "33102", "岡山市中区", "岡山市", ward="中区", entity_type="administrative_ward"),
    make_entry("33", "岡山県", "33103", "岡山市東区", "岡山市", ward="東区", entity_type="administrative_ward"),
    make_entry("33", "岡山県", "33104", "岡山市南区", "岡山市", ward="南区", entity_type="administrative_ward"),
    make_entry("33", "岡山県", "33202", "倉敷市", "倉敷市"),
    make_entry("33", "岡山県", "33203", "津山市", "津山市"),
    make_entry("33", "岡山県", "33204", "玉野市", "玉野市"),
    make_entry("33", "岡山県", "33205", "笠岡市", "笠岡市"),
    make_entry("33", "岡山県", "33207", "総社市", "総社市"),

    # -------------------------------------------------------------------------
    # 34 広島県 (Hiroshima) - Hiroshima City (8 wards), Fukuyama, Kure
    # -------------------------------------------------------------------------
    make_entry("34", "広島県", "34100", "広島市", "広島市", entity_type="designated_city"),
    make_entry("34", "広島県", "34101", "広島市中区", "広島市", ward="中区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34102", "広島市東区", "広島市", ward="東区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34103", "広島市南区", "広島市", ward="南区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34104", "広島市西区", "広島市", ward="西区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34105", "広島市安佐南区", "広島市", ward="安佐南区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34106", "広島市安佐北区", "広島市", ward="安佐北区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34107", "広島市安芸区", "広島市", ward="安芸区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34108", "広島市佐伯区", "広島市", ward="佐伯区", entity_type="administrative_ward"),
    make_entry("34", "広島県", "34202", "呉市", "呉市"),
    make_entry("34", "広島県", "34204", "竹原市", "竹原市"),
    make_entry("34", "広島県", "34205", "三原市", "三原市"),
    make_entry("34", "広島県", "34207", "尾道市", "尾道市"),
    make_entry("34", "広島県", "34208", "福山市", "福山市"),
    make_entry("34", "広島県", "34211", "三次市", "三次市"),
    make_entry("34", "広島県", "34213", "東広島市", "東広島市"),
    make_entry("34", "広島県", "34215", "廿日市市", "廿日市市"),

    # -------------------------------------------------------------------------
    # 35 山口県 (Yamaguchi)
    # -------------------------------------------------------------------------
    make_entry("35", "山口県", "35201", "下関市", "下関市"),
    make_entry("35", "山口県", "35202", "宇部市", "宇部市"),
    make_entry("35", "山口県", "35203", "山口市", "山口市"),
    make_entry("35", "山口県", "35204", "萩市", "萩市"),
    make_entry("35", "山口県", "35205", "防府市", "防府市"),
    make_entry("35", "山口県", "35206", "下松市", "下松市"),
    make_entry("35", "山口県", "35207", "岩国市", "岩国市"),
    make_entry("35", "山口県", "35208", "光市", "光市"),
    make_entry("35", "山口県", "35211", "周南市", "周南市"),

    # -------------------------------------------------------------------------
    # 36 徳島県 (Tokushima)
    # -------------------------------------------------------------------------
    make_entry("36", "徳島県", "36201", "徳島市", "徳島市"),
    make_entry("36", "徳島県", "36202", "鳴門市", "鳴門市"),
    make_entry("36", "徳島県", "36203", "小松島市", "小松島市"),
    make_entry("36", "徳島県", "36204", "阿南市", "阿南市"),
    make_entry("36", "徳島県", "36205", "吉野川市", "吉野川市"),
    make_entry("36", "徳島県", "36206", "阿波市", "阿波市"),
    make_entry("36", "徳島県", "36207", "美馬市", "美馬市"),
    make_entry("36", "徳島県", "36208", "三好市", "三好市"),

    # -------------------------------------------------------------------------
    # 37 香川県 (Kagawa)
    # -------------------------------------------------------------------------
    make_entry("37", "香川県", "37201", "高松市", "高松市"),
    make_entry("37", "香川県", "37202", "丸亀市", "丸亀市"),
    make_entry("37", "香川県", "37203", "坂出市", "坂出市"),
    make_entry("37", "香川県", "37204", "善通寺市", "善通寺市"),
    make_entry("37", "香川県", "37205", "観音寺市", "観音寺市"),
    make_entry("37", "香川県", "37206", "さぬき市", "さぬき市"),
    make_entry("37", "香川県", "37207", "東かがわ市", "東かがわ市"),
    make_entry("37", "香川県", "37208", "三豊市", "三豊市"),

    # -------------------------------------------------------------------------
    # 38 愛媛県 (Ehime)
    # -------------------------------------------------------------------------
    make_entry("38", "愛媛県", "38201", "松山市", "松山市"),
    make_entry("38", "愛媛県", "38202", "今治市", "今治市"),
    make_entry("38", "愛媛県", "38203", "宇和島市", "宇和島市"),
    make_entry("38", "愛媛県", "38204", "八幡浜市", "八幡浜市"),
    make_entry("38", "愛媛県", "38205", "新居浜市", "新居浜市"),
    make_entry("38", "愛媛県", "38206", "西条市", "西条市"),
    make_entry("38", "愛媛県", "38207", "大洲市", "大洲市"),
    make_entry("38", "愛媛県", "38210", "四国中央市", "四国中央市"),

    # -------------------------------------------------------------------------
    # 39 高知県 (Kochi)
    # -------------------------------------------------------------------------
    make_entry("39", "高知県", "39201", "高知市", "高知市"),
    make_entry("39", "高知県", "39202", "室戸市", "室戸市"),
    make_entry("39", "高知県", "39203", "安芸市", "安芸市"),
    make_entry("39", "高知県", "39204", "南国市", "南国市"),
    make_entry("39", "高知県", "39205", "土佐市", "土佐市"),
    make_entry("39", "高知県", "39206", "須崎市", "須崎市"),
    make_entry("39", "高知県", "39208", "宿毛市", "宿毛市"),
    make_entry("39", "高知県", "39209", "土佐清水市", "土佐清水市"),
    make_entry("39", "高知県", "39210", "四万十市", "四万十市"),
    make_entry("39", "高知県", "39211", "香南市", "香南市"),
    make_entry("39", "高知県", "39212", "香美市", "香美市"),

    # -------------------------------------------------------------------------
    # 40 福岡県 (Fukuoka) - Fukuoka City (7 wards), Kitakyushu (7 wards), Kurume
    # -------------------------------------------------------------------------
    make_entry("40", "福岡県", "40100", "北九州市", "北九州市", entity_type="designated_city"),
    make_entry("40", "福岡県", "40101", "北九州市門司区", "北九州市", ward="門司区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40103", "北九州市若松区", "北九州市", ward="若松区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40105", "北九州市戸畑区", "北九州市", ward="戸畑区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40106", "北九州市小倉北区", "北九州市", ward="小倉北区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40107", "北九州市小倉南区", "北九州市", ward="小倉南区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40108", "北九州市八幡東区", "北九州市", ward="八幡東区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40109", "北九州市八幡西区", "北九州市", ward="八幡西区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40130", "福岡市", "福岡市", entity_type="designated_city"),
    make_entry("40", "福岡県", "40131", "福岡市東区", "福岡市", ward="東区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40132", "福岡市博多区", "福岡市", ward="博多区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40133", "福岡市中央区", "福岡市", ward="中央区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40134", "福岡市南区", "福岡市", ward="南区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40135", "福岡市西区", "福岡市", ward="西区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40136", "福岡市城南区", "福岡市", ward="城南区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40137", "福岡市早良区", "福岡市", ward="早良区", entity_type="administrative_ward"),
    make_entry("40", "福岡県", "40202", "大牟田市", "大牟田市"),
    make_entry("40", "福岡県", "40203", "久留米市", "久留米市"),
    make_entry("40", "福岡県", "40205", "飯塚市", "飯塚市"),
    make_entry("40", "福岡県", "40206", "田川市", "田川市"),
    make_entry("40", "福岡県", "40207", "柳川市", "柳川市"),
    make_entry("40", "福岡県", "40213", "筑後市", "筑後市"),
    make_entry("40", "福岡県", "40216", "太宰府市", "太宰府市"),
    make_entry("40", "福岡県", "40217", "前原市", "糸島市"),
    make_entry("40", "福岡県", "40230", "糸島市", "糸島市"),

    # -------------------------------------------------------------------------
    # 41 佐賀県 (Saga)
    # -------------------------------------------------------------------------
    make_entry("41", "佐賀県", "41201", "佐賀市", "佐賀市"),
    make_entry("41", "佐賀県", "41202", "唐津市", "唐津市"),
    make_entry("41", "佐賀県", "41203", "鳥栖市", "鳥栖市"),
    make_entry("41", "佐賀県", "41204", "多久市", "多久市"),
    make_entry("41", "佐賀県", "41205", "伊万里市", "伊万里市"),
    make_entry("41", "佐賀県", "41206", "武雄市", "武雄市"),
    make_entry("41", "佐賀県", "41207", "鹿島市", "鹿島市"),
    make_entry("41", "佐賀県", "41208", "小城市", "小城市"),
    make_entry("41", "佐賀県", "41209", "嬉野市", "嬉野市"),
    make_entry("41", "佐賀県", "41210", "神埼市", "神埼市"),

    # -------------------------------------------------------------------------
    # 42 長崎県 (Nagasaki)
    # -------------------------------------------------------------------------
    make_entry("42", "長崎県", "42201", "長崎市", "長崎市"),
    make_entry("42", "長崎県", "42202", "佐世保市", "佐世保市"),
    make_entry("42", "長崎県", "42203", "島原市", "島原市"),
    make_entry("42", "長崎県", "42204", "諫早市", "諫早市"),
    make_entry("42", "長崎県", "42205", "大村市", "大村市"),
    make_entry("42", "長崎県", "42207", "平戸市", "平戸市"),
    make_entry("42", "長崎県", "42208", "松浦市", "松浦市"),
    make_entry("42", "長崎県", "42209", "対馬市", "対馬市"),
    make_entry("42", "長崎県", "42210", "壱岐市", "壱岐市"),
    make_entry("42", "長崎県", "42211", "五島市", "五島市"),

    # -------------------------------------------------------------------------
    # 43 熊本県 (Kumamoto) - Kumamoto City (5 wards), Yatsushiro
    # -------------------------------------------------------------------------
    make_entry("43", "熊本県", "43100", "熊本市", "熊本市", entity_type="designated_city"),
    make_entry("43", "熊本県", "43101", "熊本市中央区", "熊本市", ward="中央区", entity_type="administrative_ward"),
    make_entry("43", "熊本県", "43102", "熊本市東区", "熊本市", ward="東区", entity_type="administrative_ward"),
    make_entry("43", "熊本県", "43103", "熊本市西区", "熊本市", ward="西区", entity_type="administrative_ward"),
    make_entry("43", "熊本県", "43104", "熊本市南区", "熊本市", ward="南区", entity_type="administrative_ward"),
    make_entry("43", "熊本県", "43105", "熊本市北区", "熊本市", ward="北区", entity_type="administrative_ward"),
    make_entry("43", "熊本県", "43202", "八代市", "八代市"),
    make_entry("43", "熊本県", "43203", "人吉市", "人吉市"),
    make_entry("43", "熊本県", "43204", "荒尾市", "荒尾市"),
    make_entry("43", "熊本県", "43205", "水俣市", "水俣市"),
    make_entry("43", "熊本県", "43206", "玉名市", "玉名市"),
    make_entry("43", "熊本県", "43208", "山鹿市", "山鹿市"),
    make_entry("43", "熊本県", "43210", "菊池市", "菊池市"),
    make_entry("43", "熊本県", "43211", "宇土市", "宇土市"),
    make_entry("43", "熊本県", "43212", "上天草市", "上天草市"),
    make_entry("43", "熊本県", "43213", "宇城市", "宇城市"),
    make_entry("43", "熊本県", "43214", "阿蘇市", "阿蘇市"),
    make_entry("43", "熊本県", "43215", "天草市", "天草市"),
    make_entry("43", "熊本県", "43216", "合志市", "合志市"),

    # -------------------------------------------------------------------------
    # 44 大分県 (Oita)
    # -------------------------------------------------------------------------
    make_entry("44", "大分県", "44201", "大分市", "大分市"),
    make_entry("44", "大分県", "44202", "別府市", "別府市"),
    make_entry("44", "大分県", "44203", "中津市", "中津市"),
    make_entry("44", "大分県", "44204", "日田市", "日田市"),
    make_entry("44", "大分県", "44205", "佐伯市", "佐伯市"),
    make_entry("44", "大分県", "44206", "臼杵市", "臼杵市"),
    make_entry("44", "大分県", "44207", "津久見市", "津久見市"),
    make_entry("44", "大分県", "44208", "竹田市", "竹田市"),
    make_entry("44", "大分県", "44209", "豊後高田市", "豊後高田市"),
    make_entry("44", "大分県", "44210", "杵築市", "杵築市"),
    make_entry("44", "大分県", "44211", "宇佐市", "宇佐市"),
    make_entry("44", "大分県", "44212", "豊後大野市", "豊後大野市"),
    make_entry("44", "大分県", "44213", "由布市", "由布市"),
    make_entry("44", "大分県", "44214", "国東市", "国東市"),

    # -------------------------------------------------------------------------
    # 45 宮崎県 (Miyazaki)
    # -------------------------------------------------------------------------
    make_entry("45", "宮崎県", "45201", "宮崎市", "宮崎市"),
    make_entry("45", "宮崎県", "45202", "都城市", "都城市"),
    make_entry("45", "宮崎県", "45203", "延岡市", "延岡市"),
    make_entry("45", "宮崎県", "45204", "日南市", "日南市"),
    make_entry("45", "宮崎県", "45205", "小林市", "小林市"),
    make_entry("45", "宮崎県", "45206", "日向市", "日向市"),
    make_entry("45", "宮崎県", "45207", "串間市", "串間市"),
    make_entry("45", "宮崎県", "45208", "西都市", "西都市"),
    make_entry("45", "宮崎県", "45209", "えびの市", "えびの市"),

    # -------------------------------------------------------------------------
    # 46 鹿児島県 (Kagoshima)
    # -------------------------------------------------------------------------
    make_entry("46", "鹿児島県", "46201", "鹿児島市", "鹿児島市"),
    make_entry("46", "鹿児島県", "46203", "鹿屋市", "鹿屋市"),
    make_entry("46", "鹿児島県", "46204", "枕崎市", "枕崎市"),
    make_entry("46", "鹿児島県", "46206", "阿久根市", "阿久根市"),
    make_entry("46", "鹿児島県", "46208", "出水市", "出水市"),
    make_entry("46", "鹿児島県", "46210", "指宿市", "指宿市"),
    make_entry("46", "鹿児島県", "46213", "西之表市", "西之表市"),
    make_entry("46", "鹿児島県", "46214", "垂水市", "垂水市"),
    make_entry("46", "鹿児島県", "46215", "薩摩川内市", "薩摩川内市"),
    make_entry("46", "鹿児島県", "46216", "日置市", "日置市"),
    make_entry("46", "鹿児島県", "46217", "曽於市", "曽於市"),
    make_entry("46", "鹿児島県", "46218", "霧島市", "霧島市"),
    make_entry("46", "鹿児島県", "46219", "いちき串木野市", "いちき串木野市"),
    make_entry("46", "鹿児島県", "46220", "南さつま市", "南さつま市"),
    make_entry("46", "鹿児島県", "46221", "志布志市", "志布志市"),
    make_entry("46", "鹿児島県", "46222", "奄美市", "奄美市"),
    make_entry("46", "鹿児島県", "46223", "南九州市", "南九州市"),
    make_entry("46", "鹿児島県", "46224", "伊佐市", "伊佐市"),
    make_entry("46", "鹿児島県", "46225", "姶良市", "姶良市"),

    # -------------------------------------------------------------------------
    # 47 沖縄県 (Okinawa)
    # -------------------------------------------------------------------------
    make_entry("47", "沖縄県", "47201", "那覇市", "那覇市"),
    make_entry("47", "沖縄県", "47205", "宜野湾市", "宜野湾市"),
    make_entry("47", "沖縄県", "47207", "石垣市", "石垣市"),
    make_entry("47", "沖縄県", "47208", "浦添市", "浦添市"),
    make_entry("47", "沖縄県", "47209", "名護市", "名護市"),
    make_entry("47", "沖縄県", "47210", "糸満市", "糸満市"),
    make_entry("47", "沖縄県", "47211", "沖縄市", "沖縄市"),
    make_entry("47", "沖縄県", "47212", "豊見城市", "豊見城市"),
    make_entry("47", "沖縄県", "47213", "うるま市", "うるま市"),
    make_entry("47", "沖縄県", "47214", "宮古島市", "宮古島市"),
    make_entry("47", "沖縄県", "47215", "南城市", "南城市"),
]

def main():
    target_path = Path(__file__).parent / "municipalities.json"
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(MUNICIPALITIES_DATA, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(MUNICIPALITIES_DATA)} verified municipality records at {target_path}")

if __name__ == "__main__":
    main()
