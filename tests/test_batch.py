"""Tests for `jaden batch` and the flat record API."""

import csv
import io
import json

from jaden.batch import run_batch, RESULT_FIELDS
from jaden.cli import main

ROWS = (
    "顧客ID,氏名,住所\n"
    "1,山田,東京都港区芝公園4-2-8 101号室\n"
    "2,鈴木,府中市1-1\n"
    "3,田中,埼玉県浦和市高砂3-15-1\n"
    "4,伊藤,東京タワー\n"
)


def _run(tmp_path, data: bytes, name: str, out_name: str, **kwargs):
    src = tmp_path / name
    src.write_bytes(data)
    out = tmp_path / out_name
    counts = run_batch(src, out, log=io.StringIO(), **kwargs)
    return counts, out.read_text(encoding="utf-8")


def test_batch_csv_detects_address_column_and_appends_results(tmp_path):
    counts, text = _run(tmp_path, ROWS.encode("utf-8"), "in.csv", "out.csv")
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["顧客ID"] for r in rows] == ["1", "2", "3", "4"]
    assert rows[0]["jaden_canonical"] == "東京都港区芝公園4丁目2番8号 101号室"
    assert rows[0]["jaden_unit"] == "101号室"
    assert rows[1]["jaden_status"] == "AMBIGUOUS"
    assert "東京都府中市 (132063)" in rows[1]["jaden_candidates"]
    assert rows[2]["jaden_lg_code"] == "111074"
    assert rows[2]["jaden_former_municipality"] == "浦和市"
    assert rows[3]["jaden_status"] == "UNSUPPORTED"
    assert counts["ACCEPTED"] == 2
    assert all(f"jaden_{k}" in rows[0] for k in RESULT_FIELDS)


def test_batch_reads_shift_jis(tmp_path):
    counts, text = _run(tmp_path, ROWS.encode("cp932"), "in.csv", "out.csv")
    assert "東京都港区芝公園4丁目2番8号" in text
    assert sum(counts.values()) == 4


def test_batch_jsonl_and_column_by_number(tmp_path):
    _, text = _run(tmp_path, ROWS.encode("utf-8"), "in.csv", "out.jsonl", column="3")
    first = json.loads(text.splitlines()[0])
    assert first["氏名"] == "山田"
    assert first["jaden"]["postal_code"] == "105-0011"


def test_batch_text_input_with_workers(tmp_path):
    data = "東京都港区芝公園4-2-8\n浦和市高砂3-15-1\n\n福岡市中央区天神1-8-1\n".encode("utf-8")
    counts, text = _run(tmp_path, data, "in.txt", "out.csv", jobs=2)
    rows = list(csv.DictReader(io.StringIO(text)))
    assert [r["jaden_lg_code"] for r in rows] == ["131032", "111074", "401331"]
    assert counts["ACCEPTED"] == 3


def test_batch_cli_unknown_column(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text(ROWS, encoding="utf-8")
    assert main(["batch", str(src), "--column", "存在しない列"]) == 64


def test_english_line_has_no_japanese_unit_or_floor():
    import jaden
    assert jaden.normalize("東京都港区芝公園4-2-8 101号室").romaji.startswith("#101, 4-2-8 Shibakoen")
    assert "32F" in jaden.normalize("東京都新宿区西新宿2-8-1 東京都庁第一本庁舎 32階").romaji


def test_place_name_is_not_rewritten():
    import jaden
    assert jaden.normalize("東京タワー").canonical == "東京タワー"
