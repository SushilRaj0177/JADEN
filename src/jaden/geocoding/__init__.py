"""JADEN: Optional geospatial resolution layer.

Provides zero-dependency geospatial coordinate resolution for parsed
Japanese addresses.
"""

from typing import Optional, Union, Any

from .base import BaseGeospatialResolver
from .gsi import GSIGeocoder
from ..models.address import NormalizedAddress
from ..models.geospatial import GeocodingStatus, Coordinates, GeospatialResult

_DEFAULT_GEOCODER: Optional[GSIGeocoder] = None


def geocode(
    address: Union[str, NormalizedAddress],
    resolver: Optional[BaseGeospatialResolver] = None,
    **kwargs: Any,
) -> GeospatialResult:
    """Resolves a Japanese address string or NormalizedAddress to geographic coordinates.

    Args:
        address: Raw address string or JADEN NormalizedAddress object.
        resolver: Optional custom geospatial resolver implementing BaseGeospatialResolver.
                  Defaults to GSIGeocoder querying the Geospatial Information Authority of Japan.
        **kwargs: Optional arguments passed to the default resolver (e.g. timeout=5.0).

    Returns:
        GeospatialResult containing status (SUCCESS, NO_MATCH, AMBIGUOUS, ERROR),
        coordinates (latitude, longitude), provider name, matched address, and metadata.
    """
    if resolver is not None:
        return resolver.resolve(address)

    global _DEFAULT_GEOCODER
    timeout = kwargs.get("timeout", 5.0)
    if _DEFAULT_GEOCODER is None or _DEFAULT_GEOCODER._timeout != timeout:
        _DEFAULT_GEOCODER = GSIGeocoder(timeout=timeout)

    return _DEFAULT_GEOCODER.resolve(address)


__all__ = [
    "BaseGeospatialResolver",
    "GSIGeocoder",
    "geocode",
    "GeocodingStatus",
    "Coordinates",
    "GeospatialResult",
]
