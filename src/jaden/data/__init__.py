"""JADEN data access and registry utilities."""

from .loader import (
    MunicipalityRecord,
    AddressDataRegistry,
    get_registry,
)

__all__ = [
    "MunicipalityRecord",
    "AddressDataRegistry",
    "get_registry",
]
