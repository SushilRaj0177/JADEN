"""JADEN: Japanese Address Data Engineering & Normalization Engine.

A deterministic, high-throughput Python engine for Japanese address canonicalization,
administrative disambiguation, and statutory classification.
"""

__version__ = "0.3.0"
__author__ = "Sushil Raj"

from .engine import AddressNormalizer, normalize, parse, validate
from .models.address import AddressComponents, NormalizedAddress, KyotoDirectionClause, HokkaidoGridClause
from .models.codes import TaxonomyTier, PrefectureRecord, LocalGovernmentCode, calculate_modulus11_check_digit
from .models.validation import ValidationStatus, ValidationResult
from .models.geospatial import GeocodingStatus, Coordinates, GeospatialResult
from .geocoding import BaseGeospatialResolver, GSIGeocoder, OfflineGeocoder, geocode
from .data.loader import get_registry
from .matching import AddressComparison, compare, find_duplicates, match_key
from .extract import ExtractedAddress, extract_addresses
from .lookup import PostalAddress, ReverseResult, Suggestion, lookup_postal, reverse_geocode, suggest

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
    "OfflineGeocoder",
    "KyotoDirectionClause",
    "HokkaidoGridClause",
    "TaxonomyTier",
    "PrefectureRecord",
    "LocalGovernmentCode",
    "calculate_modulus11_check_digit",
    "get_registry",
    "AddressComparison",
    "compare",
    "find_duplicates",
    "match_key",
    "ExtractedAddress",
    "extract_addresses",
    "PostalAddress",
    "ReverseResult",
    "Suggestion",
    "lookup_postal",
    "reverse_geocode",
    "suggest",
]
