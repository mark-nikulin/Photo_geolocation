import uuid
from pathlib import Path
from typing import List, Dict, Any
import time

import aiofiles
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.schemas import (
    GeolocationRequest,
    GeolocationResponse,
    HealthCheck,
    ProcessingMode,
    ServiceStats,
)
from app.services.geolocation_service import GeolocationService
from app.utils.cache import cache_manager

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter()
geolocation_service = GeolocationService()

# Время старта сервера (вынесено на уровень модуля, не хранится как атрибут функции)
_server_start_time = time.time()


@router.post("/upload", response_model=GeolocationResponse)
async def upload_image(
    file: UploadFile = File(...),
    mode: ProcessingMode = ProcessingMode.STANDARD,
    min_confidence: float = 0.6,
    max_results: int = 5,
    include_metadata: bool = True,
    include_address: bool = True,
    db: AsyncSession = Depends(get_db),
) -> GeolocationResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    file_extension = Path(file.filename).suffix.lower()
    if file_extension not in settings.allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File extension {file_extension} not allowed. Allowed: {settings.allowed_extensions}",
        )

    content = await file.read()
    if len(content) > settings.max_file_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {settings.max_file_size} bytes",
        )

    upload_dir = Path(settings.upload_path)
    upload_dir.mkdir(exist_ok=True)

    file_id = str(uuid.uuid4())
    file_path = upload_dir / f"{file_id}_{file.filename}"

    try:
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)

        request = GeolocationRequest(
            mode=mode,
            min_confidence=min_confidence,
            max_results=max_results,
            include_metadata=include_metadata,
            include_address=include_address,
        )

        response = await geolocation_service.process_image(file_path, request)

        return response

    except Exception as e:
        logger.error("Error processing upload", error=str(e))
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

    finally:
        if file_path.exists():
            file_path.unlink()


@router.post("/batch-upload", response_model=List[GeolocationResponse])
async def batch_upload(
    files: List[UploadFile] = File(...),
    mode: ProcessingMode = ProcessingMode.STANDARD,
    min_confidence: float = 0.6,
    max_results: int = 5,
    db: AsyncSession = Depends(get_db),
) -> List[GeolocationResponse]:
    if len(files) > 10:
        raise HTTPException(
            status_code=400, detail="Too many files. Maximum 10 files allowed"
        )

    results = []

    for file in files:
        try:
            if not file.filename:
                continue

            file_extension = Path(file.filename).suffix.lower()
            if file_extension not in settings.allowed_extensions:
                continue

            content = await file.read()
            if len(content) > settings.max_file_size:
                continue

            upload_dir = Path(settings.upload_path)
            upload_dir.mkdir(exist_ok=True)

            file_id = str(uuid.uuid4())
            file_path = upload_dir / f"{file_id}_{file.filename}"

            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            request = GeolocationRequest(
                mode=mode,
                min_confidence=min_confidence,
                max_results=max_results,
                include_metadata=True,
                include_address=True,
            )

            response = await geolocation_service.process_image(file_path, request)
            results.append(response)

            if file_path.exists():
                file_path.unlink()

        except Exception as e:
            logger.error(
                "Error processing batch file", error=str(e), filename=file.filename
            )
            continue

    return results


@router.get("/health", response_model=HealthCheck)
async def health_check() -> HealthCheck:
    from datetime import datetime, timezone

    uptime = int(time.time() - _server_start_time)

    services = {
        "vision_api": (
            "available"
            if geolocation_service.vision_service.is_available()
            else "unavailable"
        ),
        "cache": "available",
        "geocoding": "available",
    }

    status = (
        "healthy" if all(s == "available" for s in services.values()) else "degraded"
    )

    return HealthCheck(
        status=status,
        timestamp=datetime.now(timezone.utc),
        version=settings.version,
        uptime_seconds=uptime,
        services=services,
    )


@router.get("/stats", response_model=ServiceStats)
async def get_stats() -> ServiceStats:
    stats = geolocation_service.get_stats()
    cache_stats = await cache_manager.get_stats()
    hits = cache_stats.get("hits", 0)
    misses = cache_stats.get("misses", 0)
    total_cache = hits + misses
    hit_rate = hits / total_cache if total_cache > 0 else 0.0

    return ServiceStats(
        total_requests=stats["total_requests"],
        successful_requests=stats["successful_requests"],
        failed_requests=stats["failed_requests"],
        average_processing_time_ms=stats["average_processing_time_ms"],
        cache_hit_rate=hit_rate,
        top_sources=[
            {"name": "EXIF GPS", "count": 0},
            {"name": "Landmark Detection", "count": 0},
            {"name": "OCR + Geocoding", "count": 0},
        ],
    )


@router.get("/cache/stats")
async def cache_stats() -> Dict[str, Any]:
    return await cache_manager.get_stats()


@router.delete("/cache")
async def clear_cache() -> Dict[str, Any]:
    success = await cache_manager.clear()
    return {
        "success": success,
        "message": "Cache cleared" if success else "Failed to clear cache",
    }


@router.get("/demo")
async def demo_page() -> HTMLResponse:
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Photo Geolocation Demo</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    </head>
    <body>
        <div class="container mt-4">
            <h1 class="text-center mb-4">📍 Photo Geolocation Service</h1>

            <div class="row">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Upload Photo</h5>
                        </div>
                        <div class="card-body">
                            <form id="uploadForm" enctype="multipart/form-data">
                                <div class="mb-3">
                                    <input type="file" class="form-control" id="photoFile" accept="image/*" required>
                                </div>
                                <div class="mb-3">
                                    <select class="form-select" id="processingMode">
                                        <option value="fast">Fast (Landmarks only)</option>
                                        <option value="standard" selected>Standard (Landmarks + OCR)</option>
                                        <option value="comprehensive">Comprehensive (All methods)</option>
                                    </select>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">
                                    📍 Find Location
                                </button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-md-6">
                    <div class="card">
                        <div class="card-header">
                            <h5>Results</h5>
                        </div>
                        <div class="card-body">
                            <div id="results">
                                <p class="text-muted">Upload a photo to see results</p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div class="row mt-4">
                <div class="col-12">
                    <div class="card">
                        <div class="card-header">
                            <h5>📍 Map</h5>
                        </div>
                        <div class="card-body">
                            <div id="map" style="height: 400px;"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            let map = L.map('map').setView([40.7128, -74.0060], 2);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);

            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();

                const fileInput = document.getElementById('photoFile');
                const modeSelect = document.getElementById('processingMode');
                const resultsDiv = document.getElementById('results');

                if (!fileInput.files[0]) {
                    alert('Please select a file');
                    return;
                }

                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                formData.append('mode', modeSelect.value);

                resultsDiv.innerHTML = '<div class="spinner-border" role="status"></div> Processing...';

                try {
                    const response = await fetch('/upload', {
                        method: 'POST',
                        body: formData
                    });

                    const result = await response.json();

                    if (result.success && result.hypotheses.length > 0) {
                        let html = '<h6>Location Hypotheses:</h6>';

                        map.eachLayer(layer => {
                            if (layer instanceof L.Marker) {
                                map.removeLayer(layer);
                            }
                        });

                        result.hypotheses.forEach((hyp, idx) => {
                            html += `
                                <div class="border-start border-3 border-primary ps-2 mb-2">
                                    <strong>${hyp.landmark_name || 'Location ' + (idx + 1)}</strong><br>
                                    <small class="text-muted">${hyp.latitude.toFixed(6)}, ${hyp.longitude.toFixed(6)}</small><br>
                                    <small>Confidence: ${(hyp.confidence * 100).toFixed(1)}%</small><br>
                                    <small>Source: ${hyp.source.replace('_', ' ')}</small>
                                </div>
                            `;

                            L.marker([hyp.latitude, hyp.longitude])
                                .addTo(map)
                                .bindPopup(`
                                    <b>${hyp.landmark_name || 'Location'}</b><br>
                                    ${hyp.description || ''}<br>
                                    Confidence: ${(hyp.confidence * 100).toFixed(1)}%
                                `);
                        });

                        if (result.best_guess) {
                            map.setView([result.best_guess.latitude, result.best_guess.longitude], 10);
                        }

                        resultsDiv.innerHTML = html;
                    } else {
                        resultsDiv.innerHTML = '<div class="alert alert-warning">No location found in this image.</div>';
                    }
                } catch (error) {
                    resultsDiv.innerHTML = '<div class="alert alert-danger">Error processing image.</div>';
                }
            });
        </script>
    </body>
    </html>
    """

    return HTMLResponse(content=html_content)
