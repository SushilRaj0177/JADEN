"""Unit and integration tests for JADEN CLI v1."""

import json
import pytest
from io import StringIO
from typing import List

from jaden.cli import main
from jaden import parse, validate, ValidationStatus, ValidationResult


def run_cli(args: List[str], monkeypatch=None, stdin_data: str = None) -> tuple[int, str, str]:
    """Helper to run CLI and capture exit code, stdout, and stderr."""
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
# 1. normalize command tests
# ==============================================================================

def test_cli_normalize_text(monkeypatch):
    code, out, err = run_cli(["normalize", "東京都港区六本木1-2-3"], monkeypatch)
    assert code == 0
    assert "Prefecture: 東京都" in out
    assert "City:       港区" in out
    assert "Town:       六本木" in out
    assert "Chome:      1" in out
    assert "Ban:        2" in out
    assert "Go:         3" in out
    assert "Canonical:  東京都港区六本木1丁目2番3号" in out
    assert "Confidence: 1.00" in out


def test_cli_normalize_canonical_only(monkeypatch):
    code, out, err = run_cli(["normalize", "東京都港区六本木1-2-3", "-c"], monkeypatch)
    assert code == 0
    assert out.strip() == "東京都港区六本木1丁目2番3号"


def test_cli_normalize_json(monkeypatch):
    code, out, err = run_cli(["normalize", "東京都港区六本木1-2-3", "--json"], monkeypatch)
    assert code == 0
    data = json.loads(out)
    assert data["canonical"] == "東京都港区六本木1丁目2番3号"
    assert data["confidence_score"] == 1.0
    assert data["components"]["prefecture"] == "東京都"
    assert data["components"]["city"] == "港区"
    assert data["components"]["ban"] == 2
    assert data["components"]["go"] == 3


def test_cli_normalize_stdin(monkeypatch):
    code, out, err = run_cli(["normalize", "-", "-c"], monkeypatch, stdin_data="東京都港区六本木1-2-3")
    assert code == 0
    assert out.strip() == "東京都港区六本木1丁目2番3号"


def test_cli_normalize_malformed(monkeypatch):
    code, out, err = run_cli(["normalize", "123 Main St, New York"], monkeypatch)
    assert code == 1
    assert "Status:     Rejected" in out


def test_cli_normalize_default_shorthand(monkeypatch):
    # Calling jaden "<address>" without subcommand should invoke normalize
    code, out, err = run_cli(["東京都港区六本木1-2-3", "-c"], monkeypatch)
    assert code == 0
    assert out.strip() == "東京都港区六本木1丁目2番3号"


# ==============================================================================
# 2. parse command tests
# ==============================================================================

def test_cli_parse_text_urban(monkeypatch):
    code, out, err = run_cli(["parse", "東京都港区六本木6-10-1六本木ヒルズ森タワー50F"], monkeypatch)
    assert code == 0
    assert "[Administrative]" in out
    assert "Prefecture:    東京都 (Code: 13)" in out
    assert "City:          港区" in out
    assert "LG Code:       131032" in out
    assert "[Block & Lot]" in out
    assert "Chome:         6" in out
    assert "Ban:           10" in out
    assert "Go:            1" in out
    assert "[Building & Unit]" in out
    assert "Building:      六本木ヒルズ森タワー" in out
    assert "Floor:         50F" in out


def test_cli_parse_text_kyoto(monkeypatch):
    code, out, err = run_cli(["parse", "京都府中京区御池通東洞院東入笹屋町436"], monkeypatch)
    assert code == 0
    assert "[Regional Convention]" in out
    assert "Thoroughfare:  御池通" in out
    assert "Cross Street:  東洞院" in out
    assert "Direction:     東入 (east)" in out
    assert "Banchi:        436" in out


def test_cli_parse_text_hokkaido(monkeypatch):
    code, out, err = run_cli(["parse", "北海道札幌市中央区北1条西2丁目"], monkeypatch)
    assert code == 0
    assert "[Regional Convention]" in out
    assert "Hokkaido Grid: 北1条西2丁目" in out
    assert "Coordinates:   Jo=1 (北), Chome=2 (西)" in out


def test_cli_parse_text_county(monkeypatch):
    code, out, err = run_cli(["parse", "神奈川県中郡大磯町国府本郷547"], monkeypatch)
    assert code == 0
    assert "County:        中郡" in out
    assert "City:          大磯町" in out
    assert "LG Code:       143413" in out


def test_cli_parse_json(monkeypatch):
    code, out, err = run_cli(["parse", "東京都港区六本木1-2-3", "--json"], monkeypatch)
    assert code == 0
    data = json.loads(out)
    assert data["raw_input"] == "東京都港区六本木1-2-3"
    assert data["confidence_score"] == 1.0
    assert "components" in data
    assert data["components"]["town"] == "六本木"
    assert "tier_map" in data


# ==============================================================================
# 3. validate command tests & exit codes
# ==============================================================================

def test_cli_validate_accepted(monkeypatch):
    code, out, err = run_cli(["validate", "東京都港区六本木1-2-3"], monkeypatch)
    assert code == 0
    assert "Status:      ACCEPTED" in out
    assert "Valid:       Yes" in out
    assert "Confidence:  1.00" in out
    assert "LG Code:     131032" in out


def test_cli_validate_accepted_county(monkeypatch):
    code, out, err = run_cli(["validate", "神奈川県中郡大磯町国府本郷547"], monkeypatch)
    assert code == 0
    assert "Status:      ACCEPTED" in out
    assert "LG Code:     143413" in out


def test_cli_validate_ambiguous(monkeypatch):
    code, out, err = run_cli(["validate", "府中市宮西町2-24"], monkeypatch)
    assert code == 2  # Exit code 2 for ambiguity
    assert "Status:      AMBIGUOUS" in out
    assert "Valid:       No" in out
    assert "Candidates:" in out
    assert "東京都府中市 (132063)" in out
    assert "広島県府中市 (342084)" in out


def test_cli_validate_malformed(monkeypatch):
    code, out, err = run_cli(["validate", "123 Main St, New York"], monkeypatch)
    assert code == 1  # Exit code 1 for malformed
    assert "Status:      MALFORMED" in out
    assert "Valid:       No" in out
    assert "Confidence:  0.00" in out


def test_cli_validate_json_accepted(monkeypatch):
    code, out, err = run_cli(["validate", "東京都港区六本木1-2-3", "--json"], monkeypatch)
    assert code == 0
    data = json.loads(out)
    assert data["status"] == "ACCEPTED"
    assert data["valid"] is True
    assert data["confidence_score"] == 1.0
    assert data["lg_code"] == "131032"


def test_cli_validate_json_ambiguous(monkeypatch):
    code, out, err = run_cli(["validate", "府中市宮西町2-24", "--json"], monkeypatch)
    assert code == 2
    data = json.loads(out)
    assert data["status"] == "AMBIGUOUS"
    assert data["valid"] is False
    assert len(data["ambiguous_candidates"]) == 2


# ==============================================================================
# 4. CLI Argument Parsing and Errors
# ==============================================================================

def test_cli_missing_address_argument(monkeypatch):
    code, out, err = run_cli(["normalize"], monkeypatch)
    assert code == 2
    assert "required: address" in err or "usage:" in err


def test_cli_help(monkeypatch):
    code, out, err = run_cli(["--help"], monkeypatch)
    assert code == 0
    assert "normalize" in out
    assert "parse" in out
    assert "validate" in out
    assert "geocode" in out


def test_cli_no_args_shows_help(monkeypatch):
    code, out, err = run_cli([], monkeypatch)
    assert code == 0
    assert "JADEN" in out


# ==============================================================================
# 5. Public Python API validation tests
# ==============================================================================

def test_python_api_validate():
    val1 = validate("東京都港区六本木1-2-3")
    assert isinstance(val1, ValidationResult)
    assert val1.status == ValidationStatus.ACCEPTED.value
    assert val1.valid is True

    val2 = validate("府中市宮西町2-24")
    assert val2.status == ValidationStatus.AMBIGUOUS.value
    assert val2.valid is False
    assert val2.is_ambiguous is True

    val3 = validate("123 Main St, New York")
    assert val3.status == ValidationStatus.MALFORMED.value
    assert val3.valid is False


def test_python_api_parse():
    components = parse("京都府中京区御池通東洞院東入笹屋町436")
    assert components.prefecture == "京都府"
    assert components.city == "京都市"
    assert components.ward == "中京区"
    assert components.kyoto_direction is not None
    assert components.kyoto_direction.street_1 == "御池通"
    assert components.kyoto_direction.street_2 == "東洞院"
    assert components.banchi == 436
