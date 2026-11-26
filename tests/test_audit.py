"""Auditing records that carry an address and a municipality code."""

import csv
import io
from pathlib import Path

from jaden.audit import VERDICTS, check_record
from jaden.batch import run_audit


def test_consistent() -> None:
    r = check_record("東京都港区芝公園4-2-8", "131032")
    assert r.verdict == "consistent" and r.resolved_code == "131032" and r.municipality_written


def test_five_digit_codes_and_designated_cities() -> None:
    assert check_record("東京都港区芝公園4-2-8", "13103").verdict == "consistent"
    # The register gives the city; the address names a ward of it
    assert check_record("北海道札幌市中央区北1条西2丁目", "011002").verdict == "consistent"


def test_conflict_names_the_other_municipality() -> None:
    r = check_record("東京都港区芝公園4-2-8", "131016")
    assert r.verdict == "conflict" and r.suggested_code == "131032" and not r.claimed_name_in_address


def test_conflict_when_the_address_names_two_municipalities() -> None:
    r = check_record("茨城県阿見町牛久市柏田町1589-3", "084433")
    assert r.verdict == "conflict" and r.claimed_name_in_address


def test_former_names_and_retired_codes() -> None:
    assert check_record("埼玉県鳩ヶ谷市里1650", "112038").verdict == "consistent_former_name"
    r = check_record("埼玉県鳩ヶ谷市里1650", "112267")
    assert r.verdict == "code_retired" and r.code_status == "retired" and r.claimed_current == ("112038",)


def test_addresses_without_a_municipality() -> None:
    assert check_record("錦町1-2", "132021").verdict == "undetermined"
    r = check_record("錦町1-2", "131032")
    assert r.verdict == "district_not_in_claimed" and len(r.candidates) == 93


def test_unreadable_and_invalid() -> None:
    assert check_record("あいうえお", "131032").verdict == "unreadable"
    assert check_record("東京都港区芝公園4-2-8", "999999").verdict == "code_invalid"


def test_every_verdict_is_documented() -> None:
    import jaden.audit
    for v in VERDICTS:
        assert v in (jaden.audit.__doc__ or "")


def test_run_audit_on_a_file(tmp_path: Path) -> None:
    src = tmp_path / "in.csv"
    src.write_text("name,address,code\nA,東京都港区芝公園4-2-8,131032\nB,東京都港区芝公園4-2-8,131016\n", encoding="utf-8")
    out = tmp_path / "out.csv"
    counts = run_audit(src, out, code_column="code", log=io.StringIO())
    assert counts == {"consistent": 1, "conflict": 1}
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [r["jaden_audit"] for r in rows] == ["consistent", "conflict"]
    assert rows[1]["jaden_suggested_code"] == "131032" and rows[0]["name"] == "A"


def test_audit_command(tmp_path: Path, capsys) -> None:
    from jaden.cli import main
    src = tmp_path / "in.csv"
    src.write_text("address,code\n東京都港区芝公園4-2-8,131032\n", encoding="utf-8")
    assert main(["audit", str(src), "--code-column", "code"]) == 0
    assert "consistent" in capsys.readouterr().out
