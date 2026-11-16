"""The HTTP API server: every endpoint over a real socket."""

import json
import threading
import urllib.error
import urllib.parse
import urllib.request

import pytest

from jaden.server import JadenApi, address_record, create_server


@pytest.fixture(scope="module")
def base_url():
    server = create_server(port=0, quiet=True, max_batch=3, cors="*")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()


def call(base_url, path, params=None, body=None):
    url = base_url + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8")), err.headers


def test_normalize_returns_one_complete_record(base_url):
    status, data, headers = call(base_url, "/v1/normalize", {"q": "港区芝公園４丁目２番８号 １０１号室"})
    assert status == 200
    assert headers["Content-Type"].startswith("application/json")
    assert headers["Access-Control-Allow-Origin"] == "*"
    assert data["status"] == "ACCEPTED" and data["valid"] is True
    assert data["canonical"] == "東京都港区芝公園4丁目2番8号 101号室"
    assert data["hyphenated"] == "東京都港区芝公園4-2-8 101号室"
    assert data["english"] == "#101, 4-2-8 Shibakoen, Minato-ku, Tokyo 105-0011"
    assert data["lines"] == ["〒105-0011", "東京都港区芝公園4丁目2番8号", "101号室"]
    assert data["postal_code"] == "105-0011" and data["lg_code"] == "131032"
    assert data["precision"] == "unit" and data["verification_level"] == "chome"
    assert data["location"]["level"] == "chome"
    assert data["components"]["town"] == "芝公園" and data["components"]["unit"] == "101号室"


def test_normalize_options_and_post(base_url):
    _, plain, _ = call(base_url, "/v1/normalize", {"q": "東京都港区芝公演4-2-8"})
    assert plain["suggestions"] == ["東京都港区芝公園4丁目2番8号"]
    _, fixed, _ = call(base_url, "/v1/normalize", body={"q": "東京都港区芝公演4-2-8", "fix": True})
    assert fixed["canonical"] == "東京都港区芝公園4丁目2番8号"
    assert fixed["components"]["town_corrected_from"] == "芝公演"
    _, strict, _ = call(base_url, "/v1/validate", {"q": "東京都港区存在しない町1-1", "strict": "1"})
    assert strict["status"] == "UNSUPPORTED"


def test_ambiguous_and_rejected_inputs_are_200_with_a_status(base_url):
    status, data, _ = call(base_url, "/v1/normalize", {"q": "府中市1-1"})
    assert status == 200 and data["status"] == "AMBIGUOUS" and len(data["candidates"]) == 2
    status, data, _ = call(base_url, "/v1/normalize", {"q": "hello world"})
    assert status == 200 and data["status"] == "MALFORMED" and data["canonical"] is None


def test_lookup_endpoints(base_url):
    status, data, _ = call(base_url, "/v1/postal/105-0011")
    assert status == 200 and data["addresses"][0]["address"] == "東京都港区芝公園"
    status, data, _ = call(base_url, "/v1/postal/999-9999")
    assert status == 404 and data["error"]["code"] == "not_found"
    _, data, _ = call(base_url, "/v1/suggest", {"q": "東京都港区しば", "limit": 3})
    assert len(data["suggestions"]) == 3 and data["suggestions"][0]["text"].startswith("東京都港区芝")
    _, data, _ = call(base_url, "/v1/reverse", {"lat": "35.0116", "lon": "135.7681"})
    assert data["results"][0]["address"] == "京都府京都市中京区上本能寺前町"
    _, data, _ = call(base_url, "/v1/geocode", {"q": "東京都港区芝公園4-2-8"})
    assert data["status"] == "SUCCESS" and data["provider"] == "offline"


def test_compare_extract_batch(base_url):
    _, data, _ = call(base_url, "/v1/compare", {"a": "東京都港区芝公園4-2-8", "b": "港区芝公園４－２－８"})
    assert data["verdict"] == "same" and data["key_a"] == data["key_b"] == "131032|芝公園|4|2|8|"
    _, data, _ = call(base_url, "/v1/extract", body={"text": "会場は東京都港区芝公園4-2-8です。"})
    assert [(a["start"], a["end"], a["canonical"]) for a in data["addresses"]] == [(3, 16, "東京都港区芝公園4丁目2番8号")]
    status, data, _ = call(base_url, "/v1/batch", body={"addresses": ["東京都港区芝公園4-2-8", "府中市1-1", "東京タワー"]})
    assert status == 200 and data["count"] == 3
    assert data["summary"] == {"ACCEPTED": 1, "AMBIGUOUS": 1, "UNSUPPORTED": 1}


def test_errors(base_url):
    assert call(base_url, "/v1/normalize")[0] == 400
    assert call(base_url, "/v1/reverse", {"lat": "abc", "lon": "1"})[0] == 400
    assert call(base_url, "/v1/reverse", {"lat": "95", "lon": "139"})[0] == 400
    assert call(base_url, "/v1/suggest", {"q": "東京", "limit": "999"})[0] == 400
    assert call(base_url, "/v1/nothing")[0] == 404
    status, data, _ = call(base_url, "/v1/batch", body={"addresses": ["a", "b", "c", "d"]})
    assert status == 413 and data["error"]["code"] == "too_many"
    assert call(base_url, "/v1/batch", body={"addresses": "東京都"})[0] == 400
    req = urllib.request.Request(base_url + "/v1/extract", data=b"{not json", headers={"Content-Type": "application/json"})
    with pytest.raises(urllib.error.HTTPError) as err:
        urllib.request.urlopen(req, timeout=10)
    assert err.value.code == 400


def test_index_health_and_demo_page(base_url):
    _, info, _ = call(base_url, "/v1")
    assert info["name"] == "JADEN" and "/v1/normalize" in info["endpoints"]
    assert info["data"]["town_records"] > 180_000
    assert call(base_url, "/health")[1]["status"] == "ok"
    with urllib.request.urlopen(base_url + "/", timeout=10) as resp:
        page = resp.read().decode("utf-8")
        assert resp.headers["Content-Type"].startswith("text/html")
    assert "<title>JADEN" in page and "/v1/normalize" in page


def test_concurrent_requests(base_url):
    results = []

    def worker():
        results.append(call(base_url, "/v1/normalize", {"q": "大阪市北区梅田3-1-1"})[1]["lg_code"])

    threads = [threading.Thread(target=worker) for _ in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == ["271276"] * 16


def test_api_object_without_http():
    api = JadenApi()
    assert api.handle("/v1/postal/1050011", {})["postal_code"] == "105-0011"
    assert address_record("東京タワー")["status"] == "UNSUPPORTED"
