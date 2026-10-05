"""JADEN: GSI (国土地理院) Geospatial Resolver.

Queries the official Geospatial Information Authority of Japan (国土地理院)
Address Search API to resolve Japanese addresses into WGS 84 coordinates.

Features:
- Zero external dependencies: Uses Python standard library urllib.request
- Zero credentials required: Free and public Japanese open government service
- Full integration with JADEN AST: Normalizes address query prior to dispatch
- Distinguishes SUCCESS, NO_MATCH, AMBIGUOUS, and ERROR without manufactured confidence scores
"""

import urllib.request
import urllib.parse
import urllib.error
import json
import socket
from typing import Optional, Union, Dict, Any, List

from ..models.address import NormalizedAddress
from ..models.geospatial import GeocodingStatus, Coordinates, GeospatialResult
from .base import BaseGeospatialResolver
from ..engine import normalize


GSI_ENDPOINT = "https://msearch.gsi.go.jp/address-search/AddressSearch"
DEFAULT_USER_AGENT = "JADEN-Geospatial-Engine/0.1.0"


class GSIGeocoder(BaseGeospatialResolver):
    """Geospatial resolver backed by the Geospatial Information Authority of Japan (GSI)."""

    def __init__(
        self,
        endpoint: str = GSI_ENDPOINT,
        timeout: float = 5.0,
        user_agent: str = DEFAULT_USER_AGENT,
        opener: Optional[urllib.request.OpenerDirector] = None,
    ) -> None:
        """Initializes the GSI geocoder.

        Args:
            endpoint: URL for the GSI AddressSearch endpoint.
            timeout: Network request timeout in seconds.
            user_agent: HTTP User-Agent string.
            opener: Optional custom urllib OpenerDirector for mocking or proxies.
        """
        self._endpoint = endpoint
        self._timeout = timeout
        self._user_agent = user_agent
        self._opener = opener or urllib.request.build_opener()

    @property
    def provider_name(self) -> str:
        return "gsi"

    def resolve(self, address: Union[str, NormalizedAddress]) -> GeospatialResult:
        """Resolves an address string or NormalizedAddress using the GSI API.

        Args:
            address: Raw Japanese address string or JADEN NormalizedAddress.

        Returns:
            GeospatialResult containing status, coordinates, and provider details.
        """
        if isinstance(address, str):
            raw_input = address
            if not raw_input or not raw_input.strip():
                return GeospatialResult(
                    query=raw_input,
                    status=GeocodingStatus.NO_MATCH.value,
                    provider=self.provider_name,
                    error_message="Empty or whitespace-only address provided.",
                )
            norm = normalize(raw_input)
        else:
            norm = address
            raw_input = norm.input_raw

        # Rejection check: If JADEN's core parser rejected the input with 0.0 confidence
        if norm.confidence_score == 0.0:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.NO_MATCH.value,
                provider=self.provider_name,
                error_message="Address rejected by JADEN validator as unrecognized or malformed.",
            )

        # Build search query string
        # Prefer canonical normalized string, falling back to raw sanitized if canonical is empty
        query_str = norm.canonical or norm.input_sanitized or raw_input

        # Dispatch HTTP GET to GSI AddressSearch
        params = urllib.parse.urlencode({"q": query_str})
        request_url = f"{self._endpoint}?{params}"
        req = urllib.request.Request(
            request_url,
            headers={"User-Agent": self._user_agent},
            method="GET",
        )

        try:
            with self._opener.open(req, timeout=self._timeout) as resp:
                status_code = resp.getcode()
                if status_code != 200:
                    return GeospatialResult(
                        query=raw_input,
                        status=GeocodingStatus.ERROR.value,
                        provider=self.provider_name,
                        error_message=f"GSI API responded with HTTP status {status_code}.",
                    )
                raw_bytes = resp.read()
                data = json.loads(raw_bytes.decode("utf-8"))

        except urllib.error.HTTPError as exc:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.ERROR.value,
                provider=self.provider_name,
                error_message=f"GSI HTTP error: {exc.code} {exc.reason}",
            )
        except urllib.error.URLError as exc:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.ERROR.value,
                provider=self.provider_name,
                error_message=f"GSI connection error: {exc.reason}",
            )
        except (socket.timeout, TimeoutError):
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.ERROR.value,
                provider=self.provider_name,
                error_message=f"GSI request timed out after {self._timeout}s.",
            )
        except json.JSONDecodeError as exc:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.ERROR.value,
                provider=self.provider_name,
                error_message=f"Failed to decode GSI JSON response: {exc}",
            )
        except Exception as exc:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.ERROR.value,
                provider=self.provider_name,
                error_message=f"Unexpected error querying GSI: {exc}",
            )

        # Parse GSI GeoJSON FeatureCollection
        if not isinstance(data, list) or len(data) == 0:
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.NO_MATCH.value,
                provider=self.provider_name,
                error_message="No matching coordinates found for the provided address.",
            )

        features: List[Dict[str, Any]] = data

        # Check for ambiguity: multiple returned candidates representing distinct titles
        candidate_titles = tuple(
            f.get("properties", {}).get("title", "").strip()
            for f in features
            if f.get("properties", {}).get("title")
        )

        # If JADEN detected administrative ambiguity or GSI returned multiple candidate places
        if norm.components.is_ambiguous or len(features) > 1:
            # Check if all returned titles and coordinates are identical (de-duplication)
            unique_titles = set(candidate_titles)
            unique_coords = {
                (
                    f.get("geometry", {}).get("coordinates", [None, None])[0],
                    f.get("geometry", {}).get("coordinates", [None, None])[1],
                )
                for f in features
                if "geometry" in f and "coordinates" in f["geometry"]
            }

            if len(unique_titles) > 1 or len(unique_coords) > 1 or norm.components.is_ambiguous:
                return GeospatialResult(
                    query=raw_input,
                    status=GeocodingStatus.AMBIGUOUS.value,
                    provider=self.provider_name,
                    matched_address=candidate_titles[0] if candidate_titles else None,
                    candidates=candidate_titles,
                    error_message=f"Ambiguous address: provider returned {len(features)} candidate locations.",
                    metadata={"candidate_count": len(features)},
                )

        # Single definitive feature
        primary = features[0]
        geometry = primary.get("geometry", {})
        coords = geometry.get("coordinates")
        if not coords or len(coords) < 2 or not isinstance(coords[0], (int, float)) or not isinstance(coords[1], (int, float)):
            return GeospatialResult(
                query=raw_input,
                status=GeocodingStatus.NO_MATCH.value,
                provider=self.provider_name,
                error_message="GSI response lacked valid coordinate geometry.",
            )

        # GeoJSON is [longitude, latitude]
        lon = float(coords[0])
        lat = float(coords[1])
        title = primary.get("properties", {}).get("title")
        address_code = primary.get("properties", {}).get("addressCode")

        metadata: Dict[str, Any] = {}
        if address_code:
            metadata["gsi_address_code"] = address_code

        return GeospatialResult(
            query=raw_input,
            status=GeocodingStatus.SUCCESS.value,
            coordinates=Coordinates(latitude=lat, longitude=lon),
            provider=self.provider_name,
            matched_address=title,
            candidates=candidate_titles,
            metadata=metadata,
        )
