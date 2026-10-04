"""JADEN: Japanese Address Data Engineering & Normalization Engine.

A deterministic, high-throughput Python engine for Japanese address canonicalization,
administrative disambiguation, and statutory classification.
"""

__version__ = "0.1.0"
__author__ = "Sushil Raj"

from .engine import AddressNormalizer, normalize
from .models.address import AddressComponents, NormalizedAddress, KyotoDirectionClause, HokkaidoGridClause
from .models.codes import TaxonomyTier, PrefectureRecord, LocalGovernmentCode, calculate_modulus11_check_digit
from .data.loader import get_registry

__all__ = [
    "__version__",
    "__author__",
    "AddressNormalizer",
    "normalize",
    "AddressComponents",
    "NormalizedAddress",
    "KyotoDirectionClause",
    "HokkaidoGridClause",
    "TaxonomyTier",
    "PrefectureRecord",
    "LocalGovernmentCode",
    "calculate_modulus11_check_digit",
    "get_registry",
]
