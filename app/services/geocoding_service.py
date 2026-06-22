import asyncio
from typing import List, Optional

import httpx
import structlog
from geopy.geocoders import Nominatim

try:
    import googlemaps

    _googlemaps_available = True
except ImportError:
    googlemaps = None  # type: ignore
    _googlemaps_available = False

from app.core.config import get_settings
from app.models.schemas import DataSource, LocationHypothesis
from app.utils.geo_utils import GeoUtils

logger = structlog.get_logger(__name__)
settings = get_settings()


class GeocodingService:
    def __init__(self) -> None:
        self.google_maps_client: Optional[googlemaps.Client] = None
        self.nominatim_client: Optional[Nominatim] = None
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        if settings.google_maps_api_key and _googlemaps_available:
            try:
                self.google_maps_client = googlemaps.Client(
                    key=settings.google_maps_api_key
                )
                logger.info("Google Maps client initialized")
            except Exception as e:
                logger.error("Failed to initialize Google Maps client", error=str(e))
        elif settings.google_maps_api_key and not _googlemaps_available:
            logger.warning(
                "googlemaps package not installed — Google Maps geocoding disabled. Install with: pip install googlemaps"
            )

        try:
            self.nominatim_client = Nominatim(
                user_agent="photo_geolocation/1.0", timeout=10
            )
            logger.info("Nominatim client initialized")
        except Exception as e:
            logger.error("Failed to initialize Nominatim client", error=str(e))

    async def geocode_text_list(self, texts: List[str]) -> List[LocationHypothesis]:
        hypotheses = []

        for text in texts:
            location_candidates = self._extract_location_candidates(text)

            for candidate in location_candidates:
                candidate_hypotheses = []

                if self.google_maps_client:
                    google_results = await self._geocode_google_maps(candidate)
                    candidate_hypotheses.extend(google_results)

                locationiq_results = await self._geocode_locationiq(candidate)
                candidate_hypotheses.extend(locationiq_results)

                opencage_results = await self._geocode_opencage(candidate)
                candidate_hypotheses.extend(opencage_results)

                if not candidate_hypotheses and self.nominatim_client:
                    nominatim_results = await self._geocode_nominatim(candidate)
                    candidate_hypotheses.extend(nominatim_results)

                hypotheses.extend(candidate_hypotheses)

        unique_hypotheses = self._deduplicate_hypotheses(hypotheses)
        unique_hypotheses.sort(key=lambda x: x.confidence, reverse=True)

        return unique_hypotheses[:10]

    def _extract_location_candidates(self, text: str) -> List[str]:
        import re

        candidates = []

        coordinates = GeoUtils.extract_coordinates_from_text(text)
        for lat, lon in coordinates:
            candidates.append(f"{lat},{lon}")

        patterns = [
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*(?:\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd))\b",
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*,\s*[A-Z]{2,}\b",
            r"\b(?:University of|Museum of|Cathedral of|Church of|Bridge|Tower|Palace|Castle|Hotel)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            candidates.extend(matches)

        words = text.split()
        for i, word in enumerate(words):
            if word[0].isupper() and len(word) > 3:
                candidates.append(word)
                if i < len(words) - 1 and words[i + 1][0].isupper():
                    candidates.append(f"{word} {words[i+1]}")

        candidates = [c.strip() for c in candidates if c.strip() and len(c.strip()) > 2]
        return list(set(candidates))

    async def _geocode_google_maps(self, query: str) -> List[LocationHypothesis]:
        if not self.google_maps_client:
            return []

        try:
            results = self.google_maps_client.geocode(query)
            hypotheses = []

            for result in results:
                geometry = result.get("geometry", {})
                location = geometry.get("location", {})

                if "lat" in location and "lng" in location:
                    hypothesis = LocationHypothesis(
                        latitude=location["lat"],
                        longitude=location["lng"],
                        confidence=0.8,
                        source=DataSource.OCR_GEOCODING,
                        description=result.get("formatted_address", query),
                        address=result.get("formatted_address"),
                    )

                    for component in result.get("address_components", []):
                        types = component.get("types", [])
                        if "country" in types:
                            hypothesis.country = component.get("long_name")
                            hypothesis.country_code = component.get("short_name")
                        elif "administrative_area_level_1" in types:
                            hypothesis.admin_area = component.get("long_name")
                        elif "locality" in types:
                            hypothesis.locality = component.get("long_name")
                        elif "postal_code" in types:
                            hypothesis.postal_code = component.get("long_name")

                    hypotheses.append(hypothesis)

            return hypotheses

        except Exception as e:
            logger.error("Google Maps geocoding error", error=str(e))
            return []

    async def _geocode_locationiq(self, query: str) -> List[LocationHypothesis]:
        if not settings.locationiq_api_key:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://us1.locationiq.com/v1/search.php",
                    params={
                        "key": settings.locationiq_api_key,
                        "q": query,
                        "format": "json",
                        "limit": 5,
                        "addressdetails": 1,
                    },
                    timeout=10,
                )

                if response.status_code == 200:
                    results = response.json()
                    hypotheses = []

                    for result in results:
                        lat, lon = float(result["lat"]), float(result["lon"])

                        if GeoUtils.validate_coordinates(lat, lon)[0]:
                            hypothesis = LocationHypothesis(
                                latitude=lat,
                                longitude=lon,
                                confidence=float(result.get("importance", 0.5)),
                                source=DataSource.OCR_GEOCODING,
                                description=result.get("display_name", query),
                                address=result.get("display_name"),
                            )

                            address = result.get("address", {})
                            hypothesis.country = address.get("country")
                            hypothesis.country_code = address.get("country_code")
                            hypothesis.admin_area = address.get("state")
                            hypothesis.locality = address.get("city")
                            hypothesis.postal_code = address.get("postcode")

                            hypotheses.append(hypothesis)

                    return hypotheses

        except Exception as e:
            logger.error("LocationIQ geocoding error", error=str(e))
            return []

        return []

    async def _geocode_opencage(self, query: str) -> List[LocationHypothesis]:
        if not settings.opencage_api_key:
            return []

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.opencagedata.com/geocode/v1/json",
                    params={"key": settings.opencage_api_key, "q": query, "limit": 5},
                    timeout=10,
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    hypotheses = []

                    for result in results:
                        geometry = result.get("geometry", {})
                        lat, lon = geometry.get("lat"), geometry.get("lng")

                        if lat is not None and lon is not None:
                            confidence = result.get("confidence", 1) / 10

                            hypothesis = LocationHypothesis(
                                latitude=lat,
                                longitude=lon,
                                confidence=confidence,
                                source=DataSource.OCR_GEOCODING,
                                description=result.get("formatted"),
                                address=result.get("formatted"),
                            )

                            components = result.get("components", {})
                            hypothesis.country = components.get("country")
                            hypothesis.country_code = components.get("country_code")
                            hypothesis.admin_area = components.get("state")
                            hypothesis.locality = components.get("city")
                            hypothesis.postal_code = components.get("postcode")

                            hypotheses.append(hypothesis)

                    return hypotheses

        except Exception as e:
            logger.error("OpenCage geocoding error", error=str(e))
            return []

        return []

    async def _geocode_nominatim(self, query: str) -> List[LocationHypothesis]:
        if not self.nominatim_client:
            return []

        try:
            loop = asyncio.get_event_loop()
            client = self.nominatim_client
            assert client is not None
            locations = await loop.run_in_executor(
                None,
                lambda: client.geocode(
                    query, exactly_one=False, limit=5
                ),
            )

            hypotheses = []
            if locations:
                for location in locations:
                    hypothesis = LocationHypothesis(
                        latitude=location.latitude,
                        longitude=location.longitude,
                        confidence=0.5,
                        source=DataSource.OCR_GEOCODING,
                        description=location.address,
                        address=location.address,
                    )
                    hypotheses.append(hypothesis)

            return hypotheses

        except Exception as e:
            logger.error("Nominatim geocoding error", error=str(e))
            return []

    def _deduplicate_hypotheses(
        self, hypotheses: List[LocationHypothesis]
    ) -> List[LocationHypothesis]:
        seen = set()
        unique_hypotheses = []

        for hypothesis in hypotheses:
            coord_key = (round(hypothesis.latitude, 4), round(hypothesis.longitude, 4))

            if coord_key not in seen:
                seen.add(coord_key)
                unique_hypotheses.append(hypothesis)

        return unique_hypotheses

    async def reverse_geocode(
        self, latitude: float, longitude: float
    ) -> Optional[LocationHypothesis]:
        if self.google_maps_client:
            try:
                results = self.google_maps_client.reverse_geocode((latitude, longitude))
                if results:
                    result = results[0]
                    return LocationHypothesis(
                        latitude=latitude,
                        longitude=longitude,
                        confidence=0.9,
                        source=DataSource.REVERSE_GEOCODING,
                        address=result.get("formatted_address"),
                        description=f"Reverse geocoded: {result.get('formatted_address')}",
                    )
            except Exception as e:
                logger.error("Google reverse geocoding error", error=str(e))

        if self.nominatim_client:
            try:
                loop = asyncio.get_event_loop()
                client = self.nominatim_client
                assert client is not None
                location = await loop.run_in_executor(
                    None,
                    lambda: client.reverse(f"{latitude}, {longitude}"),
                )

                if location:
                    return LocationHypothesis(
                        latitude=latitude,
                        longitude=longitude,
                        confidence=0.7,
                        source=DataSource.REVERSE_GEOCODING,
                        address=location.address,
                        description=f"Reverse geocoded: {location.address}",
                    )
            except Exception as e:
                logger.error("Nominatim reverse geocoding error", error=str(e))

        return None
