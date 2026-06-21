from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class ProcessingMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    COMPREHENSIVE = "comprehensive"


class DataSource(str, Enum):
    EXIF_GPS = "exif_gps"
    LANDMARK_DETECTION = "landmark_detection"
    OCR_GEOCODING = "ocr_geocoding"
    REVERSE_GEOCODING = "reverse_geocoding"


class LocationHypothesis(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    confidence: float = Field(..., ge=0, le=1)
    source: DataSource
    description: Optional[str] = None
    address: Optional[str] = None
    landmark_name: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    admin_area: Optional[str] = None
    locality: Optional[str] = None
    postal_code: Optional[str] = None


class ProcessingMetadata(BaseModel):
    processing_time_ms: int
    apis_used: List[str]
    landmark_results_count: int = 0
    text_results_count: int = 0
    geocoding_queries_count: int = 0
    cache_hit: bool = False
    error_messages: List[str] = []


class ImageMetadata(BaseModel):
    filename: str
    size_bytes: int
    dimensions: Dict[str, int]
    format: str
    has_exif: bool
    has_gps: bool
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    datetime_taken: Optional[datetime] = None


class GeolocationRequest(BaseModel):
    mode: ProcessingMode = ProcessingMode.STANDARD
    min_confidence: float = Field(0.6, ge=0, le=1)
    max_results: int = Field(5, ge=1, le=20)
    include_metadata: bool = True
    include_address: bool = True


class GeolocationResponse(BaseModel):
    success: bool
    request_id: str
    hypotheses: List[LocationHypothesis]
    best_guess: Optional[LocationHypothesis] = None
    image_metadata: Optional[ImageMetadata] = None
    processing_metadata: Optional[ProcessingMetadata] = None
    error_message: Optional[str] = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HealthCheck(BaseModel):
    status: str
    timestamp: datetime
    version: str
    uptime_seconds: int
    services: Dict[str, str]


class ServiceStats(BaseModel):
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_processing_time_ms: float
    cache_hit_rate: float
    top_sources: List[Dict[str, Any]]
