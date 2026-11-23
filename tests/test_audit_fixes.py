"""Bugs found by the full audit of 22 November 2026 (docs/CHECKLIST.md), each pinned by its reproducing input."""

import json
import time

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
    res = jaden.normalize("158-2 Arata Kamikomata, Hirakawa-shi, Aomori")
    assert res.canonical == "青森県平川市Arata Kamikomata158番2号"
    assert jaden.validate("158-2 Arata Kamikomata, Hirakawa-shi, Aomori").verification_level == "municipality"


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
    assert (cmp.verdict, cmp.conflict) == ("different", "building") and cmp.building_similarity == 0.0
    assert jaden.match_key("東京都港区芝公園4-2-8 第一ビル") != jaden.match_key("東京都港区芝公園4-2-8 第二ビル")
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
    assert pairs[0].score == 0.95 and any("typo" in r for r in pairs[0].reasons)
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
    assert stream(src, out) == 4
    lines = [json.loads(x) for x in out.getvalue().splitlines()]
    assert lines[0]["jaden"]["status"] == "ACCEPTED"
    assert lines[1]["input"]["id"] == 7 and lines[1]["jaden"]["status"] == "AMBIGUOUS"
    assert "error" in lines[2] and lines[3]["jaden"]["status"] == "MALFORMED"


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
    assert jaden.find_duplicates(rows) == [1, 2, 3, 4, 1, 5]
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
