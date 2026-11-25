"""Bugs found by the full audit of 22 November 2026 (docs/CHECKLIST.md), each pinned by its reproducing input."""

import json
import time
from pathlib import Path

import pytest

import jaden


# B1: reverse geocoding near the poles never returned
@pytest.mark.parametrize("lat, lon", [(90, 0), (-90, 0), (88, 0), (0, 0), (60, 10)])
def test_reverse_geocoding_far_from_japan_returns_at_once(lat: float, lon: float) -> None:
    start = time.perf_counter()
    assert jaden.reverse_geocode(lat, lon) == []
    assert time.perf_counter() - start < 1.0


def test_reverse_geocoding_still_reaches_the_edges_of_japan() -> None:
    assert jaden.reverse_geocode(24.4667, 153.9833)[0].address.startswith("東京都小笠原村")   # 南鳥島
    assert jaden.reverse_geocode(45.52, 141.94)[0].address.startswith("北海道稚内市")


@pytest.mark.parametrize("call", [lambda: jaden.reverse_geocode(35.0, 135.0, limit=0),
                                  lambda: jaden.suggest("東京都港区", limit=0)])
def test_limits_below_one_are_rejected(call) -> None:
    with pytest.raises(ValueError):
        call()


# B27: inputs that are not text
@pytest.mark.parametrize("value", [123, float("nan"), None])
def test_non_text_input_gives_an_empty_result_not_an_exception(value: object) -> None:
    assert jaden.validate(value).status == "MALFORMED"   # type: ignore[arg-type]
    assert jaden.match_key(value) is None                # type: ignore[arg-type]
    assert not jaden.resolve(value).answered             # type: ignore[arg-type]
    assert jaden.extract_addresses(value) == []          # type: ignore[arg-type]
    jaden.normalize(value)                               # type: ignore[arg-type]


def test_postal_lookup_accepts_an_integer() -> None:
    assert jaden.lookup_postal(1050011)[0].town == "芝公園"   # type: ignore[arg-type]


# B2: a contradicting postal code written with another dash
@pytest.mark.parametrize("dash", ["―", "‐", "–", "—", "-", "－"])
def test_contradicting_postal_code_is_caught_with_any_dash(dash: str) -> None:
    assert jaden.validate(f"〒100{dash}0001 東京都港区芝公園4-2-8").status == "MALFORMED"


# B3: postal codes without a hyphen or with spaces
@pytest.mark.parametrize("text", ["1050011 東京都港区芝公園4-2-8", "〒 105 - 0011 東京都港区芝公園4-2-8",
                                  "〒105 0011 東京都港区芝公園4-2-8", "東京都港区芝公園4-2-8 1050011"])
def test_postal_code_forms_are_read_and_removed(text: str) -> None:
    res = jaden.normalize(text)
    assert jaden.validate(text).status == "ACCEPTED"
    assert res.canonical == "東京都港区芝公園4丁目2番8号"
    assert res.components.postal_code == "105-0011"


def test_seven_digits_glued_to_the_address_are_still_a_lot_number() -> None:
    assert jaden.normalize("東京都小平市小川町２丁目1987102").components.postal_code != "198-7102"


# B4, B5: number forms around 丁目 and 番地
@pytest.mark.parametrize("text, canonical", [
    ("東京都港区芝公園4丁目-2-8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目ー2ー8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目の2の8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目2の8番地", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目2-8番地", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4 - 2 - 8", "東京都港区芝公園4丁目2番8号"),
    ("石川県輪島市門前町赤神10の1番地", "石川県輪島市門前町赤神10番地の1"),
    ("奈良県吉野郡大淀町下渕887の2番地", "奈良県吉野郡大淀町下渕887番地の2"),
    ("奈良県吉野郡大淀町下渕887-2番地", "奈良県吉野郡大淀町下渕887番地の2"),
])
def test_number_forms(text: str, canonical: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical
    assert res.components.building is None


# B24: invisible and control characters
@pytest.mark.parametrize("text", ["東​京都港区芝公園4-2-8", "東京都港区芝公園4​-2-8", "東京都港区芝公園4­-2-8",
                                  "東京都港区芝公園4 -2-8", "東京都港区芝公園4\x00-2-8", "東京都港区芝公園4⁃2⁃8",
                                  "﻿東京都港区芝公園4-2-8"])
def test_invisible_characters_are_removed(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == "東京都港区芝公園4丁目2番8号"
    assert "\x00" not in res.canonical


# B25: a phone number after the address
@pytest.mark.parametrize("text", ["東京都港区芝公園4-2-8 TEL 03-1234-5678", "東京都港区芝公園4-2-8 電話：03(1234)5678",
                                  "東京都港区芝公園4-2-8 FAX:03-1234-5679"])
def test_a_trailing_phone_number_is_not_the_building(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == "東京都港区芝公園4丁目2番8号" and res.components.building is None


# B6: town names written with 壱 / a 壱丁目 inside a building name
@pytest.mark.parametrize("text, canonical, building", [
    ("埼玉県上尾市壱丁目北24-17", "埼玉県上尾市壱丁目北24番17号", None),
    ("埼玉県上尾市壱丁目北24-17壱丁目ビル303", "埼玉県上尾市壱丁目北24番17号 壱丁目ビル 303", "壱丁目ビル"),
])
def test_ichi_chome_town_names(text: str, canonical: str, building: object) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical and res.components.building == building
    assert jaden.validate(text).verification_level == "town"


# B7: Sapporo grid followed by 番 and a lot
def test_sapporo_grid_with_ban_and_hyphen() -> None:
    c = jaden.normalize("北海道札幌市北区北29条西4丁目2番1-158").components
    assert (c.town, c.ban, c.go, c.unit) == (None, 2, 1, "158")


# B8: a town whose name holds a number, without the municipality
def test_furumachi_without_the_municipality() -> None:
    res = jaden.normalize("古町通6番町976")
    assert res.canonical == "新潟県新潟市中央区古町通六番町976番"
    assert res.components.building is None and res.components.unit is None


# B9-B11: resolver guards
def test_resolver_does_not_answer_text_without_numbers() -> None:
    for text in ("大泉町立北小学校", "南部町"):
        assert not jaden.resolve(text).answered


def test_tokyo_does_not_mention_kyoto() -> None:
    from jaden.resolve import mentions_prefecture
    assert not mentions_prefecture("京都府", "東京都立第一高校")
    assert mentions_prefecture("東京都", "東京都立第一高校")
    assert mentions_prefecture("京都府", "京都市立高校")


def test_an_answer_is_always_in_its_candidate_set() -> None:
    r = jaden.resolve("下伊那郡喬木村1396-2")
    assert r.answered and r.lg_code in r.candidate_set


# B12: an address and its canonical form get the same key
def test_dedupe_and_compare_agree_on_chome_ban() -> None:
    pair = ["埼玉県北本市本町6-232", "埼玉県北本市本町6丁目232番"]
    assert jaden.find_duplicates(pair) == [1, 1]
    assert jaden.compare(*pair).verdict == "same"


# B13: rooms with letters, wings, kanji floors
B = "東京都港区芝公園4-2-8"


def test_lettered_rooms_are_different_flats() -> None:
    assert jaden.find_duplicates([B + " A-302", B + " B-302", B]) == [1, 2, 3]
    assert jaden.compare(B + " A棟101", B + " B棟101").verdict != "same"
    assert jaden.compare(B + " 302号室", B + "-302").verdict == "same"


@pytest.mark.parametrize("tail, unit", [("A-302", "A-302"), ("302-A", "302-A"), ("2-302", "2-302"), (" 1", "1")])
def test_rooms_on_their_own(tail: str, unit: str) -> None:
    sep = "" if tail.startswith(" ") else " "
    c = jaden.normalize(B + sep + tail).components
    assert c.unit == unit and c.building is None


def test_kanji_floor() -> None:
    assert jaden.normalize(B + " 三階").components.floor == "3階"


def test_two_floors_stay_in_the_building() -> None:
    c = jaden.normalize(B + " 百道ふれあい館 2階・3階").components
    assert c.floor is None and "2階・3階" in (c.building or "")


# B14, B21-B23: canonical and hyphen forms are fixed points
@pytest.mark.parametrize("text", ["小中野3-9-26", "南3条東1-2-1", "宮城野2-4-1", "静岡県中央区日本橋兜町15-18"])
def test_unresolved_or_contradicted_input_is_returned_as_written(text: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == res.input_sanitized
    assert jaden.validate(res.canonical).status == jaden.validate(text).status


@pytest.mark.parametrize("text", [
    "千葉県市原市万田野732番地6", "福井県大野市春日三丁目１７１８", "沖縄県宜野湾市宇地泊１丁目20番7号",
    "北海道札幌市中央区南6条西11丁目1284番地4", "福井県勝山市片瀬第１５号２２番地", "熊本県八代市田中北町7号1番",
    "宮城県石巻市井内字三番113-2", "神奈川県茅ヶ崎市甘沼2723階", "宮崎県日南市大堂津1-13-16-1",
])
def test_canonical_and_hyphen_forms_read_back(text: str) -> None:
    res = jaden.normalize(text)
    assert jaden.normalize(res.canonical).canonical == res.canonical
    assert jaden.normalize(res.format("hyphen")).canonical == res.canonical
    assert jaden.match_key(text) == jaden.match_key(res.canonical)


# B15: offline geocoding follows validation
@pytest.mark.parametrize("text", ["東京都港区芝公園9-2-8", "東京都港区芝公園0-0-0", "〒100-0001 東京都港区芝公園4-2-8"])
def test_offline_geocoding_does_not_succeed_for_rejected_addresses(text: str) -> None:
    g = jaden.geocode(text, provider="offline")
    assert g.status == "NO_MATCH" and g.metadata["validation"] == "MALFORMED"


# B16, B17: extraction
def test_a_phone_number_is_not_a_postal_code() -> None:
    found = jaden.extract_addresses("電話03-1234-5678 東京都港区芝公園4-2-8")
    assert [e.text for e in found] == ["東京都港区芝公園4-2-8"]


@pytest.mark.parametrize("text", ["本社：東京都港区芝公園4-2-8 支社：大阪府大阪市北区梅田3-1-1",
                                  "東京都港区芝公園4-2-8と大阪府大阪市北区梅田3-1-1",
                                  "旧住所：東京都港区芝公園4-2-8→新住所:大阪府大阪市北区梅田3-1-1"])
def test_two_addresses_are_two_spans(text: str) -> None:
    assert [e.text for e in jaden.extract_addresses(text)] == ["東京都港区芝公園4-2-8", "大阪府大阪市北区梅田3-1-1"]


def test_normalize_stops_at_a_second_address_but_not_at_a_building_named_after_a_prefecture() -> None:
    res = jaden.normalize("東京都港区芝公園4-2-8 支社：大阪府大阪市北区梅田3-1-1")
    assert res.canonical == "東京都港区芝公園4丁目2番8号" and res.components.building is None
    assert jaden.normalize("東京都新宿区西新宿2-8-1東京都庁 第一本庁舎").components.building == "東京都庁 第一本庁舎"


# B18: the romaji table is published only once complete (checked by many threads at once)
def test_romaji_under_threads() -> None:
    from concurrent.futures import ThreadPoolExecutor
    from jaden.romaji import _index
    _index()._towns.clear()
    inputs = ["7-2 Horencho, Nara-shi, Nara", "4-2-8 Shibakoen, Minato-ku, Tokyo"] * 200
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda t: jaden.normalize(t).canonical, inputs))
    assert set(results) == {"奈良県奈良市法蓮町7番2号", "東京都港区芝公園4丁目2番8号"}


# B19: a romaji town the registry does not hold
def test_unmatched_romaji_town_stays_in_place() -> None:
    res = jaden.normalize("158-2 Qwertyz, Hirakawa-shi, Aomori")
    assert res.canonical == "青森県平川市Qwertyz158番2号"
    assert jaden.validate("158-2 Qwertyz, Hirakawa-shi, Aomori").verification_level == "municipality"
    # A town only Japan Post lists is found by its romaji too
    assert jaden.normalize("158-2 Arata Kamikomata, Hirakawa-shi, Aomori").canonical == "青森県平川市荒田上駒田158番2号"


# ---------------------------------------------------------------- B26: batch files
def _batch(tmp_path, name: str, data: bytes, *args: str):
    import io
    from jaden.batch import run_batch
    src = tmp_path / name
    src.write_bytes(data)
    out = tmp_path / ("out" + src.suffix)
    log = io.StringIO()
    counts = run_batch(src, out, log=log, *args)  # type: ignore[misc]
    return out.read_text(encoding="utf-8"), counts, log.getvalue()


def test_batch_keeps_columns_with_the_same_name(tmp_path) -> None:
    out, counts, _ = _batch(tmp_path, "a.csv", "id,住所,dup,dup\n1,東京都港区芝公園4-2-8,a,b\n".encode())
    header, row = out.splitlines()[:2]
    assert header.startswith("id,住所,dup,dup,jaden_status")
    assert row.startswith("1,東京都港区芝公園4-2-8,a,b,ACCEPTED")


def test_batch_detects_a_file_without_header(tmp_path) -> None:
    out, counts, _ = _batch(tmp_path, "a.csv", "東京都港区芝公園4-2-8,x\n大阪府大阪市北区梅田3-1-1,y\n".encode())
    assert counts["ACCEPTED"] == 2
    assert out.splitlines()[0].startswith("column1,column2,jaden_status")


@pytest.mark.parametrize("encoding", ["euc_jp", "utf-16", "cp932", "utf-8-sig"])
def test_batch_detects_the_encoding(tmp_path, encoding: str) -> None:
    data = "住所\n東京都港区芝公園4-2-8\n大阪府大阪市北区梅田3-1-1\n".encode(encoding)
    _, counts, _ = _batch(tmp_path, "a.csv", data)
    assert counts["ACCEPTED"] == 2


def test_batch_keeps_an_input_column_named_like_a_result(tmp_path) -> None:
    out, _, log = _batch(tmp_path, "a.csv", "address,jaden_status\n東京都港区芝公園4-2-8,mine\n".encode())
    assert "mine" in out.splitlines()[1] and "warning" in log


def test_batch_jsonl_null_is_empty(tmp_path) -> None:
    _, counts, _ = _batch(tmp_path, "a.jsonl", '{"address": null}\n{"address": "東京都港区芝公園4-2-8"}\n'.encode())
    assert counts["EMPTY"] == 1 and counts["ACCEPTED"] == 1


@pytest.mark.parametrize("name, data, kwargs, message", [
    ("a.jsonl", b'{"address": "x"}\n[1,2]\n', {}, "line 2"),
    ("a.csv", b"a,b\n1,2\n", {"column": "0"}, "out of range"),
    ("a.csv", b"a,b\n1,2\n", {"column": "9"}, "out of range"),
    ("a.csv", b"a,b\n1,2\n", {"encoding": "nosuchenc"}, "unknown encoding"),
])
def test_batch_input_errors_are_clear(tmp_path, name: str, data: bytes, kwargs: dict, message: str) -> None:
    import io
    from jaden.batch import run_batch
    src = tmp_path / name
    src.write_bytes(data)
    with pytest.raises(ValueError, match=message):
        run_batch(src, tmp_path / "out.csv", log=io.StringIO(), **kwargs)


def test_batch_warns_when_most_rows_are_rejected(tmp_path) -> None:
    rows = "住所\n" + "あいうえお\n" * 12
    _, _, log = _batch(tmp_path, "a.csv", rows.encode())
    assert "check --column and --encoding" in log


# ---------------------------------------------------------------- B28, F1: server
@pytest.fixture(scope="module")
def server_url():
    import threading
    from jaden.server import create_server
    server = create_server(port=0, quiet=True, warm_up=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _http(url: str, method: str = "GET", body: bytes = b"", headers: dict = None):
    import json as _json
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=body or None, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, _json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, _json.loads(e.read())


def test_server_errors_are_json(server_url: str) -> None:
    status, body = _http(server_url + "/v1/normalize", method="PUT")
    assert status == 501 and body["error"]["code"] == "http_501"


def test_server_rejects_extra_path_and_bad_types(server_url: str) -> None:
    assert _http(server_url + "/v1/postal/105-0011/extra")[0] == 404
    json_header = {"Content-Type": "application/json"}
    status, body = _http(server_url + "/v1/normalize", "POST", b'{"q": 123}', json_header)
    assert status == 400 and "string" in body["error"]["message"]
    status, _ = _http(server_url + "/v1/suggest", "POST", '{"q": "東京都", "limit": true}'.encode(), json_header)
    assert status == 400


def test_server_requires_json_content_type(server_url: str) -> None:
    assert _http(server_url + "/v1/normalize", "POST", b'{"q": "x"}', {"Content-Type": "text/plain"})[0] == 415


def test_server_caps_extraction_text(server_url: str) -> None:
    import json as _json
    big = _json.dumps({"text": "東京都" * 40000}).encode()
    assert _http(server_url + "/v1/extract", "POST", big, {"Content-Type": "application/json"})[0] == 413


def test_server_reverse_at_the_pole_and_resolve(server_url: str) -> None:
    status, body = _http(server_url + "/v1/reverse?lat=90&lon=0")
    assert status == 200 and body["results"] == []
    import urllib.parse
    status, body = _http(server_url + "/v1/resolve?q=" + urllib.parse.quote("芝公園4-2-8"))
    assert status == 200 and body["answered"] and body["lg_code"] == "131032"


# ---------------------------------------------------------------- B20, B29: command line
def _cli(args, monkeypatch, stdin: str = ""):
    import io
    from jaden.cli import main
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    monkeypatch.setattr("sys.stdin", io.StringIO(stdin))
    code = main(args)
    return code, out.getvalue(), err.getvalue()


def test_cli_reads_one_address_per_stdin_line(monkeypatch) -> None:
    code, out, _ = _cli(["normalize", "-", "-c"], monkeypatch, "東京都港区芝公園4-2-8\n大阪府大阪市北区梅田3-1-1\n")
    assert code == 0 and out.splitlines() == ["東京都港区芝公園4丁目2番8号", "大阪府大阪市北区梅田3丁目1番1号"]


def test_cli_rejects_a_limit_below_one(monkeypatch) -> None:
    code, _, err = _cli(["suggest", "東京都港区", "--limit", "0"], monkeypatch)
    assert code != 0 and "at least 1" in err


def test_cli_resolve_reads_stdin(monkeypatch) -> None:
    code, out, _ = _cli(["resolve", "-", "--limit", "1"], monkeypatch, "芝公園4-2-8\n")
    assert code == 0 and "東京都港区" in out


# ---------------------------------------------------------------- P1, P2: slow paths
def test_extraction_of_place_name_dense_text_is_fast() -> None:
    start = time.perf_counter()
    assert jaden.extract_addresses("東京都" * 20000) == []
    assert time.perf_counter() - start < 5.0


def test_kana_suggestion_is_fast_once_indexed() -> None:
    jaden.suggest("しば")
    start = time.perf_counter()
    for reading in ("きっかわ", "さかえ", "しばこうえん"):
        jaden.suggest(reading)
    assert time.perf_counter() - start < 1.0


# ---------------------------------------------------------------- F3: reason codes, Japanese messages, OpenAPI
@pytest.mark.parametrize("text, reason", [
    ("東京都港区芝公園4-2-8", "VERIFIED_CHOME"),
    ("東京都港区芝公園9-2-8", "NONEXISTENT_CHOME"),
    ("府中市1-1", "AMBIGUOUS_MUNICIPALITY"),
    ("〒100-0001 東京都港区芝公園4-2-8", "POSTAL_CODE_MISMATCH"),
    ("あいうえお", "NOT_AN_ADDRESS"),
    ("", "EMPTY"),
    ("x" * 600, "TOO_LONG"),
])
def test_validate_gives_a_reason_code_and_japanese_message(text: str, reason: str) -> None:
    from jaden.models.validation import REASONS
    v = jaden.validate(text)
    assert v.reason == reason and REASONS[reason] == v.status and v.message_ja


def test_every_status_comes_with_a_known_reason() -> None:
    from jaden.models.validation import REASONS
    for text in ("東京都千代田区霞が関1-2-1", "大阪府大阪市北区梅田3-1-1", "高崎市立国府小学校", "東京都港区ほげ1-1",
                 "北海道札幌市中央区南3条西1-2", "東京都0-1-1"):
        v = jaden.validate(text)
        assert v.reason in REASONS and REASONS[v.reason] == v.status, (text, v.status, v.reason)


def test_reason_reaches_the_api_and_batch_records() -> None:
    from jaden.batch import RESULT_FIELDS, process_address
    from jaden.server import JadenApi
    api = JadenApi()
    rec = api.handle("/v1/normalize", {"q": "東京都港区芝公園4-2-8"})
    assert rec["reason"] == "VERIFIED_CHOME" and rec["message_ja"]
    assert api.handle("/v1/validate", {"q": "府中市1-1"})["reason"] == "AMBIGUOUS_MUNICIPALITY"
    assert "reason" in RESULT_FIELDS and process_address("")["reason"] == "EMPTY"


def test_openapi_description_lists_every_route() -> None:
    from jaden.server import JadenApi
    api = JadenApi()
    spec = api.handle("/v1/openapi.json", {})
    assert spec["openapi"].startswith("3.")
    paths = {p.replace("/{code}", "") for p in spec["paths"]}
    assert set(api.routes) <= paths
    json.dumps(spec)


# ---------------------------------------------------------------- F4: MCP server
def _mcp(*messages: object) -> list:
    import io
    from jaden.mcp import serve_stdio
    out = io.StringIO()
    serve_stdio(io.StringIO("\n".join(m if isinstance(m, str) else json.dumps(m) for m in messages) + "\n"), out)
    return [json.loads(line) for line in out.getvalue().splitlines()]


def test_mcp_handshake_lists_and_calls_tools() -> None:
    replies = _mcp(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "normalize_address", "arguments": {"address": "港区芝公園4-2-8"}}},
        {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
         "params": {"name": "resolve_address", "arguments": {"address": "南3条東1-2-1"}}})
    assert [r["id"] for r in replies] == [1, 2, 3, 4]       # no reply to the notification
    assert replies[0]["result"]["protocolVersion"] == "2025-06-18"
    names = {t["name"] for t in replies[1]["result"]["tools"]}
    assert {"normalize_address", "validate_address", "resolve_address", "extract_addresses"} <= names
    rec = replies[2]["result"]
    assert not rec["isError"] and rec["structuredContent"]["canonical"] == "東京都港区芝公園4丁目2番8号"
    assert json.loads(rec["content"][0]["text"])["reason"] == "VERIFIED_CHOME"
    assert not replies[3]["result"]["structuredContent"]["answered"]  # ambiguous: no invented municipality


def test_mcp_reports_bad_input_without_dying() -> None:
    replies = _mcp("not json",
                   {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "nope"}},
                   {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "validate_address", "arguments": {"address": 5}}},
                   {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "suggest_addresses", "arguments": {"text": "しば", "limit": True}}},
                   {"jsonrpc": "2.0", "id": 4, "method": "frobnicate"},
                   {"jsonrpc": "2.0", "id": 5, "method": "ping"})
    assert replies[0]["error"]["code"] == -32700
    assert replies[1]["error"]["code"] == -32602
    assert replies[2]["result"]["isError"] and replies[3]["result"]["isError"]
    assert replies[4]["error"]["code"] == -32601 and replies[5]["result"] == {}


# ---------------------------------------------------------------- F1: resolver columns in jaden batch
def test_batch_resolve_columns(tmp_path) -> None:
    import csv
    from jaden.batch import run_batch
    src = tmp_path / "in.csv"
    src.write_text("address,name\n南3条東1-2-1,\n東京都港区芝公園4-2-8,東京タワー\n,空欄\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    run_batch(src, out, resolve=True, name_column="name", log=open(tmp_path / "log", "w"))
    rows = list(csv.DictReader(open(out, encoding="utf-8")))
    assert rows[0]["jaden_resolved_lg_code"] == "" and "北海道札幌市中央区 (011011)" in rows[0]["jaden_resolved_candidates"]
    assert rows[1]["jaden_resolved_lg_code"] == "131032" and rows[1]["jaden_resolved_name"] == "東京都港区"
    assert rows[2]["jaden_status"] == "EMPTY" and rows[2]["jaden_resolved_candidates"] == ""


def test_batch_resolve_works_with_workers_and_rejects_a_bad_name_column(tmp_path) -> None:
    import csv
    from jaden.batch import run_batch
    src = tmp_path / "in.csv"
    src.write_text("address\n" + "東京都港区芝公園4-2-8\n" * 4, encoding="utf-8")
    out = tmp_path / "out.csv"
    run_batch(src, out, resolve=True, jobs=2, log=open(tmp_path / "log", "w"))
    assert {r["jaden_resolved_lg_code"] for r in csv.DictReader(open(out, encoding="utf-8"))} == {"131032"}
    with pytest.raises(ValueError, match="not found"):
        run_batch(src, out, resolve=True, name_column="nope", log=open(tmp_path / "log", "w"))


# ---------------------------------------------------------------- F2: structured input
def test_fields_are_read_and_split_back() -> None:
    r = jaden.check_fields(postal_code="１０５ー００１１", prefecture="東京都", city="港区", line1="芝公園4-2-8",
                           line2="グランドメゾン芝公園302")
    assert r.valid and r.issues == []
    assert r.fields == {"postal_code": "105-0011", "prefecture": "東京都", "city": "港区",
                        "line1": "芝公園4丁目2番8号", "line2": "グランドメゾン芝公園 302"}


def test_fields_report_the_postal_code_and_city_that_disagree() -> None:
    r = jaden.check_fields(postal_code="100-0001", prefecture="東京都", city="港区", line1="芝公園4-2-8")
    assert not r.valid and [(i.field, i.code, i.suggestion) for i in r.issues] == \
        [("postal_code", "POSTAL_CODE_MISMATCH", "105-0011")]
    r = jaden.check_fields(prefecture="東京都", city="千代田区", line1="港区芝公園4-2-8")
    assert any(i.code == "CITY_MISMATCH" and i.suggestion == "港区" for i in r.issues)
    r = jaden.check_fields(postal_code="12-34", line1="東京都港区芝公園4-2-8")
    assert {i.code for i in r.errors} == {"POSTAL_CODE_FORMAT"}


def test_fields_postal_code_settles_an_ambiguous_city_and_blank_fields_are_filled() -> None:
    r = jaden.check_fields(city="府中市", line1="府中町1-1", postal_code="183-0055")
    assert r.valid and r.fields["prefecture"] == "東京都"
    assert [(i.field, i.code) for i in r.issues] == [("prefecture", "FILLED_IN")]
    r = jaden.check_fields(city="府中市", line1="府中町1-1")
    assert r.status == "AMBIGUOUS" and not r.valid and r.fields["city"] == ""


def test_fields_in_the_api_and_mcp() -> None:
    from jaden.server import ApiError, JadenApi
    api = JadenApi()
    out = api.handle("/v1/fields", {"prefecture": "東京都", "city": "港区", "line1": "芝公園4-2-8"})
    assert out["valid"] and out["fields"]["postal_code"] == "105-0011"
    with pytest.raises(ApiError):
        api.handle("/v1/fields", {})
    reply = _mcp({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "check_address_fields", "arguments": {"city": "港区", "line1": "芝公園4-2-8"}}})[0]
    assert reply["result"]["structuredContent"]["fields"]["prefecture"] == "東京都"


# ---------------------------------------------------------------- F8: addresses typed in kana
@pytest.mark.parametrize("text, canonical", [
    ("とうきょうとちよだくかすみがせき1-2-1", "東京都千代田区霞が関1丁目2番1号"),
    ("トウキョウトチヨダクカスミガセキ1-2-1", "東京都千代田区霞が関1丁目2番1号"),
    ("ちよだくかすみがせき1-2-1", "東京都千代田区霞が関1丁目2番1号"),
    ("おおさかふおおさかしきたくうめだ3-1-1", "大阪府大阪市北区梅田3丁目1番1号"),
    ("ﾄｳｷｮｳﾄﾐﾅﾄｸｼﾊﾞｺｳｴﾝ4-2-8", "東京都港区芝公園4丁目2番8号"),
    ("とうきょうとふちゅうしふちゅうちょう1-1", "東京都府中市府中町1丁目1番"),
    ("〒105-0011 とうきょうと みなとく しばこうえん 4-2-8", "東京都港区芝公園4丁目2番8号"),
])
def test_kana_addresses_are_read(text: str, canonical: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical and jaden.validate(text).status == "ACCEPTED"
    assert any(n.startswith("read from kana") for n in res.notes)


def test_kana_that_is_not_an_address_stays_rejected() -> None:
    assert jaden.validate("ふちゅうしふちゅうちょう1-1").status == "AMBIGUOUS"   # two 府中市
    assert jaden.validate("かすみがせき1-2-1").lg_code == "131016"   # one town in Japan reads かすみがせき
    for text in ("あいうえお1-1", "やまだたろう", "さくら銀行1-1"):
        assert jaden.validate(text).status == "MALFORMED"


# ---------------------------------------------------------------- F6: explainable fuzzy dedupe
@pytest.mark.parametrize("a, b, score, word", [
    ("グランドメゾン芝公園", "グランドメゾン芝公園", 1.0, "same"),
    ("芝公園ビル", "芝公園ビルディング", 1.0, "same"),
    ("グランドメゾン芝公園", "グランドメゾン芝公演", 0.9, "typo"),
    ("グランドメゾン", "グランドメゾン芝公園", 0.9, "shortened"),
    ("第一ビル", "第二ビル", 0.0, "separate"),
    ("第1ビル", "第一ビル", 1.0, "same"),
    ("ABC一号館", "ABC二号館", 0.0, "separate"),
    ("コーポ山田Ⅰ", "コーポ山田Ⅱ", 0.0, "separate"),
    ("サンハイツA", "サンハイツB", 0.0, "separate"),
    ("グリーンハイツ東", "グリーンハイツ西", 0.0, "separate"),
    ("サンハイツA棟", "サンハイツB棟", 0.0, "separate"),
    ("グランドメゾン芝公園", "Grand Maison", None, "scripts"),
])
def test_building_similarity_explains_itself(a: str, b: str, score, word: str) -> None:
    got, reason = jaden.building_similarity(a, b)
    assert got == score and word in reason


def test_numbered_buildings_on_one_lot_are_not_the_same_address() -> None:
    cmp = jaden.compare("東京都港区芝公園4-2-8 第一ビル", "東京都港区芝公園4-2-8 第二ビル")
    # The key leaves building names out (they are often omitted), so compare agrees with it; the note and
    # the duplicate score say the names number different buildings
    assert cmp.verdict == "same" and cmp.building_similarity == 0.0
    assert any("number different buildings" in n for n in cmp.notes)
    assert jaden.duplicate_pairs(["東京都港区芝公園4-2-8 第一ビル", "東京都港区芝公園4-2-8 第二ビル"]) == []
    wings = jaden.compare("東京都港区芝公園4-2-8 ABC一号館", "東京都港区芝公園4-2-8 ABC二号館")
    assert (wings.verdict, wings.conflict) == ("different", "building")
    assert jaden.compare("東京都港区芝公園4-2-8 グランドメゾン芝公園302",
                         "東京都港区芝公園4-2-8 グランドメゾン芝公演302").verdict == "same"


def test_duplicate_pairs_score_and_explain(tmp_path) -> None:
    import csv
    from jaden.batch import run_dedupe
    rows = ["東京都港区芝公園4-2-8 グランドメゾン芝公園302", "港区芝公園４丁目２番８号　グランドメゾン芝公演　３０２号室",
            "東京都港区芝公園4-2-8 第一ビル", "東京都港区芝公園4-2-8 第二ビル", "東京都港区芝公園4-2-8 グランドメゾン芝公園",
            "東京都港区芝公園4-2-9"]
    pairs = jaden.duplicate_pairs(rows)
    assert [(p.i, p.j) for p in pairs] == [(0, 1), (0, 4), (1, 4)]
    assert pairs[0].score == 0.9 and any("typo" in r for r in pairs[0].reasons)
    src, out = tmp_path / "in.csv", tmp_path / "pairs.csv"
    src.write_text("address\n" + "\n".join(rows) + "\n", encoding="utf-8")
    run_dedupe(src, tmp_path / "out.csv", pairs=out, log=open(tmp_path / "log", "w"))
    written = list(csv.DictReader(open(out, encoding="utf-8")))
    assert [(r["row_a"], r["row_b"]) for r in written] == [("1", "2"), ("1", "5"), ("2", "5")]


# ---------------------------------------------------------------- F7: pandas, .xlsx, NDJSON stream
def test_xlsx_round_trip_keeps_text_and_leading_zeros(tmp_path) -> None:
    from jaden.xlsx import read_xlsx, write_xlsx
    path = tmp_path / "t.xlsx"
    write_xlsx(path, [["住所", "郵便番号"], ["東京都港区芝公園4-2-8", "0600063"], ["a<&>\x01", " x "]])
    assert read_xlsx(path) == [["住所", "郵便番号"], ["東京都港区芝公園4-2-8", "0600063"], ["a<&>", " x "]]
    with pytest.raises(ValueError, match="not an .xlsx"):
        (tmp_path / "bad.xlsx").write_text("nope")
        read_xlsx(tmp_path / "bad.xlsx")


def test_xlsx_written_by_excel_tools_is_read(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    from jaden.batch import run_batch
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["id", "住所"])
    ws.append([1, "東京都港区芝公園4-2-8"])
    ws.append([2, "府中市1-1"])
    wb.save(tmp_path / "in.xlsx")
    counts = run_batch(tmp_path / "in.xlsx", tmp_path / "out.xlsx", log=open(tmp_path / "log", "w"))
    assert counts == {"ACCEPTED": 1, "AMBIGUOUS": 1}
    rows = [[c.value for c in r] for r in openpyxl.load_workbook(tmp_path / "out.xlsx").active.iter_rows()]
    assert rows[0][:3] == ["id", "住所", "jaden_status"] and rows[1][2] == "ACCEPTED"


def test_dedupe_reads_and_writes_xlsx(tmp_path) -> None:
    from jaden.batch import run_dedupe
    from jaden.xlsx import read_xlsx, write_xlsx
    write_xlsx(tmp_path / "in.xlsx", [["address"], ["東京都港区芝公園4-2-8 302"], ["港区芝公園４丁目２番８号　３０２号室"]])
    run_dedupe(tmp_path / "in.xlsx", tmp_path / "out.xlsx", log=open(tmp_path / "log", "w"))
    rows = read_xlsx(tmp_path / "out.xlsx")
    assert rows[0][-2:] == ["jaden_group", "jaden_group_size"] and rows[1][-2:] == rows[2][-2:] == ["1", "2"]


def test_pandas_helper_keeps_the_index() -> None:
    pd = pytest.importorskip("pandas")
    from jaden.frame import normalize_frame
    df = pd.DataFrame({"住所": ["港区芝公園4-2-8", None, "府中市1-1"]}, index=[10, 20, 30])
    out = normalize_frame(df, "住所", resolve=True)
    assert list(out.index) == [10, 20, 30]
    assert list(out["jaden_status"]) == ["ACCEPTED", "EMPTY", "AMBIGUOUS"]
    assert out.loc[10, "jaden_resolved_lg_code"] == "131032"
    with pytest.raises(KeyError):
        normalize_frame(df, "address")


def test_stream_writes_one_record_per_line() -> None:
    import io
    from jaden.frame import stream
    src = io.StringIO('港区芝公園4-2-8\n\n{"id": 7, "address": "府中市1-1"}\n[1]\nnot json {\n')
    out = io.StringIO()
    assert stream(src, out) == 5        # the blank line gets its own (EMPTY) record, so lines stay aligned
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert lines[0]["jaden"]["status"] == "ACCEPTED"
    assert lines[1]["input"] == "" and lines[1]["jaden"]["status"] == "EMPTY"
    assert lines[2]["input"]["id"] == 7 and lines[2]["jaden"]["status"] == "AMBIGUOUS"
    assert "error" in lines[3] and lines[4]["jaden"]["status"] == "MALFORMED"


# ---------------------------------------------------------------- F5: label lines
def test_label_lines_break_between_parts_and_report_overflow() -> None:
    res = jaden.normalize("東京都港区芝公園4-2-8 グランドメゾン芝公園302号室")
    assert res.label().lines == ("東京都港区芝公園4-2-8", "グランドメゾン芝公園 302号室")
    narrow = res.label(width=10)
    assert narrow.lines == ("東京都港区", "芝公園4-2-8", "グランドメゾン芝公園") and not narrow.fits
    assert narrow.overflow == "302号室"
    assert res.label(width=12, fullwidth=True).lines[1] == "芝公園４－２－８"
    assert all(len(x.encode("cp932")) <= 16 for x in res.label(width=16, count="bytes", max_lines=9).lines)
    assert res.label(postal_line=True).lines[0] == "〒105-0011"
    assert jaden.normalize("北海道虻田郡倶知安町南1条西1丁目").label(width=8).lines == ("北海道虻田郡", "倶知安町", "南1条西1丁目")


def test_label_never_cuts_inside_a_number_when_it_can_help_it() -> None:
    lines = jaden.normalize("東京都港区芝公園4-2-8 グランドメゾン芝公園12345号室").label(width=13, max_lines=9).lines
    assert "グランドメゾン芝公園" in lines and any(x.startswith("12345") for x in lines)
    with pytest.raises(ValueError):
        jaden.normalize("東京都港区芝公園4-2-8").label(width=2)


def test_label_in_the_api_and_cli(capsys) -> None:
    from jaden.cli import main
    from jaden.server import JadenApi
    out = JadenApi().handle("/v1/label", {"q": "東京都港区芝公園4-2-8 グランドメゾン芝公園302", "width": "10"})
    assert out["lines"][0] == "東京都港区" and out["fits"] is False
    assert main(["normalize", "東京都港区芝公園4-2-8", "--label", "20x2"]) == 0
    assert capsys.readouterr().out.strip() == "東京都港区芝公園4-2-8"
    assert main(["normalize", "東京都港区芝公園4-2-8 グランドメゾン芝公園302", "--label", "6x1"]) == 1


# ---------------------------------------------------------------- F9: refresh the MIC municipality list
_MIC_PAGE = ('<li>「都道府県コード及び市区町村コード」<br />（令和9年1月1日更新）<ul>'
             '<li><a href="/main_content/000000001.pdf">PDF</a></li><li><a href="/main_content/{name}">Excel</a></li>')


def _mic_copy(tmp_path, name: str, edit=None):
    import zipfile
    from pathlib import Path
    src = Path(jaden.__file__).parent / "data" / "soumu_000925835.xlsx"
    if not src.exists():
        pytest.skip("the source list is not in this checkout")
    cache = tmp_path / "cache"
    cache.mkdir(exist_ok=True)
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(cache / name, "w", zipfile.ZIP_STORED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if edit and item.filename == "xl/sharedStrings.xml":
                data = edit(data)
            zout.writestr(item.filename, data)
    return cache


def test_mic_page_link_is_found() -> None:
    from jaden.data.build_municipalities import decode_page, find_latest_list
    html = decode_page(_MIC_PAGE.format(name="000925835.xlsx").encode("cp932"))
    assert find_latest_list(html) == ("https://www.soumu.go.jp/main_content/000925835.xlsx", "令和9年1月1日更新")
    assert find_latest_list("<p>nothing here</p>") is None


def test_mic_refresh_writes_a_changed_list_and_the_registry_reads_it(tmp_path, monkeypatch) -> None:
    from jaden.data.build_municipalities import refresh
    from jaden.data.loader import AddressDataRegistry
    name = "000999999.xlsx"
    cache = _mic_copy(tmp_path, name, lambda d: d.replace("千代田区".encode(), "新千代田区".encode(), 1))
    out = tmp_path / "data"
    result = refresh(out, cache, log=lambda m: None, index_html=_MIC_PAGE.format(name=name))
    assert result["changed"] and result["records"] == 1918 and result["added"] == result["removed"] == []
    monkeypatch.setenv("JADEN_DATA_DIR", str(out))
    registry = AddressDataRegistry()
    registry.load_all()
    assert registry.get_municipality_by_code("131016").name == "新千代田区"


def test_mic_refresh_keeps_the_bundled_list_when_nothing_changed(tmp_path) -> None:
    import shutil
    from pathlib import Path
    from jaden.data.build_municipalities import refresh
    src = Path(jaden.__file__).parent / "data" / "soumu_000925835.xlsx"
    if not src.exists():
        pytest.skip("the source list is not in this checkout")
    (tmp_path / "cache").mkdir()
    shutil.copy(src, tmp_path / "cache" / "000925835.xlsx")
    out = tmp_path / "data"
    out.mkdir()
    (out / "municipalities.json").write_text("[]")      # left by an earlier refresh
    result = refresh(out, tmp_path / "cache", log=lambda m: None, index_html=_MIC_PAGE.format(name="000925835.xlsx"))
    assert not result["changed"] and not (out / "municipalities.json").exists()


def test_mic_refresh_rejects_a_broken_download(tmp_path) -> None:
    from jaden.data.build_municipalities import refresh
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "000000002.xlsx").write_bytes(b"not a zip")
    with pytest.raises(RuntimeError, match="bundled list stays"):
        refresh(tmp_path / "data", tmp_path / "cache", log=lambda m: None,
                index_html=_MIC_PAGE.format(name="000000002.xlsx"))
    assert not (tmp_path / "data" / "municipalities.json").exists()


# ---------------------------------------------------------------- final scan, round 1: kana input (H1, M2, M9)
@pytest.mark.parametrize("text, lg, canonical", [
    ("ならしのだい1-2", "122041", "千葉県船橋市習志野台1丁目2番"),
    ("ちょうふしんしおうじちょう1-2", "352012", "山口県下関市長府新四王司町1番2号"),
    ("ほっかいどうあさひかわししゅんこうだい4じょう4-2-4", "012041", "北海道旭川市春光台四条4丁目2番4号"),
    ("ながのけんしおじりしだいもん7ばんちょう13-24", "202151", "長野県塩尻市大門七番町13番24号"),
    ("ほっかいどうさっぽろしちゅうおうくきた1じょうにし2ちょうめ1-1", "011011", "北海道札幌市中央区北1条西2丁目1番1号"),
    ("おおさかふおおさかしきたく梅田3-1-1", "271276", "大阪府大阪市北区梅田3丁目1番1号"),
    ("とうきょうと港区芝公園4-2-8", "131032", "東京都港区芝公園4丁目2番8号"),
    ("みやぎけんいわぬましたけくま1-2", "042111", "宮城県岩沼市字武隈1番地の2"),
])
def test_kana_reads_the_right_town(text: str, lg: str, canonical: str) -> None:
    assert jaden.validate(text).lg_code == lg and jaden.normalize(text).canonical == canonical


@pytest.mark.parametrize("text", ["さかえまち1-2", "かみちょう1-2", "あさひ1-2", "つきのわ1-2", "うめだ3-1-1",
                                  "ふちゅうしふちゅうちょう1-1"])
def test_kana_with_several_readings_is_not_guessed(text: str) -> None:
    assert jaden.validate(text).status == "AMBIGUOUS"


def test_kana_town_homophones_inside_one_city_keep_the_city_only() -> None:
    res = jaden.normalize("にいがたしこうなんくそがわ1-2")
    assert res.components.lg_code == "151041" and res.components.town_verified is not True
    assert any("曽川" in n and "楚川" in n for n in res.notes)


def test_random_kana_readings_never_land_in_another_municipality() -> None:
    import random
    from jaden.data.gazetteer import get_gazetteer
    from jaden.data.loader import get_registry
    from jaden.lookup import _muni_kana
    gaz, reg = get_gazetteer(), get_registry()

    def hira(s: str) -> str:
        return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
    munis = [m for m in reg.list_municipalities() if _muni_kana(m)]
    prefs = {p.code: p.kana for p in reg.list_all_prefectures()}
    rnd = random.Random(20261123)
    wrong = []
    for i in range(600):
        m = rnd.choice(munis)
        towns = [e for v in gaz.towns_by_kana(m.lg_code).values() for e in v if e.kana and not e.kana[-1].isdigit()]
        if not towns:
            continue
        e = rnd.choice(towns)
        text = hira(e.kana) + "1-2"
        if i % 3:
            text = hira(_muni_kana(m)) + text
        if i % 3 == 2:
            text = hira(prefs[m.prefecture_code]) + text
        v = jaden.validate(text)
        other = reg.get_municipality_by_code(v.lg_code) if v.lg_code else None
        if v.status == "ACCEPTED" and other and other.lg_code != m.lg_code and \
                not (other.city == m.city and other.prefecture_code == m.prefecture_code):
            wrong.append((text, m.name, e.name, other.name))
    assert wrong == []


def test_check_fields_reads_kana_fields_and_its_status_agrees_with_valid() -> None:
    r = jaden.check_fields(prefecture="とうきょうと", city="みなとく", line1="しばこうえん4-2-8")
    assert r.valid and r.status == "ACCEPTED" and r.fields["line1"] == "芝公園4丁目2番8号"
    r = jaden.check_fields(prefecture="東京都", city="とうきょうとみなとく", line1="芝公園4-2-8")
    assert r.valid and r.fields["city"] == "港区"
    r = jaden.check_fields(postal_code="100-0001", prefecture="東京都", city="港区", line1="芝公園4-2-8")
    assert (r.status, r.reason, r.valid) == ("MALFORMED", "POSTAL_CODE_MISMATCH", False)
    assert jaden.check_fields(postal_code=1050011, city="港区", line1="芝公園4-2-8").valid
    assert jaden.check_fields(postal_code=600063.0, prefecture="北海道", city="札幌市中央区", line1="南3条西1-2").valid


# ---------------------------------------------------------------- final scan, round 1: hostile and Japanese .xlsx (H2, H3)
def _xlsx(tmp_path, sheet: str, shared: str = "", name: str = "t.xlsx", compress: bool = True):
    import zipfile
    from jaden.xlsx import _NS
    path = tmp_path / name
    head = '<?xml version="1.0" encoding="UTF-8"?>'
    files = {
        "[Content_Types].xml": head + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "xl/workbook.xml": head + f'<workbook xmlns="{_NS["m"]}" xmlns:r="{_NS["r"]}"><sheets>'
                           '<sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": head + f'<Relationships xmlns="{_NS["rel"]}"><Relationship Id="rId1" '
                                      'Type="x" Target="worksheets/sheet1.xml"/></Relationships>',
        "xl/worksheets/sheet1.xml": head + f'<worksheet xmlns="{_NS["m"]}"><sheetData>{sheet}</sheetData></worksheet>',
    }
    if shared:
        files["xl/sharedStrings.xml"] = head + f'<sst xmlns="{_NS["m"]}">{shared}</sst>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED) as z:
        for k, v in files.items():
            z.writestr(k, v)
    return path


def test_xlsx_furigana_is_not_part_of_the_text(tmp_path) -> None:
    from jaden.xlsx import read_xlsx
    shared = ('<si><t>東京都港区芝公園4-2-8</t><rPh sb="0" eb="3"><t>トウキョウト</t></rPh><rPh sb="3" eb="5"><t>ミナトク</t></rPh>'
              '<phoneticPr fontId="1"/></si><si><r><t>港区</t></r><r><t>芝公園</t></r><rPh sb="0" eb="2"><t>ミナトク</t></rPh></si>')
    path = _xlsx(tmp_path, '<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row>', shared)
    assert read_xlsx(path) == [["東京都港区芝公園4-2-8", "港区芝公園"]]


@pytest.mark.parametrize("sheet, message", [
    ('<row r="300000000"><c r="A300000000"><v>1</v></c></row>', "limit"),
    ('<row r="1"><c r="ZZZZZZ1"><v>1</v></c></row>', "limit"),
    ('<row r="2"><c r="A2"><v>1</v></c></row><row r="1"><c r="A1"><v>1</v></c></row>', "order"),
    ('<row r="1"><c r="A1"><v>1</v></row>', "not valid XML"),
])
def test_xlsx_hostile_sheets_are_refused_quickly(tmp_path, sheet: str, message: str) -> None:
    from jaden.xlsx import read_xlsx
    started = time.perf_counter()
    with pytest.raises(ValueError, match=message):
        read_xlsx(_xlsx(tmp_path, sheet))
    assert time.perf_counter() - started < 2


def test_xlsx_zip_bomb_dtd_and_missing_parts_are_refused(tmp_path) -> None:
    import zipfile
    from jaden.xlsx import read_xlsx
    bomb = _xlsx(tmp_path, '<row r="1"><c r="A1"><v>1</v></c></row>' + " " * 50_000_000, name="bomb.xlsx")
    with pytest.raises(ValueError, match="too large"):
        read_xlsx(bomb)
    dtd = tmp_path / "dtd.xlsx"
    with zipfile.ZipFile(_xlsx(tmp_path, "", name="src.xlsx")) as zin, zipfile.ZipFile(dtd, "w") as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item == "xl/worksheets/sheet1.xml":
                data = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><worksheet/>'
            zout.writestr(item, data)
    with pytest.raises(ValueError, match="DTD"):
        read_xlsx(dtd)
    broken = tmp_path / "broken.xlsx"
    with zipfile.ZipFile(broken, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    with pytest.raises(ValueError, match="missing"):
        read_xlsx(broken)


def test_xlsx_errors_reach_the_cli_as_a_message(tmp_path, capsys) -> None:
    from jaden.cli import main
    path = tmp_path / "bad.xlsx"
    path.write_bytes(b"PK\x03\x04 broken")
    assert main(["batch", str(path)]) == 64
    assert "Error:" in capsys.readouterr().err


# ---------------------------------------------------------------- final scan, round 1: rooms and buildings (H4, M1, M3)
def test_wing_and_room_written_after_the_name_keep_flats_apart() -> None:
    p = "東京都港区芝公園4-2-8 "
    rows = [p + "コーポ1-201", p + "コーポ1-202", p + "コーポ 1-203", p + "ハイツ山田2-101", p + "コーポ1 201号室",
            p + "第2コーポ201"]
    assert jaden.find_duplicates(rows) == [1, 2, 3, 4, 1, 5]   # 第2コーポ201 is room 201 without a wing
    assert jaden.compare(rows[0], rows[4]).verdict == "same"
    c = jaden.normalize(rows[0]).components
    assert (c.building, c.unit) == ("コーポ", "1-201")


def test_duplicate_pairs_cover_a_large_building_without_a_silent_cap() -> None:
    p = "東京都港区芝公園4-2-8 グランドメゾン芝公園"
    rows = [f"{p}{100 + i}" for i in range(400)] + [f"{p}{499}号室"]
    report: dict = {}
    pairs = jaden.duplicate_pairs(rows, report=report)
    assert [(x.i, x.j, x.score) for x in pairs] == [(399, 400, 1.0)] and report["truncated"] is False
    assert report["comparisons"] < 1000          # rooms are bucketed, not compared all against all


def test_different_rooms_are_not_reported_as_duplicates() -> None:
    p = "東京都港区芝公園4-2-8 グランドメゾン芝公園"
    assert jaden.duplicate_pairs([p + "301", p + "302"]) == []


@pytest.mark.parametrize("text, building", [("京都府宇治市五ヶ庄3番割31-11", "番割31-11"), ("奈良県奈良市朱雀5町目3-10", "町目3-10")])
def test_place_names_before_a_lot_are_not_wing_and_room(text: str, building: str) -> None:
    c = jaden.normalize(text).components
    assert (c.building, c.unit) == (building, None)


# ---------------------------------------------------------------- final scan, round 1: acceptance and cleaning (M5-M8, M11)
def test_lone_surrogates_and_invisible_marks_are_removed() -> None:
    for text in ("港区芝公園4-2-8\ud800", "港区芝公️園4-2-8", "港区芝公͏園4-2-8", "港区芝公￼園4-2-8",
                 "港区芝公ㅤ園4-2-8", "港区芝公\U000e0101園4-2-8"):
        res = jaden.normalize(text)
        assert res.canonical == "東京都港区芝公園4丁目2番8号", text
        res.to_json().encode("utf-8")


def test_surrogates_do_not_break_outputs(tmp_path) -> None:
    import io
    from jaden.batch import run_batch
    from jaden.frame import stream
    from jaden.server import JadenApi
    src = tmp_path / "s.jsonl"
    src.write_text(json.dumps({"address": "港区芝公園4-2-8 ビル\ud800"}) + "\n", encoding="utf-8")
    run_batch(src, tmp_path / "out.csv", log=io.StringIO())
    run_batch(src, tmp_path / "out.xlsx", log=io.StringIO())
    out = io.StringIO()
    assert stream(io.StringIO(json.dumps("港区芝公園4-2-8\ud800") + "\n" + "港区芝公園4-2-8\n"), out) == 2
    assert JadenApi().handle("/v1/normalize", {"q": "港区芝公園4-2-8\ud800"})["status"] == "ACCEPTED"


@pytest.mark.parametrize("text, canonical", [
    ("港区芝公園4-2、8", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4丁目2番、8号", "東京都港区芝公園4丁目2番8号"),
    ("1050011東京都港区芝公園4-2-8", "東京都港区芝公園4丁目2番8号"),
    ("岡山県岡山市北区大供10之1番地", "岡山県岡山市北区大供10番地の1"),
    ("岡山県岡山市北区大供10ノ1番地", "岡山県岡山市北区大供10番地の1"),
    ("東京都港区芝公園4-2-8 TEL/FAX 03-1234-5678", "東京都港区芝公園4丁目2番8号"),
    ("東京都港区芝公園4-2-8 携帯 090-1234-5678", "東京都港区芝公園4丁目2番8号"),
    ("広島市県広島市安佐南区伴東7丁目55番9号", "広島県広島市安佐南区伴東7丁目55番9号"),
    ("群馬県吾妻郡中之条町中之条町1395-1", "群馬県吾妻郡中之条町中之条町1395番地の1"),
])
def test_separators_and_old_spellings_read_as_meant(text: str, canonical: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical
    assert jaden.match_key(text) == jaden.match_key(res.canonical)
    assert jaden.normalize(res.canonical).canonical == canonical


@pytest.mark.parametrize("text", ["横浜市立第3中学校", "向日市立第４向陽小学校", "札幌市立白石中学校"])
def test_facility_names_with_numbers_are_not_addresses(text: str) -> None:
    assert jaden.validate(text).reason == "NAME_NOT_ADDRESS"


def test_a_town_of_another_ward_is_flagged_and_the_right_one_offered() -> None:
    v = jaden.validate("東京都新宿区芝公園4-2-8")
    assert v.suggestions == ("東京都港区芝公園4丁目2番8号",)
    r = jaden.check_fields(prefecture="東京都", city="新宿区", line1="芝公園4-2-8")
    assert not r.valid and r.reason == "CITY_MISMATCH" and r.issues[0].suggestion == "港区"
    assert not any(i.field == "postal_code" for i in r.issues)


def test_a_designated_city_without_its_ward_is_not_accepted_with_the_city_code() -> None:
    v = jaden.validate("広島県広島市ほげ1-1")
    assert v.status == "AMBIGUOUS" and len(v.ambiguous_candidates) == 8
    assert jaden.validate("広島県広島市伴東7丁目55-9").lg_code == "341053"


@pytest.mark.parametrize("text", ["大阪府堺市南区茶山台99-5-1", "大阪府堺市南区茶山台4-5-1", "大阪府堺市南区晴美台5-1-1"])
def test_chome_beyond_a_numbered_town_family_does_not_exist(text: str) -> None:
    assert jaden.validate(text).reason == "NONEXISTENT_CHOME"
    assert jaden.validate("大阪府堺市南区茶山台2-5-1").status == "ACCEPTED"


# ---------------------------------------------------------------- final scan, round 1: files, labels, server, MCP, CLI
def test_jsonl_to_csv_keeps_every_key_and_csv_to_jsonl_every_value(tmp_path) -> None:
    import csv
    import io
    from jaden.batch import run_batch
    src = tmp_path / "in.jsonl"
    src.write_text('{"address": "港区芝公園4-2-8", "id": 1}\n'
                   '{"address": "府中市1-1", "id": 2, "phone": "03-1111", "tags": ["a", "b"]}\n', encoding="utf-8")
    run_batch(src, tmp_path / "out.csv", log=io.StringIO())
    rows = list(csv.DictReader(open(tmp_path / "out.csv", encoding="utf-8")))
    assert rows[1]["phone"] == "03-1111" and json.loads(rows[1]["tags"]) == ["a", "b"]
    src = tmp_path / "in.csv"
    src.write_text("住所,メモ,メモ\n港区芝公園4-2-8,a,b,c\n", encoding="utf-8")
    run_batch(src, tmp_path / "out.jsonl", log=io.StringIO())
    row = json.loads(open(tmp_path / "out.jsonl", encoding="utf-8").readline())
    assert {k: row[k] for k in ("住所", "メモ", "メモ_2", "column4")} == \
        {"住所": "港区芝公園4-2-8", "メモ": "a", "メモ_2": "b", "column4": "c"}


def test_labels_keep_every_line_within_the_width() -> None:
    res = jaden.normalize("東京都港区芝公園4-2-8 グランドメゾン芝公園302号室")
    for width in range(4, 30):
        for kw in ({}, {"postal_line": True}, {"fullwidth": True}, {"count": "bytes"}, {"style": "en"}):
            label = res.label(width=width, max_lines=9, **kw)
            measure = (lambda t: len(t.encode("cp932"))) if kw.get("count") == "bytes" else len
            assert all(measure(line) <= width for line in label.lines), (width, kw, label.lines)
    assert res.label(width=12, fullwidth=True).lines[1] == "芝公園４－２－８"
    assert res.label(width=9, fullwidth=True).overflow == "園　３０２号室"
    en = res.label(width=30, max_lines=5, style="en").lines
    assert "".join(en).count("グランドメゾン") == 1 and "4-2-8 Shibakoen, Minato-ku," in en


def test_extract_stops_at_the_next_postal_code() -> None:
    found = jaden.extract_addresses("〒105-0011東京都港区芝公園4-2-8〒160-0023東京都新宿区西新宿2-8-1")
    assert [x.to_dict()["text"] for x in found] == ["〒105-0011東京都港区芝公園4-2-8", "〒160-0023東京都新宿区西新宿2-8-1"]


def test_bom_less_utf16_and_integer_postal_codes(tmp_path) -> None:
    from jaden.batch import read_text
    for enc in ("utf-16-le", "utf-16-be"):
        path = tmp_path / f"{enc}.txt"
        path.write_bytes("東京都港区芝公園4-2-8\n大阪府大阪市北区梅田3-1-1\n".encode(enc))
        assert read_text(path, None).startswith("東京都港区")
    assert jaden.lookup_postal(600063) and jaden.lookup_postal(600063)[0].postal_code == "060-0063"


def test_pandas_helper_reuses_its_engine_and_replaces_earlier_results() -> None:
    pd = pytest.importorskip("pandas")
    from jaden.frame import normalize_frame, records
    started = time.perf_counter()
    for _ in range(100):
        list(records(["港区芝公園4-2-8"]))
    assert time.perf_counter() - started < 2
    df = pd.DataFrame({"住所": ["港区芝公園4-2-8"], "name": ["x"]}, index=[5])
    once = normalize_frame(df, "住所")
    twice = normalize_frame(once, "住所")
    assert list(twice.columns).count("jaden_status") == 1
    names = pd.Series(["a", "b"], index=[6, 5])
    from jaden.frame import normalize_series
    out = normalize_series(pd.Series(["錦町1番2号"], index=[5]), resolve=True, names=names)
    assert list(out.index) == [5]


def test_server_rejects_non_json_and_chunked_bodies_and_takes_numbers(base_server) -> None:
    import http.client
    host, port = base_server
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("POST", "/v1/normalize", body=b'{"q": "x"}', headers={"Content-Type": "text/plain; a=json"})
    assert conn.getresponse().status == 415
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.putrequest("POST", "/v1/normalize")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Transfer-Encoding", "chunked")
    conn.endheaders()
    conn.send(b"a\r\n{\"q\":\"x\"}\r\n0\r\n\r\n")
    assert conn.getresponse().status == 411
    conn = http.client.HTTPConnection(host, port, timeout=5)
    conn.request("POST", "/v1/reverse", body=json.dumps({"lat": 35.6586, "lon": 139.7454}).encode(),
                 headers={"Content-Type": "application/json; charset=utf-8"})
    resp = conn.getresponse()
    assert resp.status == 200 and json.loads(resp.read())["results"]


def test_server_caps_concurrent_connections(monkeypatch) -> None:
    import socket
    import threading
    import jaden.server as srv
    monkeypatch.setattr(srv, "MAX_CONNECTIONS", 4)
    server = srv.create_server(port=0, quiet=True, warm_up=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    host, port = server.server_address[:2]
    idle = [socket.create_connection((host, port)) for _ in range(4)]
    time.sleep(0.3)
    extra = socket.create_connection((host, port))
    extra.settimeout(5)
    assert b"503" in extra.recv(200)
    for s in idle + [extra]:
        s.close()
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def base_server():
    import threading
    from jaden.server import create_server
    server = create_server(port=0, quiet=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[:2]
    server.shutdown()
    server.server_close()


def test_mcp_checks_argument_types_ids_and_empty_batches() -> None:
    replies = _mcp("[]", {"jsonrpc": "2.0", "id": {"x": 1}, "method": "ping"},
                   {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": ["x"]}},
                   {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "normalize_address", "arguments": {"address": "港区芝公園4-2-8", "strict": "false"}}})
    assert replies[0]["error"]["code"] == -32600 and replies[1]["error"]["code"] == -32600
    assert replies[2]["error"]["code"] == -32602
    assert replies[3]["result"]["isError"] and "boolean" in replies[3]["result"]["content"][0]["text"]


@pytest.mark.parametrize("args", [["batch", "x.csv", "--jobs", "0"], ["dedupe", "x.csv", "--min-score", "5"],
                                  ["batch", "x.csv", "--name-column", "n"]])
def test_cli_refuses_bad_option_values(args) -> None:
    from jaden.cli import main
    try:
        code = main(args)
    except SystemExit as exc:
        code = exc.code
    assert code in (2, 64)


# ---------------------------------------------------------------- audit round 2: rooms, wings, buildings
P = "東京都港区芝公園4-2-8 "


@pytest.mark.parametrize("a, b", [("A-201号室", "B-201号室"), ("1-201号室", "2-201号室"), ("201室", "202室"),
                                  ("パレス壱番館101", "パレス弐番館101")])
def test_different_flats_get_different_keys(a: str, b: str) -> None:
    assert jaden.match_key(P + a) != jaden.match_key(P + b)
    assert jaden.compare(P + a, P + b).verdict != "same"
    assert jaden.find_duplicates([P + a, P + b]) == [1, 2]


@pytest.mark.parametrize("forms", [("A-201号室", "A-201", "A201", "A棟201", "コーポA 201号室"),
                                   ("201室", "201号室", "２０１室", "Apt 201", "#201"),
                                   ("パレス壱番館101", "パレス一番館101", "パレス1番館 101号室"),
                                   ("ライオンズマンション第2-305", "ライオンズマンション第2 305号室")])
def test_one_flat_written_several_ways_gets_one_key(forms) -> None:
    assert len({jaden.match_key(P + f) for f in forms}) == 1


@pytest.mark.parametrize("text, canonical", [
    ("東京都港区芝公園4丁目 201号室", "東京都港区芝公園4丁目 201号室"),
    ("北海道札幌市北区北11条西7丁目 703号室", "北海道札幌市北区北11条西7丁目 703号室"),
    ("北海道札幌市北区北11条西7丁目 中央ビルディング 3F", "北海道札幌市北区北11条西7丁目 中央ビルディング 3F"),
    ("北海道網走市潮見188 Apt 703", "北海道網走市潮見188番 703号室"),
    ("北海道網走市潮見188 703", "北海道網走市潮見188番 703号室"),
])
def test_a_room_after_an_open_number_stays_a_room(text: str, canonical: str) -> None:
    res = jaden.normalize(text)
    assert res.canonical == canonical
    assert jaden.normalize(res.canonical).canonical == canonical
    assert jaden.normalize(res.format("hyphen")).canonical == canonical
    assert jaden.match_key(text) == jaden.match_key(canonical)


def test_check_fields_keeps_a_room_line_as_the_room() -> None:
    r = jaden.check_fields(prefecture="東京都", city="港区", line1="芝公園4丁目", line2="201号室")
    assert r.fields["line1"] == "芝公園4丁目" and r.fields["line2"] == "201号室"


def test_duplicate_pairs_stay_fast_for_one_large_building() -> None:
    import random
    rows = [P + f"{100 + i}" for i in range(3000)] + [P] * 900
    random.Random(1).shuffle(rows)
    started = time.perf_counter()
    report: dict = {}
    pairs = jaden.duplicate_pairs(rows, report=report)
    assert time.perf_counter() - started < 20
    assert len(pairs) == 899 and report["comparisons"] < 5000      # the copies, linked to one of them


# ---------------------------------------------------------------- audit round 2: engine, kana, English, geocoding
def test_numbers_without_a_town_are_not_a_house() -> None:
    v, r = jaden.validate("東京都新宿区1-1"), jaden.normalize("東京都新宿区1-1")
    assert r.precision == "municipality" and any("no town is written" in w for w in v.warnings)
    assert not any("no block or lot number" in w for w in v.warnings)
    for whole in ("長野県上伊那郡南箕輪村6744-7-2", "福島県南会津郡檜枝岐村1234"):   # numbered across the village
        assert jaden.normalize(whole).precision in ("house", "block")
    v = jaden.validate("広島県広島市1-1")
    assert v.status == "AMBIGUOUS" and len(v.ambiguous_candidates) == 8
    assert jaden.validate("広島県広島市").status == "ACCEPTED"


@pytest.mark.parametrize("text, canonical", [
    ("北海道旭川市しゅんこうだい4じょう1-2-3", "北海道旭川市春光台四条1丁目2番3号"),
    ("北海道岩見沢市みなみまち1じょう1-2", "北海道岩見沢市南町一条1丁目2番"),
    ("北海道札幌市中央区きた1じょうにし2ちょうめ1-1", "北海道札幌市中央区北1条西2丁目1番1号"),
    ("北海道札幌市白石区本郷通6-南1-1", "北海道札幌市白石区本郷通六丁目南1番1号"),
])
def test_kana_and_short_town_forms_after_a_kanji_municipality(text: str, canonical: str) -> None:
    assert jaden.normalize(text).canonical == canonical and jaden.validate(text).status == "ACCEPTED"


@pytest.mark.parametrize("english", [
    "#101, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011",
    "Room 101, 4-2-8 Shibakoen, Minato-ku, Tokyo",
    "グランドメゾン芝公園 #101, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011",
])
def test_english_lines_with_a_building_or_room_first(english: str) -> None:
    res = jaden.normalize(english)
    assert res.components.lg_code == "131032" and res.components.town == "芝公園"
    assert res.components.unit and "101" in res.components.unit


def test_jadens_own_english_line_reads_back_to_the_same_key() -> None:
    bad = []
    bench = Path(__file__).resolve().parents[1] / "benchmarks" / "jabench" / "jabench.jsonl"
    with open(bench, encoding="utf-8") as fh:
        rows = [json.loads(line)["input"] for i, line in enumerate(fh) if i % 60 == 0]
    for text in rows:
        for tail in ("", " グランドメゾン302", " 302号室"):
            res = jaden.normalize(text + tail)
            if res.romaji and jaden.validate(text).status == "ACCEPTED":
                back = jaden.normalize(res.romaji)
                if jaden.match_key(back) != jaden.match_key(res):
                    bad.append((text + tail, res.romaji, back.canonical))
    assert len(bad) <= len(rows) // 50, bad[:5]      # a few registry towns have no reading to write


def test_english_keeps_an_unregistered_town_and_a_koaza() -> None:
    assert "常磐町" in jaden.normalize("北海道北見市常磐町3-8-4").romaji
    assert "字大作平" in jaden.normalize("青森県八戸市鮫町字大作平44-29").romaji


def test_reverse_geocode_far_away_is_quick() -> None:
    started = time.perf_counter()
    jaden.reverse_geocode(10, 100, max_km=5000)
    found = jaden.reverse_geocode(-1.85, -121.36, max_km=1e9)
    assert time.perf_counter() - started < 5 and found and found[0].distance_m < 20_037_000


def test_check_fields_gives_no_postal_code_for_a_town_in_another_city() -> None:
    r = jaden.check_fields(prefecture="東京都", city="新宿区", line1="芝公園4-2-8")
    assert r.fields["postal_code"] == "" and r.reason == "CITY_MISMATCH"


# ---------------------------------------------------------------- audit round 2: files, server, labels
def test_xlsx_sparse_wide_rows_strict_ooxml_and_late_dtd(tmp_path) -> None:
    import zipfile
    from jaden.xlsx import read_xlsx
    wide = "".join(f'<row r="{i}"><c r="XFD{i}"><v>1</v></c></row>' for i in range(1, 2001))
    with pytest.raises(ValueError, match="too wide"):
        import jaden.xlsx as xl
        old, xl.MAX_MATERIALIZED = xl.MAX_MATERIALIZED, 1_000_000
        try:
            read_xlsx(_xlsx(tmp_path, wide, name="wide.xlsx"))
        finally:
            xl.MAX_MATERIALIZED = old
    strict = tmp_path / "strict.xlsx"
    ns, rns = "http://purl.oclc.org/ooxml/spreadsheetml/main", "http://purl.oclc.org/ooxml/officeDocument/relationships"
    with zipfile.ZipFile(strict, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{rns}"><sheets><sheet name="S" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="x" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="b1" t="inlineStr">'
                   '<is><t>住所</t></is></c></row></sheetData></worksheet>')
    assert read_xlsx(strict) == [["", "住所"]]
    late = tmp_path / "late.xlsx"
    with zipfile.ZipFile(_xlsx(tmp_path, "", name="base.xlsx")) as zin, zipfile.ZipFile(late, "w") as zout:
        for item in zin.namelist():
            data = zin.read(item)
            if item.endswith("sheet1.xml"):
                data = b'<?xml version="1.0"?><!--' + b"x" * 5000 + b'--><!DOCTYPE w [<!ENTITY a "a">]><worksheet/>'
            zout.writestr(item, data)
    with pytest.raises(ValueError, match="DTD"):
        read_xlsx(late)


def test_rows_longer_than_the_header_keep_the_result_columns_in_place(tmp_path) -> None:
    import csv
    import io
    from jaden.batch import run_batch, run_dedupe
    src = tmp_path / "in.csv"
    src.write_text("id,住所,note\n1,東京都港区芝公園4-2-8,x,EXTRA\n2,府中市1-1,y\n", encoding="utf-8")
    for run in (run_batch, run_dedupe):
        run(src, tmp_path / "out.csv", log=io.StringIO())
        rows = list(csv.DictReader(open(tmp_path / "out.csv", encoding="utf-8")))
        assert rows[0]["column4"] == "EXTRA" and rows[0]["jaden_status"] == "ACCEPTED"


def test_output_encoding_is_checked_and_applied(tmp_path, capsys) -> None:
    from jaden.cli import main
    src = tmp_path / "in.csv"
    src.write_text("住所\n東京都港区芝公園4-2-8\n", encoding="utf-8")
    assert main(["batch", str(src), "--output-encoding", "bogus", "-o", str(tmp_path / "x.csv")]) == 64
    assert "unknown output encoding" in capsys.readouterr().err


def test_server_fields_take_a_numeric_postal_code_and_label_takes_a_style() -> None:
    from jaden.server import JadenApi
    api = JadenApi()
    assert api.handle("/v1/fields", {"postal_code": 1050011, "city": "港区", "line1": "芝公園4-2-8"})["valid"]
    assert api.handle("/v1/label", {"q": "東京都港区芝公園4-2-8", "style": "en", "width": "30"})["lines"][0].startswith("4-2-8")
    spec = api.handle("/v1/openapi.json", {})
    assert any(p["name"] == "style" for p in spec["paths"]["/v1/label"]["get"]["parameters"])
    assert "/v1/postal" in spec["paths"]


def test_english_labels_print_the_postal_code_once_and_keep_words_whole() -> None:
    res = jaden.normalize("三重県伊勢市楠部町2484")
    lines = res.label(width=20, style="en", postal_line=True).lines
    assert "".join(lines).count("516-0014") == 1
    lines = jaden.normalize("東京都港区芝公園4-2-8").label(width=12, style="en", max_lines=9).lines
    assert "Shibakoen," in lines and all(len(x) <= 12 for x in lines)


def test_a_grid_inside_a_longer_town_name_is_not_split() -> None:
    res = jaden.normalize("北海道標津郡中標津町計根別南二条東１丁目２番地１")
    assert res.components.town_verified and res.canonical.startswith("北海道標津郡中標津町計根別南二条東1丁目")
    assert res.components.postal_code == "088-2682"


# ---------------------------------------------------------------- audit round 3
@pytest.mark.parametrize("japanese", ["茨城県筑西市大林100", "千葉県佐倉市井野100", "秋田県秋田市上北手小山田100",
                                      "石川県小松市小野町152-2"])
def test_english_lines_of_towns_spelled_alike_read_back_by_postal_code(japanese: str) -> None:
    res = jaden.normalize(japanese)
    assert jaden.match_key(jaden.normalize(res.romaji)) == jaden.match_key(res)


def test_english_towns_spelled_alike_without_a_postal_code_are_not_guessed() -> None:
    res = jaden.normalize("100 Obayashi, Chikusei-shi, Ibaraki")
    assert res.components.town is None
    assert any("several spellings" in n for n in res.notes)


@pytest.mark.parametrize("japanese", [
    "東京都港区芝公園4-2-8 1-201号室", "長野県下伊那郡喬木村1396-2 サンハイツけやき1505",
    "北海道旭川市6条通22-4-46 エステートサンライズ703", "佐賀県佐賀市本庄町1 フラット青葉405",
    "岩手県盛岡市下飯岡8地割99", "石川県七尾市佐味町10部4", "佐賀県佐賀市本庄町1", "京都府福知山市石原上野45"])
def test_more_english_lines_read_back(japanese: str) -> None:
    res = jaden.normalize(japanese)
    assert jaden.match_key(jaden.normalize(res.romaji)) == jaden.match_key(res), res.romaji


@pytest.mark.parametrize("text, building, unit", [
    ("秋田県大仙市神宮寺字荒屋20番地 305室", None, "305室"),
    ("北海道網走市潮見188番地 2号棟305号室", "2号棟", "305号室"),
    ("北海道網走市潮見188番地 1号館305号室", "1号館", "305号室"),
    ("東京都港区芝公園4丁目2番 305室", None, "305室"),
])
def test_rooms_and_wings_after_an_open_number(text: str, building, unit: str) -> None:
    c = jaden.normalize(text).components
    assert (c.building, c.unit) == (building, unit)


def test_wing_and_room_after_an_open_number_read_back() -> None:
    res = jaden.normalize("北海道網走市潮見188 1-201号室")
    assert jaden.normalize(res.canonical).canonical == res.canonical
    assert jaden.match_key(res.canonical) == jaden.match_key("北海道網走市潮見188 1-201号室")


def test_kana_number_words_after_a_kana_town() -> None:
    assert jaden.normalize("東京都港区しばこうえん4ちょうめ2ばん8ごう").canonical == "東京都港区芝公園4丁目2番8号"
    r = jaden.check_fields(prefecture="東京都", city="港区", line1="しばこうえん4ちょうめ2ばん8ごう")
    assert r.fields["line1"] == "芝公園4丁目2番8号" and r.fields["line2"] == ""


def test_round_three_small_items(tmp_path) -> None:
    import csv as csv_module
    import io
    from jaden.batch import run_batch
    assert jaden.match_key("東京都港区芝公園4-2-8 305ごうしつ") == jaden.match_key("東京都港区芝公園4-2-8 305号室")
    assert jaden.match_key("東京都港区芝公園4丁目 1-201号室") == jaden.match_key("東京都港区芝公園4丁目1番 201号室")
    assert jaden.normalize("広島県広島市1-1").precision == "municipality"
    src = tmp_path / "huge.csv"
    src.write_text("住所,note\n東京都港区芝公園4-2-8," + "x" * 300_000 + "\n", encoding="utf-8")
    limit = csv_module.field_size_limit()
    assert run_batch(src, tmp_path / "out.xlsx", log=io.StringIO()) == {"ACCEPTED": 1}
    assert csv_module.field_size_limit() == limit


def test_xlsx_dtd_in_a_utf16_part_is_refused(tmp_path) -> None:
    import zipfile
    from jaden.xlsx import _NS, read_xlsx
    path = tmp_path / "u16.xlsx"
    ns = _NS["m"]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{_NS["r"]}"><sheets><sheet name="S" sheetId="1" '
                   'r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{_NS["rel"]}"><Relationship Id="rId1" Type="x" '
                   'Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", ('<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "x">]>'
                                                f'<worksheet xmlns="{ns}"/>').encode("utf-16"))
    with pytest.raises(ValueError, match="DTD"):
        read_xlsx(path)


@pytest.mark.parametrize("raw, canonical", [
    ("北海道札幌市中央区南五条西５丁目１３番地１－２階", "北海道札幌市中央区南5条西5丁目13番地の1 2階"),
    ("北海道札幌市中央区南二条東１丁目１番地１９ロベージＳ２Ｅ１－１階", "北海道札幌市中央区南2条東1丁目1番地の19 ロベージS2E1 1階"),
    ("大阪府堺市堺区向陵東町３丁８番１－１３１１号", "大阪府堺市堺区向陵東町三丁8番1号 1311号"),
    ("千葉県館山市湊４９３番地の２館山レアージュ６０６", "千葉県館山市湊493番地の2 館山レアージュ 606号室"),
])
def test_a_marked_number_never_ends_up_inside_the_town(raw, canonical) -> None:
    assert jaden.normalize(raw).canonical == canonical


@pytest.mark.parametrize("raw, english", [
    ("北海道札幌市中央区南五条西５丁目１３番地１", "5-13-1 Minami5-Jonishi"),
    ("群馬県桐生市相生町1-乙394", "1-chome Aioicho 乙394"),
    ("青森県弘前市松原東2-17", "2-chome-17 Matsubara Higashi"),
])
def test_english_line_keeps_every_number_and_reads_back(raw, english) -> None:
    line = jaden.normalize(raw).romaji
    assert line.startswith(english)
    assert jaden.match_key(line) == jaden.match_key(raw)


# ---------------------------------------------------------------- audit round 4
@pytest.mark.parametrize("raw, canonical, precision", [
    ("栃木県那須塩原市東赤田321-1221", "栃木県那須塩原市東赤田321番1221号", "house"),           # R4-H1 not a postal code
    ("東京都港区芝公園 2階", "東京都港区芝公園 2階", "town"),                                   # R4-H2
    ("東京都港区芝公園 101号室", "東京都港区芝公園 101号室", "town"),
    ("東京都港区芝公園 Aビル 3階", "東京都港区芝公園 Aビル 3階", "town"),
    ("兵庫県神戸市灘区摩耶埠頭摩耶業務センタービル５階", "兵庫県神戸市灘区摩耶埠頭 摩耶業務センタービル 5階", "town"),
    ("神奈川県茅ヶ崎市甘沼2723階", "神奈川県茅ヶ崎市甘沼272番 3階", "block"),
    ("北海道旭川市1条通8丁目右2号", "北海道旭川市一条通8丁目右2号", "house"),                  # R4-M3
    ("愛媛県松山市東野4丁目乙222番地30", "愛媛県松山市東野4丁目乙222-30", "house"),            # R4-M4
    ("東京都港区芝公園4 2 8", "東京都港区芝公園4丁目2番8号", "house"),                         # R4-M6
    ("東京都港区芝公園4ちょうめ2-8", "東京都港区芝公園4丁目2番8号", "house"),                   # R4-M7
    ("京都府京都市中京区寺町通御池上る上本能寺前町488 101号", "京都府京都市中京区寺町通御池上る上本能寺前町488番地 101号室", "unit"),
    ("京都府京都市中京区寺町通御池上る上本能寺前町488 1・2階", "京都府京都市中京区寺町通御池上る上本能寺前町488番地 1・2階", "house"),
    ("東京都港区芝公園4-2-8号", "東京都港区芝公園4丁目2番8号", "house"),                       # R4-L1
])
def test_round_four_parsing(raw, canonical, precision) -> None:
    res = jaden.normalize(raw)
    assert (res.canonical, res.precision) == (canonical, precision)
    assert jaden.normalize(res.canonical).canonical == res.canonical
    assert jaden.match_key(res.canonical) == jaden.match_key(raw)


def test_round_four_rooms_and_compare() -> None:
    same = lambda a, b: jaden.compare(a, b).verdict   # noqa: E731
    assert same("東京都港区芝公園4-2-8 207-1号室", "東京都港区芝公園4-2-8 307-1号室") == "same_building"   # R4-H3
    assert same("東京都港区芝公園4丁目2番8号 101A号室", "東京都港区芝公園4丁目2番8号 101B号室") == "same_building"
    assert same("東京都港区芝公園4-2-8 3F-301", "東京都港区芝公園4-2-8 3F-302") == "same_building"
    assert same("東京都港区芝公園4丁目 東京タワービル 2階", "東京都港区芝公園4丁目 メルパルク 2階") == "possibly_same"   # R4-M2
    assert same("北海道旭川市1条通8丁目右2号", "北海道旭川市1条通8丁目左2号") == "different"
    a, b = "京都府京都市中京区河原町通三条上る下丸屋町390", "京都府京都市中京区丸太町通油小路東入下丸屋町390"   # R4-M1
    assert same(a, b) == "different" and jaden.normalize(a).latitude is None
    assert same(a, "京都府京都市中京区河原町通三条上ル下丸屋町390番地") == "same"


@pytest.mark.parametrize("english, japanese", [                                               # R4-H5
    ("668,Katsura-cho, Sakae ku Yokohama shi, Kanagawa", "神奈川県横浜市栄区桂町668番"),
    ("1-1,Chuo, Konosu shi, Saitama", "埼玉県鴻巣市中央1番1号"),
    ("1-1 Kita 1-jo Nishi 2-chome, Chuo-ku, Sapporo", "北海道札幌市中央区北1条西2丁目1番1号"),
    ("1-22-5, Setagaya, Setagaya ku, Tokyo", "東京都世田谷区世田谷1丁目22番5号"),
    ("1-1 Hongo 7-chome, Bunkyo-ku, Tokyo", "東京都文京区本郷7丁目1番1号"),
])
def test_round_four_english_input(english, japanese) -> None:
    assert jaden.normalize(english).canonical == japanese


@pytest.mark.parametrize("raw", [                                                            # R4-M5, L2, L3
    "福井県敦賀市石ケ町2番地の1", "沖縄県宜野湾市宇地泊１丁目20番7号", "東京都中央区銀座4-6-16 銀座三越 B2",
    "東京都目黒区自由が丘２丁目１６‐１２ＲＪ３", "京都府京都市中京区河原町通三条上る下丸屋町390", "宮崎県西都市聖陵町1番地68",
    "大阪府堺市堺区楠町一丁5-3", "岩手県盛岡市仁王第3地割字新山小路65番地", "和歌山市友田町4丁目130番地A-tower２階207-1号室",
])
def test_round_four_english_and_hyphen_lines_read_back(raw) -> None:
    res = jaden.normalize(raw)
    assert res.romaji and jaden.match_key(res.romaji) == jaden.match_key(raw)
    assert jaden.match_key(res.format("hyphen")) == jaden.match_key(raw)


def test_round_four_files_and_json(tmp_path) -> None:
    import io
    import json as json_module
    import zipfile
    from jaden.batch import run_batch
    from jaden.frame import _address_of
    from jaden.xlsx import _NS, read_xlsx
    deep = "[" * 100_000
    assert _address_of(deep, "address")["address"] == deep                               # R4-M9
    src = tmp_path / "deep.jsonl"
    src.write_text('{"address": ' + deep + "}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not valid JSON"):
        run_batch(src, tmp_path / "o.csv", log=io.StringIO())
    path = tmp_path / "amp.xlsx"                                                              # R4-H4
    ns = _NS["m"]
    cells = "".join(f'<row r="{i}"><c r="A{i}" t="s"><v>0</v></c></row>' for i in range(1, 400))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml", f'<workbook xmlns="{ns}" xmlns:r="{_NS["r"]}"><sheets><sheet name="S" '
                   'sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", f'<Relationships xmlns="{_NS["rel"]}"><Relationship Id="rId1" '
                   'Type="x" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/sharedStrings.xml", f'<sst xmlns="{ns}"><si><t>{"あ" * 300_000}</t></si></sst>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="{ns}"><sheetData>{cells}</sheetData></worksheet>')
    with pytest.raises(ValueError, match="characters of text"):
        read_xlsx(path)
    assert json_module.dumps(jaden.normalize("〒100-8111 東京都千代田区千代田1-1").notes).count("large-office") == 1   # R4-L6


# ---------------------------------------------------------------- audit round 5
@pytest.mark.parametrize("english, japanese", [
    ("4-2-8-101 Shibakoen, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号 101号室"),                   # R5-H1
    ("1-10-1-915, Higashishinbashi, Minato ku, Tokyo", "東京都港区東新橋1丁目10番1号 915号室"),
    ("791, Yoshida, Yoshida-cho, Akitakata-shi, Hiroshima", "広島県安芸高田市吉田町吉田791番"),             # R5-H2
    ("4-22-26 Kasumigaseki Kita Kawagoe-shi Saitama", "埼玉県川越市霞ケ関北4丁目22番26号"),
    ("2-22, Minami 14-jo Nishi 1-chome, Chuo-ku, Sapporo", "北海道札幌市中央区南14条西1丁目2番22号"),      # R5-H3
    ("2-18, 4-chome, Shibakoen, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番18号"),
    ("5F, 4-2-8 Shibakoen, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号 5F"),                         # R5-M4
    ("Shibakoen 4-chome 2-8, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号"),                          # R5-M5
    ("oomachi 1-chome 2-ban 15-go, Takikawa shi, Hokkaido", "北海道滝川市大町1丁目2番15号"),
    ("4-2-8, Tokyo Tower 2F, Shibakoen, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号 Tokyo Tower 2F"),
    ("4-11-3 Asahicho Kashiwa-shi Chiba", "千葉県柏市旭町4丁目11番3号"),                                # R5-M6
    ("2587 Ishikawa Uruma-shi Okinawa", "沖縄県うるま市石川2587番"),
    ("1-6-1 Izumi Kita Akita-shi Akita", "秋田県秋田市泉北1丁目6番1号"),
    ("4-6-16 Ginza, Chūō-ku, Tōkyō", "東京都中央区銀座4丁目6番16号"),
    ("45-18, Ohyamacho, Shibuya ku, Tokyo", "東京都渋谷区大山町45番18号"),
])
def test_round_five_english(english, japanese) -> None:
    assert jaden.normalize(english).canonical == japanese


def test_round_five_units_lots_and_names() -> None:
    same = lambda a, b: jaden.compare(a, b).verdict   # noqa: E731
    base = "東京都港区芝公園4-2-8 "
    for a, b in (("3B", "4B"), ("10-1", "10-2"), ("B-3", "B-4"), ("3F B室", "3F A室")):            # R5-M1
        assert same(base + a, base + b) == "same_building"
    assert same("鹿児島県指宿市東方828番地ロ", "鹿児島県指宿市東方828番地イ") == "different"           # R5-M2
    two = jaden.normalize(base + "101号室、102号室")                                                 # R5-M3
    assert two.components.unit is None and jaden.normalize(two.canonical).canonical == two.canonical
    twice = jaden.normalize("愛知県一宮市花池2丁目16-12　メゾン花池101号メゾン花池101号室")
    assert jaden.match_key(twice).endswith("|101")
    for name in ("仙台市長", "金沢市長", "白浜町中央保健センター", "東京都港区第5"):                     # R5-M7
        assert jaden.validate(name).status != "ACCEPTED"
    assert jaden.validate("石川県白山市松任駅北相木第2土地区画整理事業施行地区内19街区1").status == "ACCEPTED"
    kana = jaden.normalize("とうきょうとみなとくしばこうえん4-2-8 101ごうしつ")                       # R5-L4
    assert kana.components.building is None and jaden.match_key(kana).endswith("|101")
    for raw in ("東京都港区芝公園4-2-8-105-0011", "京都府京都市上京区東堀川通出水上る3-13-1"):          # R5-L5
        res = jaden.normalize(raw)
        assert jaden.normalize(res.canonical).canonical == res.canonical
        assert jaden.match_key(res.canonical) == jaden.match_key(raw)


@pytest.mark.parametrize("raw", [                                                            # R5-L1, L2, L3
    "宮崎県延岡市野地町6-5415-乙", "長野県上高井郡小布施町大字小布施860-イ", "山梨県南巨摩郡身延町身延身延3552",
    "京都府京都市右京区西院西田町1洛西マンションNO,2　102号室", "鹿児島県日置市日吉町日置３１０５",
    "東京都新宿区百人町１丁目１１－２８ＰＬＡＴ１００－３０３号", "大阪市住吉区苅田8-11-30-12　メゾン阪南",
])
def test_round_five_english_lines_read_back(raw) -> None:
    res = jaden.normalize(raw)
    assert jaden.match_key(res.romaji) == jaden.match_key(raw)
    assert jaden.match_key(res.romaji.replace(",", "")) == jaden.match_key(raw)


def test_round_five_io(tmp_path) -> None:
    import io
    from jaden.batch import run_batch
    from jaden.core.text import load_json
    from jaden.fields import check_fields
    with pytest.raises(ValueError):                                                           # R5-L6
        load_json('{"x": 1e400}')
    with pytest.raises(ValueError):
        load_json('{"x": NaN}')
    src = tmp_path / "in.txt"                                                                 # R5-L7
    src.write_text("東京都港区芝公園4-2-8\n\n大阪府大阪市北区梅田1-1\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    run_batch(src, out, log=io.StringIO())
    assert len(out.read_text(encoding="utf-8-sig").splitlines()) == 4
    result = check_fields(prefecture="Tokyo", city="Minato-ku", line1="4-2-8 Shibakoen")      # R5-L9
    assert result.status == "ACCEPTED" and result.fields["line1"] == "芝公園4丁目2番8号"


# ---------------------------------------------------------------- audit round 6
@pytest.mark.parametrize("english, japanese", [
    ("Chiba, Yachiyo-shi, 55-1 Shimada", "千葉県八千代市島田55番1号"),                                     # R6-H1
    ("Tokyo, Setagaya-ku, 9-1-35 Kitami", "東京都世田谷区喜多見9丁目1番35号"),
    ("Shiba Park Bldg,4-2-8 Shibakoen,Minato-ku,Tokyo", "東京都港区芝公園4丁目2番8号 Shiba Park Bldg"),     # R6-H2
    ("3-1-1 Izumi Kita Akita shi Akita", "秋田県秋田市泉北3丁目1番1号"),                                    # R6-H5
    ("Shibakoen 4chome 2ban 8go, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号"),                         # R6-M2
    ("Shibakoen 4 chome 2 ban 8 go, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号"),
    ("5200 banchi, Moseushi, Moseushi-cho, Uryu-gun, Hokkaido", "北海道雨竜郡妹背牛町5200番地"),
    ("1642-26, Oaza-Kumagawa, Fussa-shi, Tokyo", "東京都福生市大字熊川1642番地の26"),                         # R6-M3
    ("Aikoku 191-5711, Kushiro-shi, Hokkaido", "北海道釧路市愛国191番5711号"),                              # R6-M4
    ("Kita 8 Nishi 5, Kita-ku, Sapporo", "北海道札幌市北区北8条西5丁目"),                                     # R6-M5
    ("札幌市中央区南3西4 1-1", "北海道札幌市中央区南3条西4丁目1番1号"),
    ("Hyogo, Itami-shi, 1-2-17 Minamihommachi, ベラカーザ 1F", "兵庫県伊丹市南本町1丁目2番17号 ベラカーザ 1F"),   # R6-M6
    ("807-1 Ako Miyake-mura Miyakejima Tokyo", "東京都三宅村阿古807番1号"),                                  # R6-M7
    ("6956-2 Uwae Takanabe cho Koyu gun Miyazaki", "宮崎県児湯郡高鍋町大字上江6956番地の2"),                  # R6-M10
    ("3-1-1 Sinzyuku, Sinzyuku-ku, Tokyo", "東京都新宿区新宿3丁目1番1号"),                                   # R6-L1
    ("3-3-5 三山木中央, Kyotanabe City, Kyoto", "京都府京田辺市三山木中央3丁目3番5号"),                         # R6-L2
    ("1-2-9, Imojima, Gifu", "岐阜県岐阜市芋島1丁目2番9号"),                                                 # R6-L3
])
def test_round_six_english(english, japanese) -> None:
    assert jaden.normalize(english).canonical == japanese


def test_round_six_japanese() -> None:
    for raw, canonical in (("東京都港区芝公園4丁目2番18号 Fビル", "東京都港区芝公園4丁目2番18号 Fビル"),          # R6-H3
                           ("大分県豊後大野市緒方町576番地 201・202号室", "大分県豊後大野市緒方町576番地 201-202号室")):  # R6-M11
        res = jaden.normalize(raw)
        assert res.canonical == canonical and jaden.normalize(res.canonical).canonical == canonical
    for name in ("千葉大学", "岡山大学", "熊本城", "大阪港", "世田谷区役所 第2庁舎"):                           # R6-H4, M12
        assert jaden.validate(name).status != "ACCEPTED"
    for real in ("千葉県大学町", "東京 芝公園", "石川県白山市松任駅北相木第2土地区画整理事業施行地区内19街区1"):
        assert jaden.validate(real).status == "ACCEPTED"
    same = lambda a, b: jaden.compare(a, b).verdict   # noqa: E731
    assert same("東京都港区芝公園4-2-8 メゾン芝 4A", "東京都港区芝公園4-2-8 メゾン芝 4B") == "same_building"   # R6-M1
    assert same("京都府京都市中京区笹屋町436", "京都府京都市中京区御池通東洞院東入笹屋町436") == "possibly_same"   # R6-M9
    res = jaden.normalize("富山県富山市山岸95 503 号")                                                     # R6-L4
    assert jaden.normalize(res.canonical).canonical == res.canonical


def test_round_six_mixed_fields() -> None:                                                     # R6-M8
    for kw in (dict(prefecture="東京都", city="Minato-ku", line1="4-2-8 Shibakoen"),
               dict(prefecture="東京都", city="港区", line1="4-2-8 Shibakoen"),
               dict(prefecture="Tokyo", city="港区", line1="芝公園4-2-8")):
        result = jaden.check_fields(**kw)
        assert result.status == "ACCEPTED" and result.canonical == "東京都港区芝公園4丁目2番8号"


# ---------------------------------------------------------------- audit round 7
@pytest.mark.parametrize("raw, canonical", [
    ("東京都港区芝公園4丁目2番8号 F201", "東京都港区芝公園4丁目2番8号 F201"),                              # R7-H1
    ("大分県豊後大野市緒方町576番地 F201", "大分県豊後大野市緒方町576番地 F201"),
    ("茨城県笠間市東平2-12-2　F/Kビル2階", "茨城県笠間市東平2丁目12番2号 F/Kビル 2階"),
    ("東京都港区芝公園4丁目2番 8 号", "東京都港区芝公園4丁目2番8号"),                                        # R7-M1
    ("東京都港区芝公園 4 丁目 2 番 8 号", "東京都港区芝公園4丁目2番8号"),                                     # R7-M6
    ("北海道札幌市中央区南七条西７丁目４ラフィリア札幌７０６号", "北海道札幌市中央区南7条西7丁目4番 ラフィリア札幌 706号"),   # R7-M5
])
def test_round_seven_japanese(raw, canonical) -> None:
    res = jaden.normalize(raw)
    assert res.canonical == canonical and jaden.normalize(canonical).canonical == canonical
    assert jaden.match_key(canonical) == jaden.match_key(raw)


@pytest.mark.parametrize("english, japanese", [
    ("1-2-3 本荘, Chuo-ku, Kumamoto-shi, Kumamoto", "熊本県熊本市中央区本荘1丁目2番3号"),                    # R7-H2
    ("1-2 二階堂, Kamakura-shi, Kanagawa", "神奈川県鎌倉市二階堂1番2号"),
    ("Hokkaido Kitami-shi 1-4-2 Minamimachi 浦川整骨院", "北海道北見市南町1丁目4番2号 浦川整骨院"),          # R7-M3
    ("4-2-8 Shibakoen, Minato-ku, Tokyo, メゾン芝 #A-2", "東京都港区芝公園4丁目2番8号 メゾン芝 A-2号室"),      # R7-L1
    ("SHIMOKOBATACHO DAI 6GO 1-1, SABAE SHI, Fukui", "福井県鯖江市下河端町第6号1番地の1"),                  # R7-L2
    ("3-22-5 Miyamae, Sakura-shi, Chiba, ソレイユの丘佐倉", "千葉県佐倉市宮前3丁目22番5号 ソレイユの丘佐倉"),  # R7-L3
    ("5-1 Nihonbashi Kabuto-cho, Tokyo", "東京都中央区日本橋兜町5番1号"),                                    # R7-L6
    ("13-1-14 Nagayama 4-Zyo, Asahikawa-si, Hokkaido", "北海道旭川市永山四条13丁目1番14号"),
])
def test_round_seven_english(english, japanese) -> None:
    assert jaden.normalize(english).canonical == japanese


@pytest.mark.parametrize("raw", ["大阪府堺市東区日置荘北町三丁5-3", "秋田県山本郡八峰町八森字岩館８番地",       # R7-H2, M4
                                 "北海道標津郡標津町北六条西１丁目１番２３号"])
def test_round_seven_english_lines_read_back(raw) -> None:
    res = jaden.normalize(raw)
    assert jaden.match_key(res.romaji) == jaden.match_key(raw)


def test_round_seven_fields_postal_and_rooms() -> None:
    for kw in (dict(city="中央区", line1="4-6-1 Hatchobori"), dict(city="Chuo-ku", line1="八丁堀4-6-1")):   # R7-M2
        assert jaden.check_fields(**kw).canonical == "東京都中央区八丁堀4丁目6番1号"
    assert any("芝公園" in w for w in jaden.validate("〒105-0011 東京都港区芝4-2-8").warnings)                 # R7-M7
    two = jaden.normalize("愛知県豊橋市中岩田5丁目8番地1 トランキーロT 101 102")                              # R7-L9
    assert two.components.unit is None and jaden.normalize(two.canonical).canonical == two.canonical


def test_round_seven_english_town_in_another_ward_is_suggested() -> None:                     # R7-L5
    notes = jaden.normalize("4-2-8 Shibakoen, Shinjuku-ku, Tokyo").notes
    assert any("東京都港区芝公園" in n for n in notes)


# ---------------------------------------------------------------- audit round 8
@pytest.mark.parametrize("english, japanese", [
    ("4-2-8 Shibakoen 3号棟 201, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号 3号棟 201"),                # R8-H1
    ("4-2-8 Shibakoen 3階, Minato-ku, Tokyo", "東京都港区芝公園4丁目2番8号 3階"),
    ("1365 Takaya, Sodegaura-shi, Chiba 299-0203, 百笑", "千葉県袖ケ浦市高谷1365番 百笑"),                    # R8-M5
    ("2031-1081 Tsuda, Ibaraki 312-0032", "茨城県ひたちなか市大字津田2031番地の1081"),                         # R8-M6
    ("2000 Kitazaike Kakogawa cho, Kakogawa shi, Hyogo", "兵庫県加古川市加古川町北在家2000番"),                # R8-M7
    ("サンハイツ #402 1-chome-1-18 Showa-ku Nagoya-shi Aichi", "愛知県名古屋市昭和区1丁目1番18号 サンハイツ 402号室"),  # R8-L1
    ("DAI 6GO 1-1, SHIMOKOBATACHO, SABAE SHI, Fukui", "福井県鯖江市下河端町第6号1番地の1"),                     # R8-L4
    ("1-1 Minami 3-jo Nishi 4-chome, Chuo-ku", "北海道札幌市中央区南3条西4丁目1番1号"),                         # R8-L10
    ("12th Fl.3-2-5 kasumigaseki, Chiyoda ku, Tokyo", "東京都千代田区霞が関3丁目2番5号 12F"),                  # R8-L12
])
def test_round_eight_english(english, japanese) -> None:
    assert jaden.normalize(english).canonical == japanese


@pytest.mark.parametrize("raw, canonical", [
    ("北海道札幌市中央区南1条西4丁目5-1-201A", "北海道札幌市中央区南1条西4丁目5番1号 201A"),                     # R8-M1
    ("東京都港区芝公園4丁目2番8号 F 201", "東京都港区芝公園4丁目2番8号 F 201"),                                # R8-M4
    ("大阪府大阪市西区九条1丁目21-242F/6F", "大阪府大阪市西区九条1丁目21番24号 2F/6F"),                         # R8-L3
    ("富山県富山市山岸95番 503 号", "富山県富山市山岸95番503号"),                                              # R8-L2, R9-M3
    ("東京都港区芝公園4-2-8 サンハイツ 301 号室", "東京都港区芝公園4丁目2番8号 サンハイツ 301号室"),            # R8-L7
    ("北海道札幌市中央区南 1 条西 4 丁目 5 番 1 号", "北海道札幌市中央区南1条西4丁目5番1号"),                   # R8-L5, L6
    ("Room 301, 東京都港区芝公園4-2-8", "東京都港区芝公園4丁目2番8号 301"),                                     # R8-L8
])
def test_round_eight_japanese(raw, canonical) -> None:
    res = jaden.normalize(raw)
    assert res.canonical == canonical and jaden.normalize(canonical).canonical == canonical


def test_round_eight_validation() -> None:
    for name in ("東京都港区芝公園付近", "東京都新宿区新宿御苑", "東京都港区芝公園未定"):                    # R8-H2
        assert jaden.validate(name).status != "ACCEPTED"
    assert jaden.normalize("2-8 Kayabacho Nihonbashi, Tokyo").components.town != "日本橋"                 # R8-M2
    for own in ("〒501-2526 岐阜県岐阜市門屋字野崎95", "〒765-0011 香川県善通寺市上吉田町3丁目5番6号"):    # R8-M3
        assert not [w for w in jaden.validate(own).warnings if w.startswith("postal code")]
    assert [w for w in jaden.validate("〒105-0011 東京都港区芝4-2-8").warnings if "芝公園" in w]
    assert jaden.match_key(jaden.normalize("山形県東根市大字羽入字東原571番地の3").romaji) == \
        jaden.match_key("山形県東根市大字羽入字東原571番地の3")                                                 # R8-M8
    result = jaden.check_fields(city="Shinjuku-ku", line1="4-2-8 Shibakoen")                             # R8-M9
    assert any(i.code == "CITY_MISMATCH" for i in result.issues)
    assert jaden.normalize("東京都港区芝公園第2ビル").components.chome is None                              # R8-L9


# ---------------------------------------------------------------- audit round 9
def test_round_nine_leading_text_and_postal() -> None:
    for text in ("大阪市北区梅田1-1-3、東京都港区芝公園4-2-8", "TEL 03-3433-5111, 東京都港区芝公園4-2-8",       # R9-H1
                 "株式会社ABC、東京都港区芝公園4-2-8", "2024年1月1日、東京都港区芝公園4-2-8"):
        assert "芝公園4丁目2番8号 " not in jaden.normalize(text).canonical
    assert jaden.normalize("Room 301, 東京都港区芝公園4-2-8").canonical == "東京都港区芝公園4丁目2番8号 301"
    for code, address in (("105-0014", "東京都港区芝公園4-2-8"), ("105-0011", "東京都港区芝4-2-8公園前ハイツ")):   # R9-M1
        assert [w for w in jaden.validate(f"〒{code} {address}").warnings if w.startswith("postal code")]
    for own in ("〒501-2526 岐阜県岐阜市門屋字野崎95", "〒380-0813 長野県長野市大字鶴賀緑町1107番地9"):
        assert not [w for w in jaden.validate(own).warnings if w.startswith("postal code")]


@pytest.mark.parametrize("raw, canonical", [
    ("東京都港区芝5-1-1 森第2ビル", "東京都港区芝5丁目1番1号 森第2ビル"),                                    # R9-M2
    ("奈良県橿原市中町200番 128号", "奈良県橿原市中町200番128号"),                                             # R9-M3
    ("東京都港区芝公園4-2-8 号室", "東京都港区芝公園4丁目2番8号"),                                              # R9-L1
    ("香川県高松市香川町安原下第三号56", "香川県高松市香川町安原下第三号56番地"),                               # R9-M6
    ("東京都港区芝公園4丁目2番8号 F 2F", "東京都港区芝公園4丁目2番8号 F 2F"),                                   # R9-L2
    ("大阪府大阪市西区九条1丁目21-242F・6F", "大阪府大阪市西区九条1丁目21番24号 2F・6F"),                       # R9-L3
])
def test_round_nine_japanese(raw, canonical) -> None:
    res = jaden.normalize(raw)
    assert res.canonical == canonical and jaden.normalize(canonical).canonical == canonical


def test_round_nine_english_and_notes() -> None:
    res = jaden.normalize("4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011, Sun Heights 201")                  # R9-M5
    assert res.components.postal_code == "105-0011" and res.canonical.startswith("東京都港区芝公園4丁目2番8号")
    assert jaden.normalize("88-1 江刺区愛宕字前中野, Oshu-shi 023-0000").components.town                       # R9-L5
    raw = "茨城県土浦市菅谷町タカノス1168-1"                                                                    # R9-L6
    assert jaden.match_key(jaden.normalize(raw).romaji) == jaden.match_key(raw)
    assert jaden.validate("東京都港区芝公園4-2-8付近").warnings                                                 # R9-L9
    assert jaden.normalize("東京都港区芝公園第2ビル101").components.chome is None                               # R9-M4


# ---------------------------------------------------------------- audit round 10
def test_round_ten_regressions() -> None:
    assert jaden.normalize("東京都港区芝公園4丁目2番8号F").canonical == "東京都港区芝公園4丁目2番8号 F"         # R10-H1
    for text in ("本町ビル、大阪府大阪市中央区本町1-1-1", "グランドタワー、東京都港区芝公園4-2-8",              # R10-M1
                 "サンハイツ1-201、東京都港区芝公園4-2-8", "大手町タワー 12階、東京都千代田区大手町1-5-1"):
        assert jaden.validate(text).status == "ACCEPTED"
    assert jaden.validate("TEL 03-3433-5111, 東京都港区芝公園4-2-8").status != "ACCEPTED"
    assert "名古屋市中区丸の内" in jaden.normalize("3-1 Marunouchi, Naka-ku 730-0035").canonical               # R10-M2
    assert jaden.compare("北海道網走市字栄12-3", "北海道網走市栄12-3").verdict == "same"                       # R10-M3
