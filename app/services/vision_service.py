import asyncio
import json
from typing import Any, Dict, List

import google.generativeai as genai
from PIL import Image

import structlog

from app.core.config import get_settings
from app.models.schemas import DataSource, LocationHypothesis

_vision_available = True

logger = structlog.get_logger(__name__)
settings = get_settings()


class VisionService:
    def __init__(self) -> None:
        self.model: Any = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        if not _vision_available:
            logger.warning(
                "google-generativeai package not installed — Vision API disabled. "
                "Install with: pip install google-generativeai pillow"
            )
            return

        try:
            if settings.gemini_api_key:
                genai.configure(api_key=settings.gemini_api_key)
                self.model = genai.GenerativeModel("gemini-flash-latest")
                logger.info("Gemini Vision client initialized")
            else:
                logger.warning("GEMINI_API_KEY is not set. Vision AI disabled.")
                self.model = None
        except Exception as e:
            logger.error("Failed to initialize Gemini client", error=str(e))
            self.model = None

    def is_available(self) -> bool:
        return self.model is not None

    async def detect_landmarks(self, image_path: str) -> List[LocationHypothesis]:
        if not self.is_available():
            logger.warning("Gemini Vision API not available")
            return []

        try:
            loop = asyncio.get_event_loop()

            def run_inference():
                img = Image.open(image_path)
                prompt = (
                    "Identify any famous landmarks, monuments, or identifiable places in this image. "
                    "Return ONLY a valid JSON array of objects. Do not use markdown blocks. "
                    "Each object must have the following keys: "
                    "'name' (string, name of the landmark), "
                    "'latitude' (float, best estimate latitude), "
                    "'longitude' (float, best estimate longitude), "
                    "'confidence' (float between 0.0 and 1.0 representing your certainty)."
                    "If no landmarks are found, return an empty array []."
                )
                response = self.model.generate_content([prompt, img])
                return response.text

            text_response = await loop.run_in_executor(None, run_inference)

            # Clean markdown codeblocks
            text_response = text_response.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            text_response = text_response.strip()

            if not text_response or text_response == "[]":
                return []

            landmarks_data = json.loads(text_response)
            hypotheses = []

            for item in landmarks_data:
                if item.get("confidence", 0) >= settings.landmark_confidence_threshold:
                    hypothesis = LocationHypothesis(
                        latitude=float(item.get("latitude", 0)),
                        longitude=float(item.get("longitude", 0)),
                        confidence=float(item.get("confidence", 0)),
                        source=DataSource.LANDMARK_DETECTION,
                        landmark_name=item.get("name", "Unknown Landmark"),
                        description=f"Landmark: {item.get('name', 'Unknown')}",
                    )
                    hypotheses.append(hypothesis)

            logger.info(
                "Landmark detection completed via Gemini", count=len(hypotheses)
            )
            return hypotheses

        except Exception as e:
            logger.error("Error in Gemini landmark detection", error=str(e))
            return []

    async def detect_text(self, image_path: str) -> List[str]:
        if not self.is_available():
            logger.warning("Gemini Vision API not available")
            return []

        try:
            loop = asyncio.get_event_loop()

            def run_inference():
                img = Image.open(image_path)
                prompt = (
                    "Extract all visible text from this image that could be useful for geolocation "
                    "(like street signs, store names, city names, advertisements). "
                    "Return ONLY a JSON array of strings. If no text is found, return []."
                )
                response = self.model.generate_content([prompt, img])
                return response.text

            text_response = await loop.run_in_executor(None, run_inference)

            # Clean up markdown
            text_response = text_response.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            text_response = text_response.strip()

            if not text_response or text_response == "[]":
                return []

            texts = json.loads(text_response)

            logger.info("Text detection completed via Gemini", count=len(texts))
            return texts

        except Exception as e:
            logger.error("Error in Gemini text detection", error=str(e))
            return []

    async def detect_objects(self, image_path: str) -> List[Dict[str, Any]]:
        # For geolocation, we only care about generic location types (towers, bridges, etc.)
        if not self.is_available():
            return []

        try:
            loop = asyncio.get_event_loop()

            def run_inference():
                img = Image.open(image_path)
                prompt = (
                    "Identify general types of location-indicating objects in this image "
                    "(e.g., 'Tower', 'Bridge', 'Church', 'Stadium', 'Mountain'). "
                    "Return ONLY a JSON array of strings representing the objects found. "
                    "If none, return []."
                )
                response = self.model.generate_content([prompt, img])
                return response.text

            text_response = await loop.run_in_executor(None, run_inference)

            text_response = text_response.strip()
            if text_response.startswith("```json"):
                text_response = text_response[7:]
            if text_response.startswith("```"):
                text_response = text_response[3:]
            if text_response.endswith("```"):
                text_response = text_response[:-3]
            text_response = text_response.strip()

            if not text_response or text_response == "[]":
                return []

            object_names = json.loads(text_response)
            objects = [{"name": obj_name, "score": 0.9} for obj_name in object_names]

            logger.info("Object detection completed via Gemini", count=len(objects))
            return objects

        except Exception as e:
            logger.error("Error in Gemini object detection", error=str(e))
            return []

    def get_service_info(self) -> Dict[str, Any]:
        return {
            "name": "Google Gemini Vision",
            "available": self.is_available(),
            "features": ["landmark_detection", "text_detection", "object_detection"],
        }
