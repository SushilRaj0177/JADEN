"""JADEN: Offline geospatial resolver.

Resolves addresses to the MLIT representative point of the matched block
(街区, when that prefecture's block data is installed), 丁目 or town, with no
network access. Precision is reported in ``metadata['level']`` so callers can
tell a block-level point from a town-wide one.
"""

from typing import Union

from ..models.address import NormalizedAddress
from ..models.geospatial import GeocodingStatus, Coordinates, GeospatialResult
from .base import BaseGeospatialResolver
from ..engine import normalize


class OfflineGeocoder(BaseGeospatialResolver):
    """Geospatial resolver backed by the bundled MLIT gazetteer."""

    @property
    def provider_name(self) -> str:
        return "offline"

    def resolve(self, address: Union[str, NormalizedAddress]) -> GeospatialResult:
        if isinstance(address, str):
            if not address.strip():
                return GeospatialResult(query=address, status=GeocodingStatus.NO_MATCH.value,
                                        provider=self.provider_name,
                                        error_message="Empty or whitespace-only address provided.")
            norm = normalize(address)
        else:
            norm = address
        c = norm.components

        if c.is_ambiguous:
            return GeospatialResult(
                query=norm.input_raw,
                status=GeocodingStatus.AMBIGUOUS.value,
                provider=self.provider_name,
                candidates=c.ambiguous_candidates,
                error_message="Address matches several municipalities; add the prefecture or city.",
            )
        if norm.latitude is None or norm.longitude is None:
            return GeospatialResult(
                query=norm.input_raw,
                status=GeocodingStatus.NO_MATCH.value,
                provider=self.provider_name,
                matched_address=norm.canonical or None,
                error_message="No registered town matched, so there is no offline point for this address.",
            )
        return GeospatialResult(
            query=norm.input_raw,
            status=GeocodingStatus.SUCCESS.value,
            coordinates=Coordinates(latitude=norm.latitude, longitude=norm.longitude),
            provider=self.provider_name,
            matched_address=norm.canonical,
            metadata={
                "level": norm.location_level,
                "machiaza_id": c.machiaza_id,
                "lg_code": c.lg_code,
                "source": "MLIT 位置参照情報 (block level)" if norm.location_level == "block"
                          else "MLIT 大字・町丁目レベル位置参照情報",
            },
        )
