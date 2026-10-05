"""Tests for packaging, metadata, distribution assets, and public API integrity."""

import json
from pathlib import Path
import pytest

import jaden
from jaden.data.loader import get_registry


def test_package_metadata():
    """Verify package metadata constants."""
    assert hasattr(jaden, "__version__")
    assert jaden.__version__ == "0.1.0"
    assert hasattr(jaden, "__author__")
    assert jaden.__author__ == "Sushil Raj"


def test_package_public_api_exports():
    """Verify that all public API symbols declared in __all__ are directly importable."""
    expected_exports = [
        "AddressNormalizer",
        "normalize",
        "parse",
        "validate",
        "AddressComponents",
        "NormalizedAddress",
        "ValidationStatus",
        "ValidationResult",
        "KyotoDirectionClause",
        "HokkaidoGridClause",
        "TaxonomyTier",
        "PrefectureRecord",
        "LocalGovernmentCode",
        "calculate_modulus11_check_digit",
        "get_registry",
    ]
    for symbol in expected_exports:
        assert hasattr(jaden, symbol), f"Expected '{symbol}' to be exported from top-level jaden package"
        assert symbol in jaden.__all__, f"Expected '{symbol}' in jaden.__all__"


def test_runtime_package_data_files_exist():
    """Verify runtime package data files are present and valid JSON."""
    data_dir = Path(jaden.__file__).parent / "data"
    assert data_dir.exists() and data_dir.is_dir()

    required_data_files = [
        "jis_prefectures.json",
        "municipalities.json",
        "county_mapping.json",
        "provenance.json",
    ]

    for fname in required_data_files:
        fpath = data_dir / fname
        assert fpath.exists(), f"Runtime package data file missing: {fname}"
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert len(data) > 0, f"Package data file is empty: {fname}"


def test_registry_loads_all_bundled_records():
    """Verify registry parses all statutory records from bundled package data."""
    reg = get_registry()
    prefs = reg.list_all_prefectures()
    assert len(prefs) == 47

    # Check designated city and standard ward
    minato = reg.get_municipality_by_code("131032")
    assert minato is not None
    assert minato.name == "港区"

    # Check county mapping
    oiso = reg.get_municipality_by_code("143413")
    assert oiso is not None
    assert oiso.county == "中郡"
    assert oiso.name == "大磯町"

    # Check provenance
    prov = reg.get_provenance()
    assert prov.get("source_organization") is not None


def test_cli_entrypoint_callable():
    """Verify the CLI main entrypoint function is importable and callable."""
    from jaden.cli import main
    assert callable(main)
    # Invoking with --version should return 0
    assert main(["--version"]) == 0
