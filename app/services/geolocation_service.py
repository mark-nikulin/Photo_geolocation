import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

import structlog

from app.core.config import get_settings
from app.models.schemas import (
    DataSource,
    GeolocationRequest,
    GeolocationResponse,
    ImageMetadata,
    LocationHypothesis,
    ProcessingMetadata,
)
from app.services.geocoding_service import GeocodingService
from app.services.vision_service import VisionService
from app.utils.cache import cache_manager
from app.utils.geo_utils import GeoUtils
from app.utils.image_processing import ImageProcessor

logger = structlog.get_logger(__name__)
settings = get_settings()


class GeolocationService:
    def __init__(self) -> None:
        self.vision_service = VisionService()
        self.geocoding_service = GeocodingService()
        self.image_processor = ImageProcessor()
        self.processing_stats: Dict[str, Any] = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "processing_times": [],
        }

    async def process_image(
        self, image_path: Path, request: GeolocationRequest
    ) -> GeolocationResponse:
        start_time = time.time()
        request_id = str(uuid.uuid4())

        self.processing_stats["total_requests"] += 1

        processing_metadata = ProcessingMetadata(processing_time_ms=0, apis_used=[])

        try:
            cache_key = cache_manager.generate_key(
                f"{self.image_processor.generate_hash(image_path)}_{request.mode.value}_{request.min_confidence}",
                "geolocation",
            )

            cached_result = await cache_manager.get(cache_key)
            if cached_result:
                processing_metadata.cache_hit = True
                processing_metadata.processing_time_ms = int(
                    (time.time() - start_time) * 1000
                )
                logger.info("Cache hit for geolocation", request_id=request_id)
                return cached_result  # type: ignore

            is_valid, error_msg = self.image_processor.validate_image(image_path)
            if not is_valid:
                raise ValueError(f"Invalid image: {error_msg}")

            image_metadata = self._extract_image_metadata(image_path)
            all_hypotheses = []

            exif_hypotheses = self._extract_exif_coordinates(image_metadata)
            if exif_hypotheses:
                all_hypotheses.extend(exif_hypotheses)
                logger.info(
                    "Found EXIF GPS coordinates",
                    request_id=request_id,
                    count=len(exif_hypotheses),
                )

            if self.vision_service.is_available():
                processing_metadata.apis_used.append("gemini_vision_landmark")
                landmark_hypotheses = await self.vision_service.detect_landmarks(
                    str(image_path)
                )
                all_hypotheses.extend(landmark_hypotheses)
                processing_metadata.landmark_results_count = len(landmark_hypotheses)

                if request.mode.value in ["standard", "comprehensive"]:
                    processing_metadata.apis_used.append("gemini_vision_text")
                    texts = await self.vision_service.detect_text(str(image_path))
                    processing_metadata.text_results_count = len(texts)

                    if texts:
                        geocoding_hypotheses = (
                            await self.geocoding_service.geocode_text_list(texts)
                        )
                        all_hypotheses.extend(geocoding_hypotheses)
                        processing_metadata.geocoding_queries_count = len(texts)
                        processing_metadata.apis_used.append("geocoding_services")

            if request.mode.value == "comprehensive":
                if self.vision_service.is_available():
                    processing_metadata.apis_used.append("gemini_vision_objects")
                    objects = await self.vision_service.detect_objects(str(image_path))
                    object_hypotheses = await self._process_objects(objects)
                    all_hypotheses.extend(object_hypotheses)

            filtered_hypotheses = self._filter_hypotheses(
                all_hypotheses, request.min_confidence
            )
            ranked_hypotheses = self._rank_hypotheses(
                filtered_hypotheses, image_metadata
            )

            final_hypotheses = ranked_hypotheses[: request.max_results]

            if request.include_address:
                final_hypotheses = await self._enhance_with_addresses(final_hypotheses)

            best_guess = final_hypotheses[0] if final_hypotheses else None

            processing_metadata.processing_time_ms = int(
                (time.time() - start_time) * 1000
            )
            self.processing_stats["processing_times"].append(
                processing_metadata.processing_time_ms
            )

            response = GeolocationResponse(
                success=True,
                request_id=request_id,
                hypotheses=final_hypotheses,
                best_guess=best_guess,
                image_metadata=image_metadata if request.include_metadata else None,
                processing_metadata=(
                    processing_metadata if request.include_metadata else None
                ),
            )

            await cache_manager.set(cache_key, response, ttl=3600)

            self.processing_stats["successful_requests"] += 1
            logger.info(
                "Geolocation processing completed",
                request_id=request_id,
                hypotheses_count=len(final_hypotheses),
                processing_time_ms=processing_metadata.processing_time_ms,
            )

            return response

        except Exception as e:
            error_msg = f"Error processing image: {str(e)}"
            logger.error(
                "Geolocation processing failed", request_id=request_id, error=str(e)
            )

            processing_metadata.error_messages.append(error_msg)
            processing_metadata.processing_time_ms = int(
                (time.time() - start_time) * 1000
            )
            self.processing_stats["failed_requests"] += 1

            return GeolocationResponse(
                success=False,
                request_id=request_id,
                hypotheses=[],
                error_message=error_msg,
                processing_metadata=(
                    processing_metadata if request.include_metadata else None
                ),
            )

    def _extract_image_metadata(self, image_path: Path) -> ImageMetadata:
        try:
            metadata_dict = self.image_processor.extract_metadata(image_path)

            return ImageMetadata(
                filename=metadata_dict.get("filename", "unknown"),
                size_bytes=metadata_dict.get("size_bytes", 0),
                dimensions=metadata_dict.get("dimensions", {}),
                format=metadata_dict.get("format", "unknown"),
                has_exif=metadata_dict.get("has_exif", False),
                has_gps=metadata_dict.get("has_gps", False),
                camera_make=metadata_dict.get("exif_data", {}).get("make"),
                camera_model=metadata_dict.get("exif_data", {}).get("model"),
                datetime_taken=metadata_dict.get("exif_data", {}).get("DateTime"),
            )
        except Exception as e:
            logger.error("Error extracting image metadata", error=str(e))
            return ImageMetadata(
                filename=image_path.name,
                size_bytes=0,
                dimensions={},
                format="unknown",
                has_exif=False,
                has_gps=False,
            )

    def _extract_exif_coordinates(
        self, image_metadata: ImageMetadata
    ) -> List[LocationHypothesis]:
        if not image_metadata.has_gps:
            return []

        try:
            metadata_dict = self.image_processor.extract_metadata(
                Path(image_metadata.filename)
            )
            gps_data = metadata_dict.get("exif_data", {}).get("GPS", {})

            if "latitude" in gps_data and "longitude" in gps_data:
                hypothesis = LocationHypothesis(
                    latitude=gps_data["latitude"],
                    longitude=gps_data["longitude"],
                    confidence=1.0,
                    source=DataSource.EXIF_GPS,
                    description="GPS coordinates from image EXIF data",
                )
                return [hypothesis]
        except Exception as e:
            logger.error("Error extracting EXIF coordinates", error=str(e))

        return []

    def _filter_hypotheses(
        self, hypotheses: List[LocationHypothesis], min_confidence: float
    ) -> List[LocationHypothesis]:
        return [h for h in hypotheses if h.confidence >= min_confidence]

    def _rank_hypotheses(
        self, hypotheses: List[LocationHypothesis], image_metadata: ImageMetadata
    ) -> List[LocationHypothesis]:
        if not hypotheses:
            return []

        source_weights = {
            DataSource.EXIF_GPS: 1.0,
            DataSource.LANDMARK_DETECTION: 0.9,
            DataSource.OCR_GEOCODING: 0.7,
            DataSource.REVERSE_GEOCODING: 0.8,
        }

        for hypothesis in hypotheses:
            base_confidence = hypothesis.confidence
            source_weight = source_weights.get(hypothesis.source, 0.5)
            hypothesis.confidence = min(1.0, base_confidence * source_weight)

        if len(hypotheses) > 1:
            for i, hypothesis in enumerate(hypotheses):
                nearby_count = 0
                for j, other in enumerate(hypotheses):
                    if i != j:
                        distance = GeoUtils.calculate_distance(
                            (hypothesis.latitude, hypothesis.longitude),
                            (other.latitude, other.longitude),
                        )
                        if distance < 50:
                            nearby_count += 1

                if nearby_count > 0:
                    boost = min(0.1, nearby_count * 0.02)
                    hypothesis.confidence = min(1.0, hypothesis.confidence + boost)

        return sorted(hypotheses, key=lambda x: x.confidence, reverse=True)

    async def _enhance_with_addresses(
        self, hypotheses: List[LocationHypothesis]
    ) -> List[LocationHypothesis]:
        enhanced = []

        for hypothesis in hypotheses:
            if not hypothesis.address:
                reverse_result = await self.geocoding_service.reverse_geocode(
                    hypothesis.latitude, hypothesis.longitude
                )

                if reverse_result and reverse_result.address:
                    hypothesis.address = reverse_result.address
                    hypothesis.country = reverse_result.country
                    hypothesis.country_code = reverse_result.country_code
                    hypothesis.admin_area = reverse_result.admin_area
                    hypothesis.locality = reverse_result.locality

            enhanced.append(hypothesis)

        return enhanced

    async def _process_objects(
        self, objects: List[Dict[str, Any]]
    ) -> List[LocationHypothesis]:
        hypotheses: List[LocationHypothesis] = []

        location_objects = [
            "Tower",
            "Bridge",
            "Church",
            "Cathedral",
            "Museum",
            "Monument",
            "Stadium",
            "Airport",
            "Train station",
            "University",
            "Hospital",
        ]

        for obj in objects:
            obj_name = obj.get("name", "").lower()
            if any(
                location_obj.lower() in obj_name for location_obj in location_objects
            ):
                pass

        return hypotheses

    def get_stats(self) -> Dict[str, Any]:
        avg_time = (
            sum(self.processing_stats["processing_times"])
            / len(self.processing_stats["processing_times"])
            if self.processing_stats["processing_times"]
            else 0
        )

        return {
            "total_requests": self.processing_stats["total_requests"],
            "successful_requests": self.processing_stats["successful_requests"],
            "failed_requests": self.processing_stats["failed_requests"],
            "average_processing_time_ms": round(avg_time, 2),
            "success_rate": (
                self.processing_stats["successful_requests"]
                / self.processing_stats["total_requests"]
                if self.processing_stats["total_requests"] > 0
                else 0
            ),
        }
