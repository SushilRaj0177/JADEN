"""JADEN: Base abstraction for optional geospatial resolution.

Defines the abstract resolver interface allowing arbitrary geocoding backends
(GSI, OpenStreetMap, local GIS databases, municipal centroid indices)
to be plugged into JADEN without altering core parsing logic.
"""

from abc import ABC, abstractmethod
from typing import Union
from ..models.address import NormalizedAddress
from ..models.geospatial import GeospatialResult


class BaseGeospatialResolver(ABC):
    """Abstract base class for all JADEN geospatial resolvers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the resolver provider (e.g. 'gsi', 'offline_centroid')."""
        pass

    @abstractmethod
    def resolve(self, address: Union[str, NormalizedAddress]) -> GeospatialResult:
        """Resolves a Japanese address string or NormalizedAddress to geographic coordinates.

        Args:
            address: Either a raw/normalized address string or a JADEN NormalizedAddress object.

        Returns:
            GeospatialResult containing match status, coordinates, and metadata.
        """
        pass
