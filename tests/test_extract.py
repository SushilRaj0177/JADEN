"""Finding addresses inside free text."""

import pytest

import jaden
from jaden.cli import main
from jaden.extract import extract_addresses


def spans(text):
    return [x.text for x in extract_addresses(text)]


@pytest.mark.parametrize("text, expected", [
    ("会場は東京都港区芝公園4-2-8の東京タワーです。TEL 03-3433-5111", ["東京都港区芝公園4-2-8"]),
    ("本社：〒100-0005 東京都千代田区丸の内1-9-1 グラントウキョウノースタワー 3F　TEL: 03-1234-5678",
     ["〒100-0005 東京都千代田区丸の内1-9-1 グラントウキョウノースタワー 3F"]),
    ("山田太郎様\n大阪市北区梅田3-1-1 大阪ステーションシティ 5F にお越しください。",
     ["大阪市北区梅田3-1-1 大阪ステーションシティ 5F"]),
    ("【店舗情報】住所　福岡県福岡市中央区天神1-8-1（福岡市役所）／営業時間 9:00-17:00", ["福岡県福岡市中央区天神1-8-1"]),
    ("横浜市立大学は神奈川県横浜市金沢区瀬戸22-2にあります。", ["神奈川県横浜市金沢区瀬戸22-2"]),
    ("新宿区役所は新宿区歌舞伎町1-4-1。", ["新宿区歌舞伎町1-4-1"]),
    ("港区芝公園４丁目２番８号　グランドメゾン芝公園　３０２号室 山田様", ["港区芝公園４丁目２番８号　グランドメゾン芝公園　３０２号室"]),
])
def test_extracts_the_address_span(text, expected):
    assert spans(text) == expected


def test_offsets_point_into_the_original_text():
    text = "お届け先：東京都港区芝公園4-2-8-101、ご連絡先：03-1234-5678"
    (found,) = extract_addresses(text)
    assert text[found.start:found.end] == found.text == "東京都港区芝公園4-2-8-101"
    assert found.canonical == "東京都港区芝公園4丁目2番8号 101"
    assert found.lg_code == "131032" and found.status == "ACCEPTED"
    assert found.to_dict()["precision"] == "unit"


def test_several_addresses_in_one_text():
    text = ("支店一覧: 札幌支店 北海道札幌市中央区北1条西2丁目1-1、仙台支店 宮城県仙台市青葉区本町3-8-1、"
            "名古屋支店 愛知県名古屋市中区三の丸3-1-2")
    assert [x.lg_code for x in extract_addresses(text)] == ["011011", "041017", "231061"]


def test_postal_code_on_its_own_line_joins_the_address_below():
    (found,) = extract_addresses("〒105-0011\n東京都港区芝公園4-2-8\n東京タワー")
    assert found.text == "〒105-0011\n東京都港区芝公園4-2-8"
    assert found.result.components.postal_code == "105-0011"


@pytest.mark.parametrize("text", [
    "東京タワーと大阪城公園に行きました。東京都は広い。",
    "2024年1月15日 10:00-12:00 参加費3,000円",
    "お問い合わせ: 03-1234-5678 / info@example.com",
    "弘前市立東中学校は1947年に開校しました。",
    "",
])
def test_text_without_an_address(text):
    assert extract_addresses(text) == []


def test_ambiguous_addresses_are_optional():
    text = "配送先は府中市宮西町2-24です。別宅は府中市1-1。"
    found = extract_addresses(text)
    assert [(x.text, x.status) for x in found] == [("府中市宮西町2-24", "ACCEPTED"), ("府中市1-1", "AMBIGUOUS")]
    assert [x.text for x in extract_addresses(text, include_ambiguous=False)] == ["府中市宮西町2-24"]


def test_extract_command(tmp_path, capsys):
    src = tmp_path / "mail.txt"
    src.write_text("会場は東京都港区芝公園4-2-8です。\n受付は大阪市北区梅田3-1-1にて。\n", encoding="utf-8")
    assert main(["extract", str(src)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("1:3-16\tACCEPTED\t東京都港区芝公園4丁目2番8号")
    assert out[1].startswith("2:") and "大阪府大阪市北区梅田3丁目1番1号" in out[1]
    empty = tmp_path / "none.txt"
    empty.write_text("住所はありません。", encoding="utf-8")
    assert main(["extract", str(empty)]) == 1


def test_top_level_export():
    assert jaden.extract_addresses("東京都港区芝公園4-2-8")[0].canonical == "東京都港区芝公園4丁目2番8号"
