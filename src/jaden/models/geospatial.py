"""JADEN: Strongly-typed data models for geospatial resolution.

Defines status enums, coordinate structures, and resolution outcomes
without fabricating artificial confidence metrics.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, Tuple
import json


class GeocodingStatus(str, Enum):
    """Status outcomes for geospatial resolution operations."""
    SUCCESS = "SUCCESS"          # Resolved to definitive coordinates
    NO_MATCH = "NO_MATCH"        # Address not found or unrecognized by provider
    AMBIGUOUS = "AMBIGUOUS"      # Multiple conflicting candidate locations
    ERROR = "ERROR"              # Network, timeout, provider, or parsing failure


@dataclass(frozen=True, slots=True)
class Coordinates:
    """Geographic point coordinates (JGD2011 / WGS 84 compatible datum, EPSG:6668 / EPSG:4326)."""
    latitude: float
    longitude: float

    def to_dict(self) -> Dict[str, float]:
        return {"latitude": self.latitude, "longitude": self.longitude}


@dataclass(frozen=True, slots=True)
class GeospatialResult:
    """Output structure of a JADEN geospatial resolution operation."""
    query: str
    status: str
    coordinates: Optional[Coordinates] = None
    provider: str = ""
    matched_address: Optional[str] = None
    candidates: Tuple[str, ...] = field(default_factory=tuple)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the result to a clean dictionary."""
        data: Dict[str, Any] = {
            "query": self.query,
            "status": self.status,
            "provider": self.provider,
            "coordinates": self.coordinates.to_dict() if self.coordinates else None,
            "matched_address": self.matched_address,
            "candidates": list(self.candidates),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }
        return data

    def to_json(self, indent: Optional[int] = None) -> str:
        """Serializes the result to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)
