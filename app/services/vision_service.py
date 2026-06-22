import asyncio
from typing import Any, Dict, List, Optional

try:
    from google.cloud import vision

    _vision_available = True
except ImportError:
    vision = None  # type: ignore
    _vision_available = False

import structlog

from app.core.config import get_settings
from app.models.schemas import DataSource, LocationHypothesis

logger = structlog.get_logger(__name__)
settings = get_settings()


class VisionService:
    def __init__(self) -> None:
        self.client: Optional[vision.ImageAnnotatorClient] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        if not _vision_available:
            logger.warning(
                "google-cloud-vision package not installed — Vision API disabled. "
                "Install with: pip install google-cloud-vision"
            )
            return
        try:
            if settings.google_cloud_credentials_path:
                self.client = vision.ImageAnnotatorClient.from_service_account_file(
                    settings.google_cloud_credentials_path
                )
            else:
                self.client = vision.ImageAnnotatorClient()

            logger.info("Google Vision client initialized")
        except Exception as e:
            logger.error("Failed to initialize Vision client", error=str(e))
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    async def detect_landmarks(self, image_path: str) -> List[LocationHypothesis]:
        if not self.is_available():
            logger.warning("Vision API not available")
            return []

        try:
            with open(image_path, "rb") as image_file:
                content = image_file.read()

            client = self.client
            assert client is not None
            image = vision.Image(content=content)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.landmark_detection(image=image)
            )

            if response.error.message:
                logger.error("Vision API error", error=response.error.message)
                return []

            hypotheses = []
            for landmark in response.landmark_annotations:
                if landmark.score >= settings.landmark_confidence_threshold:
                    for location in landmark.locations:
                        hypothesis = LocationHypothesis(
                            latitude=location.lat_lng.latitude,
                            longitude=location.lat_lng.longitude,
                            confidence=landmark.score,
                            source=DataSource.LANDMARK_DETECTION,
                            landmark_name=landmark.description,
                            description=f"Landmark: {landmark.description}",
                        )
                        hypotheses.append(hypothesis)

            logger.info("Landmark detection completed", count=len(hypotheses))
            return hypotheses

        except Exception as e:
            logger.error("Error in landmark detection", error=str(e))
            return []

    async def detect_text(self, image_path: str) -> List[str]:
        if not self.is_available():
            logger.warning("Vision API not available")
            return []

        try:
            with open(image_path, "rb") as image_file:
                content = image_file.read()

            client = self.client
            assert client is not None
            image = vision.Image(content=content)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.text_detection(image=image)
            )

            if response.error.message:
                logger.error("Vision API error", error=response.error.message)
                return []

            texts = []
            for text in response.text_annotations:
                if text.description and len(text.description.strip()) > 2:
                    texts.append(text.description.strip())

            logger.info("Text detection completed", count=len(texts))
            return texts

        except Exception as e:
            logger.error("Error in text detection", error=str(e))
            return []

    async def detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        if not self.is_available():
            return []

        try:
            with open(image_path, "rb") as image_file:
                content = image_file.read()

            client = self.client
            assert client is not None
            image = vision.Image(content=content)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, lambda: client.object_localization(image=image)
            )

            if response.error.message:
                logger.error("Vision API error", error=response.error.message)
                return []

            objects = []
            for obj in response.localized_object_annotations:
                objects.append(
                    {
                        "name": obj.name,
                        "score": obj.score,
                        "bounding_poly": {
                            "vertices": [
                                {"x": vertex.x, "y": vertex.y}
                                for vertex in obj.bounding_poly.normalized_vertices
                            ]
                        },
                    }
                )

            logger.info("Object detection completed", count=len(objects))
            return objects

        except Exception as e:
            logger.error("Error in object detection", error=str(e))
            return []

    def get_service_info(self) -> Dict[str, Any]:
        return {
            "name": "Google Cloud Vision",
            "available": self.is_available(),
            "features": ["landmark_detection", "text_detection", "object_detection"],
        }
