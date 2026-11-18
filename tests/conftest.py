"""Pytest fixtures and configuration for JADEN test suite."""

import os
import tempfile

# The tests pin results on the bundled data. Data a user installed (`jaden data update`,
# `jaden data fetch-blocks`) legitimately changes some answers, e.g. block data shows that a
# number is a land lot (103番地の2) rather than a block (103番2号), so it is hidden from the
# tests unless JADEN_TESTS_USE_INSTALLED_DATA=1.
if not os.environ.get("JADEN_TESTS_USE_INSTALLED_DATA"):
    os.environ["XDG_DATA_HOME"] = tempfile.mkdtemp(prefix="jaden-tests-")
    os.environ.pop("JADEN_DATA_DIR", None)

import pytest  # noqa: E402
from jaden.data.loader import get_registry, AddressDataRegistry  # noqa: E402
from jaden.engine import AddressNormalizer  # noqa: E402


@pytest.fixture(scope="session")
def registry() -> AddressDataRegistry:
    """Session-scoped loaded registry."""
    return get_registry()


@pytest.fixture(scope="session")
def normalizer() -> AddressNormalizer:
    """Session-scoped address normalizer."""
    return AddressNormalizer()


@pytest.fixture(scope="session")
def parser_only() -> AddressNormalizer:
    """Normalizer without the town gazetteer: structural parsing and the MIC registry only."""
    return AddressNormalizer(use_gazetteer=False)
