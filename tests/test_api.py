from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.models.schemas import DataSource, LocationHypothesis


class TestAPIEndpoints:

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "services" in data

    @pytest.mark.asyncio
    async def test_stats_endpoint(self, client: AsyncClient):
        response = await client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_requests" in data
        assert "successful_requests" in data
        assert "failed_requests" in data

    @pytest.mark.asyncio
    async def test_cache_stats_endpoint(self, client: AsyncClient):
        response = await client.get("/cache/stats")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_demo_endpoint(self, client: AsyncClient):
        response = await client.get("/demo")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    @pytest.mark.asyncio
    async def test_upload_no_file(self, client: AsyncClient):
        response = await client.post("/upload")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self, client: AsyncClient):
        files = {"file": ("test.txt", b"not an image", "text/plain")}
        response = await client.post("/upload", files=files)
        assert response.status_code == 400
        assert "not allowed" in response.json()["detail"]

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.GeolocationService.process_image")
    async def test_upload_valid_image(self, mock_process, client: AsyncClient):
        from datetime import datetime, timezone

        from app.models.schemas import GeolocationResponse

        mock_hypothesis = LocationHypothesis(
            latitude=40.7128,
            longitude=-74.0060,
            confidence=0.9,
            source=DataSource.LANDMARK_DETECTION,
            description="Test landmark",
        )

        mock_response = GeolocationResponse(
            success=True,
            request_id="test-123",
            hypotheses=[mock_hypothesis],
            best_guess=mock_hypothesis,
            processed_at=datetime.now(timezone.utc),
        )

        mock_process.return_value = mock_response

        files = {"file": ("test.jpg", b"fake image data", "image/jpeg")}
        response = await client.post("/upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["hypotheses"]) == 1
        assert data["hypotheses"][0]["latitude"] == 40.7128

    @pytest.mark.asyncio
    async def test_upload_large_file(self, client: AsyncClient):
        large_data = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {"file": ("large.jpg", large_data, "image/jpeg")}

        response = await client.post("/upload", files=files)
        assert response.status_code == 400
        assert "too large" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    @patch("app.services.geolocation_service.GeolocationService.process_image")
    async def test_batch_upload(self, mock_process, client: AsyncClient):
        from datetime import datetime, timezone

        from app.models.schemas import GeolocationResponse

        mock_hypothesis = LocationHypothesis(
            latitude=40.7128,
            longitude=-74.0060,
            confidence=0.9,
            source=DataSource.LANDMARK_DETECTION,
            description="Test landmark",
        )

        mock_response = GeolocationResponse(
            success=True,
            request_id="test-123",
            hypotheses=[mock_hypothesis],
            best_guess=mock_hypothesis,
            processed_at=datetime.now(timezone.utc),
        )

        mock_process.return_value = mock_response

        files = [
            ("files", ("test1.jpg", b"fake image data 1", "image/jpeg")),
            ("files", ("test2.jpg", b"fake image data 2", "image/jpeg")),
        ]

        response = await client.post("/batch-upload", files=files)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_clear_cache(self, client: AsyncClient):
        response = await client.delete("/cache")
        assert response.status_code == 200

        data = response.json()
        assert "success" in data
        assert "message" in data
