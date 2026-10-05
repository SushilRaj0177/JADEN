"""JADEN: Japanese Address Data Engineering & Normalization Engine.

A deterministic, high-throughput Python engine for Japanese address canonicalization,
administrative disambiguation, and statutory classification.
"""

__version__ = "0.1.0"
__author__ = "Sushil Raj"

from .engine import AddressNormalizer, normalize, parse, validate
from .models.address import AddressComponents, NormalizedAddress, KyotoDirectionClause, HokkaidoGridClause
from .models.codes import TaxonomyTier, PrefectureRecord, LocalGovernmentCode, calculate_modulus11_check_digit
from .models.validation import ValidationStatus, ValidationResult
from .models.geospatial import GeocodingStatus, Coordinates, GeospatialResult
from .geocoding import BaseGeospatialResolver, GSIGeocoder, geocode
from .data.loader import get_registry

__all__ = [
    "__version__",
    "__author__",
    "AddressNormalizer",
    "normalize",
    "parse",
    "validate",
    "geocode",
    "AddressComponents",
    "NormalizedAddress",
    "ValidationStatus",
    "ValidationResult",
    "GeocodingStatus",
    "Coordinates",
    "GeospatialResult",
    "BaseGeospatialResolver",
    "GSIGeocoder",
    "KyotoDirectionClause",
    "HokkaidoGridClause",
    "TaxonomyTier",
    "PrefectureRecord",
    "LocalGovernmentCode",
    "calculate_modulus11_check_digit",
    "get_registry",
]
