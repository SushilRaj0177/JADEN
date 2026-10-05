"""Unit and integration tests for JADEN optional geospatial resolution."""

import json
import os
import urllib.error
from io import BytesIO, StringIO
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest

import jaden
from jaden import (
    BaseGeospatialResolver,
    Coordinates,
    GeocodingStatus,
    GeospatialResult,
    GSIGeocoder,
    geocode,
    normalize,
    parse,
    validate,
)
from jaden.cli import main


# ==============================================================================
# Mock Fixtures & Helpers
# ==============================================================================

class MockHttpResponse:
    """Mock context-manager response for urllib.request."""

    def __init__(self, data: bytes, code: int = 200) -> None:
        self._data = data
        self._code = code

    def getcode(self) -> int:
        return self._code

    def read(self) -> bytes:
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


GSI_SUCCESS_PAYLOAD = json.dumps([
    {
        "geometry": {
            "coordinates": [139.729202, 35.660206],
            "type": "Point",
        },
        "type": "Feature",
        "properties": {
            "addressCode": "13103",
            "title": "東京都港区六本木六丁目１０番",
        },
    }
]).encode("utf-8")

GSI_AMBIGUOUS_PAYLOAD = json.dumps([
    {
        "geometry": {
            "coordinates": [139.477585, 35.669403],
            "type": "Point",
        },
        "type": "Feature",
        "properties": {
            "addressCode": "13206",
            "title": "東京都府中市",
        },
    },
    {
        "geometry": {
            "coordinates": [133.236389, 34.568333],
            "type": "Point",
        },
        "type": "Feature",
        "properties": {
            "addressCode": "34208",
            "title": "広島県府中市",
        },
    },
]).encode("utf-8")


def run_cli(args: List[str], monkeypatch=None, stdin_data: Optional[str] = None) -> tuple[int, str, str]:
    """Helper to run CLI and capture output."""
    stdout_buf = StringIO()
    stderr_buf = StringIO()

    if monkeypatch:
        monkeypatch.setattr("sys.stdout", stdout_buf)
        monkeypatch.setattr("sys.stderr", stderr_buf)
        if stdin_data is not None:
            monkeypatch.setattr("sys.stdin", StringIO(stdin_data))

    exit_code = main(args)
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


# ==============================================================================
# 1. GSIGeocoder Unit Tests
# ==============================================================================

def test_gsi_geocoder_success():
    mock_opener = MagicMock()
    mock_opener.open.return_value = MockHttpResponse(GSI_SUCCESS_PAYLOAD)

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("東京都港区六本木6-10-1")

    assert res.status == GeocodingStatus.SUCCESS.value
    assert res.provider == "gsi"
    assert res.coordinates is not None
    assert pytest.approx(res.coordinates.latitude, 0.0001) == 35.660206
    assert pytest.approx(res.coordinates.longitude, 0.0001) == 139.729202
    assert "東京都港区六本木六丁目１０番" in res.matched_address
    assert res.metadata.get("gsi_address_code") == "13103"


def test_gsi_geocoder_no_match():
    mock_opener = MagicMock()
    mock_opener.open.return_value = MockHttpResponse(b"[]")

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("東京都千代田区存在しない架空の町999")

    assert res.status == GeocodingStatus.NO_MATCH.value
    assert res.coordinates is None
    assert "No matching coordinates found" in (res.error_message or "")


def test_gsi_geocoder_ambiguous_matches():
    mock_opener = MagicMock()
    mock_opener.open.return_value = MockHttpResponse(GSI_AMBIGUOUS_PAYLOAD)

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("府中市")

    assert res.status == GeocodingStatus.AMBIGUOUS.value
    assert res.coordinates is None
    assert len(res.candidates) == 2
    assert "東京都府中市" in res.candidates
    assert "広島県府中市" in res.candidates
    assert "Ambiguous address" in (res.error_message or "")


def test_gsi_geocoder_http_error():
    mock_opener = MagicMock()
    mock_opener.open.side_effect = urllib.error.HTTPError(
        url="https://msearch.gsi.go.jp",
        code=503,
        msg="Service Unavailable",
        hdrs={},
        fp=BytesIO(b""),
    )

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("東京都港区六本木6-10-1")

    assert res.status == GeocodingStatus.ERROR.value
    assert res.coordinates is None
    assert "503" in (res.error_message or "")


def test_gsi_geocoder_timeout():
    mock_opener = MagicMock()
    mock_opener.open.side_effect = TimeoutError("Network timed out")

    geocoder = GSIGeocoder(timeout=2.0, opener=mock_opener)
    res = geocoder.resolve("東京都港区六本木6-10-1")

    assert res.status == GeocodingStatus.ERROR.value
    assert res.coordinates is None
    assert "timed out after 2.0s" in (res.error_message or "")


def test_gsi_geocoder_connection_error():
    mock_opener = MagicMock()
    mock_opener.open.side_effect = urllib.error.URLError("Name resolution failure")

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("東京都港区六本木6-10-1")

    assert res.status == GeocodingStatus.ERROR.value
    assert res.coordinates is None
    assert "connection error" in (res.error_message or "").lower()


def test_gsi_geocoder_invalid_json():
    mock_opener = MagicMock()
    mock_opener.open.return_value = MockHttpResponse(b"<html>Bad Gateway</html>")

    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve("東京都港区六本木6-10-1")

    assert res.status == GeocodingStatus.ERROR.value
    assert "Failed to decode GSI JSON" in (res.error_message or "")


def test_gsi_geocoder_empty_input():
    mock_opener = MagicMock()
    geocoder = GSIGeocoder(opener=mock_opener)

    res_empty = geocoder.resolve("")
    assert res_empty.status == GeocodingStatus.NO_MATCH.value
    assert mock_opener.open.call_count == 0

    res_spaces = geocoder.resolve("   ")
    assert res_spaces.status == GeocodingStatus.NO_MATCH.value
    assert mock_opener.open.call_count == 0


def test_gsi_geocoder_rejected_by_jaden_core():
    mock_opener = MagicMock()
    geocoder = GSIGeocoder(opener=mock_opener)

    # Completely nonsensical non-Japanese input rejected with confidence 0.0
    res = geocoder.resolve("12345 Hello World USA")
    assert res.status == GeocodingStatus.NO_MATCH.value
    assert mock_opener.open.call_count == 0
    assert "rejected by JADEN validator" in (res.error_message or "")


def test_gsi_geocoder_accepts_normalized_address():
    mock_opener = MagicMock()
    mock_opener.open.return_value = MockHttpResponse(GSI_SUCCESS_PAYLOAD)

    norm = normalize("東京都港区六本木6-10-1")
    geocoder = GSIGeocoder(opener=mock_opener)
    res = geocoder.resolve(norm)

    assert res.status == GeocodingStatus.SUCCESS.value
    assert res.coordinates is not None
    assert mock_opener.open.call_count == 1


# ==============================================================================
# 2. Public API & Extensibility Tests
# ==============================================================================

class DummyLocalResolver(BaseGeospatialResolver):
    """Custom resolver verifying the pluggable BaseGeospatialResolver abstraction."""

    @property
    def provider_name(self) -> str:
        return "dummy_local"

    def resolve(self, address) -> GeospatialResult:
        return GeospatialResult(
            query=str(address),
            status=GeocodingStatus.SUCCESS.value,
            coordinates=Coordinates(latitude=35.0, longitude=139.0),
            provider=self.provider_name,
            matched_address="Custom Mock Location",
        )


def test_custom_resolver_injection():
    custom_resolver = DummyLocalResolver()
    res = geocode("東京都千代田区丸の内1-1", resolver=custom_resolver)

    assert res.status == GeocodingStatus.SUCCESS.value
    assert res.provider == "dummy_local"
    assert res.coordinates == Coordinates(latitude=35.0, longitude=139.0)
    assert res.matched_address == "Custom Mock Location"


def test_geospatial_result_serialization():
    result = GeospatialResult(
        query="東京都港区六本木6-10-1",
        status=GeocodingStatus.SUCCESS.value,
        coordinates=Coordinates(latitude=35.660206, longitude=139.729202),
        provider="gsi",
        matched_address="東京都港区六本木六丁目１０番",
        candidates=("東京都港区六本木六丁目１０番",),
        metadata={"precision": "block"},
    )

    data = result.to_dict()
    assert data["query"] == "東京都港区六本木6-10-1"
    assert data["status"] == "SUCCESS"
    assert data["coordinates"] == {"latitude": 35.660206, "longitude": 139.729202}
    assert data["provider"] == "gsi"

    json_str = result.to_json(indent=2)
    parsed = json.loads(json_str)
    assert parsed["coordinates"]["latitude"] == 35.660206


# ==============================================================================
# 3. Core Parser Independence (Strict Offline Guarantee)
# ==============================================================================

def test_core_parser_never_invokes_network():
    """Verifies that core parsing and normalization never invoke urllib or network calls."""
    with patch("urllib.request.urlopen", side_effect=RuntimeError("NETWORK_CALLED")):
        with patch("urllib.request.OpenerDirector.open", side_effect=RuntimeError("NETWORK_CALLED")):
            # Core normalize
            norm = normalize("東京都港区六本木6-10-1 六本木ヒルズ森タワー 50F")
            assert norm.components.prefecture == "東京都"
            assert norm.components.city == "港区"

            # Core parse
            parsed = parse("京都府京都市中京区寺町通御池上る上本能寺前町488")
            assert parsed.kyoto_direction is not None

            # Core validate
            val = validate("北海道札幌市中央区北1条西2丁目")
            assert val.valid is True


# ==============================================================================
# 4. CLI geocode Command Tests
# ==============================================================================

def test_cli_geocode_success_text(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", return_value=MockHttpResponse(GSI_SUCCESS_PAYLOAD)):
        code, out, err = run_cli(["geocode", "東京都港区六本木6-10-1"], monkeypatch)
        assert code == 0
        assert "Input:       東京都港区六本木6-10-1" in out
        assert "Status:      SUCCESS" in out
        assert "Provider:    gsi" in out
        assert "Coordinates: 35.660206, 139.729202 (Lat, Lon)" in out
        assert "Matched:     東京都港区六本木六丁目１０番" in out


def test_cli_geocode_success_json(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", return_value=MockHttpResponse(GSI_SUCCESS_PAYLOAD)):
        code, out, err = run_cli(["geocode", "東京都港区六本木6-10-1", "--json"], monkeypatch)
        assert code == 0
        data = json.loads(out)
        assert data["status"] == "SUCCESS"
        assert data["provider"] == "gsi"
        assert data["coordinates"]["latitude"] == 35.660206
        assert data["coordinates"]["longitude"] == 139.729202


def test_cli_geocode_no_match(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", return_value=MockHttpResponse(b"[]")):
        code, out, err = run_cli(["geocode", "東京都千代田区架空の町999"], monkeypatch)
        assert code == 1
        assert "Status:      NO_MATCH" in out
        assert "Coordinates:" not in out


def test_cli_geocode_no_match_json(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", return_value=MockHttpResponse(b"[]")):
        code, out, err = run_cli(["geocode", "東京都千代田区架空の町999", "--json"], monkeypatch)
        assert code == 1
        data = json.loads(out)
        assert data["status"] == "NO_MATCH"
        assert data["coordinates"] is None


def test_cli_geocode_ambiguous(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", return_value=MockHttpResponse(GSI_AMBIGUOUS_PAYLOAD)):
        code, out, err = run_cli(["geocode", "府中市"], monkeypatch)
        assert code == 1
        assert "Status:      AMBIGUOUS" in out
        assert "Candidates:" in out
        assert "東京都府中市" in out
        assert "広島県府中市" in out


def test_cli_geocode_timeout_error(monkeypatch):
    with patch("urllib.request.OpenerDirector.open", side_effect=TimeoutError("Timed out")):
        code, out, err = run_cli(["geocode", "東京都港区六本木6-10-1"], monkeypatch)
        assert code == 1
        assert "Status:      ERROR" in out
        assert "timed out after" in out


# ==============================================================================
# 5. Optional Live Integration Test (Skipped by default in CI)
# ==============================================================================

@pytest.mark.network
@pytest.mark.skipif(
    not os.environ.get("JADEN_ENABLE_NETWORK_TESTS"),
    reason="Live network test skipped by default. Enable via JADEN_ENABLE_NETWORK_TESTS=1.",
)
def test_live_gsi_geocoding_integration():
    """Live integration test against official GSI endpoint."""
    res = geocode("東京都港区六本木6-10-1")
    assert res.status == GeocodingStatus.SUCCESS.value
    assert res.coordinates is not None
    assert 35.0 < res.coordinates.latitude < 36.0
    assert 139.0 < res.coordinates.longitude < 140.0
