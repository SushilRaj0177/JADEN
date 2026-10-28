"""Pytest fixtures and configuration for JADEN test suite."""

import pytest
from jaden.data.loader import get_registry, AddressDataRegistry
from jaden.engine import AddressNormalizer


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
