import asyncio
from typing import Any, List, Optional

import httpx
import structlog
from geopy.geocoders import Nominatim

from app.core.config import get_settings
from app.models.schemas import DataSource, LocationHypothesis
from app.utils.geo_utils import GeoUtils

logger = structlog.get_logger(__name__)
settings = get_settings()


class GeocodingService:
    def __init__(self) -> None:
        self.nominatim_client: Optional[Nominatim] = None
        self._initialize_clients()

    def _initialize_clients(self) -> None:
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

            def run_geocode() -> Any:
                return client.geocode(query, exactly_one=False, limit=5)

            locations: Any = await loop.run_in_executor(None, run_geocode)

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
        if self.nominatim_client:
            try:
                loop = asyncio.get_event_loop()
                client = self.nominatim_client
                assert client is not None

                def run_reverse() -> Any:
                    return client.reverse(f"{latitude}, {longitude}")

                location: Any = await loop.run_in_executor(None, run_reverse)

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
