# 🌍 Photo Geolocation Service

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7+-red.svg)
![Docker](https://img.shields.io/badge/Docker-ready-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

> 🚀 **AI-powered photo geolocation service** that determines geographic coordinates from images using advanced computer vision and multi-provider geocoding.

## ✨ Features

### 🎯 Core Capabilities
- **EXIF GPS Extraction** - Direct coordinate extraction from image metadata
- **AI Landmark Recognition** - Google Cloud Vision API integration  
- **OCR + Geocoding** - Text recognition with multi-provider geocoding
- **Intelligent Ranking** - Confidence-based result scoring and clustering
- **Batch Processing** - Multiple image processing support

### 🛠 Technical Features  
- **Production-Ready** - Async FastAPI with proper error handling
- **Multi-Provider Geocoding** - Google Maps, LocationIQ, OpenCage, Nominatim
- **Smart Caching** - Redis + in-memory caching for performance
- **Comprehensive Testing** - Unit and integration tests with pytest
- **Docker Ready** - Full containerization with Docker Compose
- **Monitoring** - Health checks, metrics, and structured logging

### 🌐 API & UI
- **RESTful API** - Complete OpenAPI documentation  
- **Interactive Demo** - Web interface with drag & drop
- **Batch Endpoints** - Process multiple images simultaneously
- **Real-time Results** - Interactive maps with confidence scores

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Usage](#-usage)
- [API Documentation](#-api-documentation)
- [Architecture](#-architecture)
- [Development](#-development)
- [Testing](#-testing)
- [Deployment](#-deployment)
- [Contributing](#-contributing)

## 🚀 Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone repository
git clone <repository-url>
cd photo-geolocation

# Setup environment
cp .env.example .env
# Edit .env with your API keys

# Start all services
make run
# Or: docker-compose up
```

### Option 2: Local Development

```bash
# Install dependencies
make install

# Setup environment  
make setup-dev

# Start development server
make dev
```

Visit **http://localhost:8000/demo** to access the interactive demo.

## 📦 Installation

### System Requirements

- **Python 3.11+**
- **Poetry** (package manager)
- **PostgreSQL 15+** (or SQLite for development)
- **Redis 7+** (optional, for caching)
- **Docker & Docker Compose** (for containerized deployment)

### Development Setup

```bash
# Install Poetry (if not installed)
curl -sSL https://install.python-poetry.org | python3 -

# Clone and setup project
git clone <repository-url>
cd photo-geolocation

# Run setup script
python scripts/setup.py

# Or manual setup:
poetry install
cp .env.example .env
# Edit .env with your API keys
```

### Dependencies

The project uses modern Python stack:

- **FastAPI** - Async web framework
- **SQLAlchemy 2.0** - ORM with async support  
- **Pydantic V2** - Data validation and serialization
- **Google Cloud Vision** - Landmark detection and OCR
- **Multiple Geocoding APIs** - Geographic coordinate resolution
- **Redis** - Caching and session storage
- **Pytest** - Testing framework with async support

## ⚙️ Configuration

### Environment Variables

Create `.env` file from template:

```bash
cp .env.example .env
```

Required configuration:

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/geolocation

# Redis (optional but recommended)
REDIS_URL=redis://localhost:6379

# Security
SECRET_KEY=your-super-secret-key-here

# Google Cloud Vision API
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account-key.json

# Google Maps API (recommended)
GOOGLE_MAPS_API_KEY=your-google-maps-api-key

# Alternative geocoding services (optional)
LOCATIONIQ_API_KEY=your-locationiq-key
OPENCAGE_API_KEY=your-opencage-key
```

### API Keys Setup

#### 🔐 Google Cloud Vision API
1. Create [Google Cloud Project](https://console.cloud.google.com/)
2. Enable Cloud Vision API
3. Create Service Account
4. Download JSON credentials file
5. Set `GOOGLE_APPLICATION_CREDENTIALS` path

#### 🗺️ Google Maps API  
1. Enable Geocoding API in Google Cloud Console
2. Create API key with appropriate restrictions
3. Set `GOOGLE_MAPS_API_KEY`

#### 🌍 Alternative Geocoding APIs
- **LocationIQ**: 5,000 requests/day free tier
- **OpenCage**: 2,500 requests/day free tier  
- **Nominatim**: Unlimited (OpenStreetMap)

## 💻 Usage

### Web Interface

1. **Navigate** to http://localhost:8000/demo
2. **Upload Image** - Drag & drop or click to select
3. **Choose Processing Mode**:
   - `fast` - Landmark detection only (~500ms)
   - `standard` - Landmarks + OCR (~1-2s)  
   - `comprehensive` - All methods (~2-3s)
4. **View Results** - Interactive map with confidence scores

### API Usage

#### Upload Single Image

```python
import requests

with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/upload',
        files={'file': f},
        data={
            'mode': 'standard',
            'min_confidence': 0.6,
            'max_results': 5
        }
    )

result = response.json()
print(f"Best guess: {result['best_guess']}")
```

#### Batch Processing

```python
files = [
    ('files', ('image1.jpg', open('image1.jpg', 'rb'), 'image/jpeg')),
    ('files', ('image2.jpg', open('image2.jpg', 'rb'), 'image/jpeg'))
]

response = requests.post(
    'http://localhost:8000/batch-upload',
    files=files,
    data={'mode': 'standard'}
)

results = response.json()
```

#### cURL Examples

```bash
# Single upload
curl -X POST http://localhost:8000/upload \
  -F "file=@photo.jpg" \
  -F "mode=standard" \
  -F "min_confidence=0.7"

# Health check
curl http://localhost:8000/health

# Service statistics  
curl http://localhost:8000/stats
```

## 📚 API Documentation

### Core Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Redirect to demo interface |
| `GET` | `/demo` | Interactive web interface |
| `POST` | `/upload` | Single image geolocation |
| `POST` | `/batch-upload` | Multiple image processing |
| `GET` | `/health` | Service health status |
| `GET` | `/stats` | Processing statistics |
| `GET` | `/docs` | OpenAPI documentation |
| `GET` | `/redoc` | ReDoc documentation |

### Response Format

```json
{
  "success": true,
  "request_id": "uuid-string",
  "hypotheses": [
    {
      "latitude": 40.7829,
      "longitude": -73.9654,
      "confidence": 0.95,
      "source": "landmark_detection",
      "description": "Central Park, New York",
      "address": "Central Park, New York, NY 10024, USA",
      "landmark_name": "Central Park",
      "country": "United States",
      "country_code": "US"
    }
  ],
  "best_guess": { /* same structure */ },
  "processing_metadata": {
    "processing_time_ms": 1247,
    "apis_used": ["google_vision_landmark", "geocoding_services"],
    "cache_hit": false
  }
}
```

### Processing Modes

- **`fast`** - Landmark detection only (fastest, ~500ms)
- **`standard`** - Landmarks + OCR + geocoding (balanced, ~1-2s)
- **`comprehensive`** - All methods including object detection (~2-3s)

### Data Sources

Results are ranked by reliability:

1. **`exif_gps`** - GPS coordinates from image metadata (100% confidence)
2. **`landmark_detection`** - Google Vision landmark recognition (90% weight)  
3. **`ocr_geocoding`** - Text extraction + geocoding (70% weight)
4. **`reverse_geocoding`** - Coordinate to address conversion (80% weight)

## 🏗️ Architecture

### System Overview

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Web UI    │◄──►│  FastAPI     │◄──►│ External    │
│   Demo      │    │  Application │    │ APIs        │
└─────────────┘    │              │    │             │
                   │ ┌──────────┐ │    │ • Vision    │
┌─────────────┐    │ │ Geoloc.  │ │    │ • Geocoding │
│  PostgreSQL │◄──►│ │ Service  │ │    │ • Maps      │
│  Database   │    │ └──────────┘ │    └─────────────┘
└─────────────┘    │              │          
                   │ ┌──────────┐ │    ┌─────────────┐
┌─────────────┐    │ │ Vision   │ │    │    Redis    │
│   File      │◄──►│ │ Service  │ │◄──►│   Cache     │
│   Storage   │    │ └──────────┘ │    └─────────────┘
└─────────────┘    └──────────────┘          
```

### Component Description

- **FastAPI Application** - Async web server with OpenAPI docs
- **Geolocation Service** - Main processing logic and orchestration
- **Vision Service** - Google Cloud Vision API integration  
- **Geocoding Service** - Multi-provider geocoding with fallbacks
- **Caching Layer** - Redis + in-memory for performance
- **Database Layer** - SQLAlchemy with async PostgreSQL
- **Image Processing** - PIL-based image validation and EXIF extraction

### Processing Pipeline

```mermaid
graph TD
    A[Upload Image] --> B[Validate & Extract Metadata]
    B --> C{EXIF GPS?}
    C -->|Yes| D[High Confidence Result]
    C -->|No| E[Landmark Detection]
    E --> F[OCR Text Extraction]  
    F --> G[Multi-Provider Geocoding]
    G --> H[Result Ranking & Filtering]
    H --> I[Address Enhancement]
    I --> J[Cache & Return Results]
```

## 🧪 Testing

### Run Tests

```bash
# All tests with coverage
make test

# Unit tests only
poetry run pytest tests/unit/ -v

# Integration tests only  
poetry run pytest tests/integration/ -v

# Specific test file
poetry run pytest tests/unit/test_image_processing.py -v
```

### Test Structure

```
tests/
├── conftest.py              # Test configuration
├── unit/                    # Unit tests
│   ├── test_image_processing.py
│   ├── test_geo_utils.py
│   └── test_cache.py
└── integration/             # Integration tests
    ├── test_api.py
    ├── test_services.py
    └── test_database.py
```

### Test Coverage

The test suite covers:

- **Image Processing** - EXIF extraction, validation, metadata
- **Geocoding Services** - All provider integrations
- **API Endpoints** - Request/response validation  
- **Caching** - Redis and memory cache functionality
- **Database** - Model creation and queries
- **Error Handling** - Various failure scenarios

## 🐳 Deployment

### Docker Deployment

#### Development
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f app

# Stop services
docker-compose down
```

#### Production

```bash
# Use production override
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# With SSL/HTTPS
docker-compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
```

### Manual Deployment

#### Prerequisites
```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install python3.11 python3.11-pip postgresql redis-server nginx

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

#### Application Setup
```bash
# Clone and setup
git clone <repository-url>
cd photo-geolocation

# Install dependencies
poetry install --only=main

# Setup database
createdb geolocation
poetry run alembic upgrade head

# Configure systemd service
sudo cp deploy/photo-geolocation.service /etc/systemd/system/
sudo systemctl enable photo-geolocation
sudo systemctl start photo-geolocation
```

#### Nginx Configuration
```nginx
server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Environment-Specific Configurations

#### Development
- SQLite database for simplicity
- Debug logging enabled
- Hot reloading with uvicorn
- No authentication required

#### Production  
- PostgreSQL with connection pooling
- Redis caching enabled
- Structured JSON logging
- Rate limiting and authentication
- SSL/TLS termination
- Health checks and monitoring

## 🛠️ Development

### Project Structure

```
photo-geolocation/
├── app/                     # Main application
│   ├── main.py             # FastAPI application
│   ├── core/               # Core configuration  
│   │   ├── config.py       # Settings management
│   │   └── database.py     # Database configuration
│   ├── models/             # Data models
│   │   ├── schemas.py      # Pydantic models
│   │   └── database.py     # SQLAlchemy models  
│   ├── services/           # Business logic
│   │   ├── geolocation_service.py
│   │   ├── vision_service.py
│   │   └── geocoding_service.py
│   ├── api/                # API routes
│   │   └── endpoints.py
│   └── utils/              # Utilities
│       ├── image_processing.py
│       ├── cache.py
│       └── geo_utils.py
├── tests/                  # Test suite
├── docker/                 # Docker configuration
├── scripts/                # Utility scripts
└── docs/                   # Documentation
```

### Adding New Features

#### New Geocoding Provider
1. Create new method in `GeocodingService`
2. Add API key to configuration  
3. Update `_geocode_text_list` method
4. Add tests for new provider

#### New Processing Mode
1. Extend `ProcessingMode` enum
2. Update processing logic in `GeolocationService`
3. Modify API endpoints to support new mode
4. Add comprehensive tests

#### New Data Source
1. Extend `DataSource` enum  
2. Implement extraction logic
3. Update ranking weights
4. Add confidence calculation

### Code Style

The project follows strict Python standards:

- **Black** - Code formatting
- **isort** - Import sorting  
- **Flake8** - Linting
- **MyPy** - Type checking
- **Pre-commit** - Git hooks

```bash
# Format code
make format

# Run linting  
make lint

# Type checking
poetry run mypy app/
```

### Database Migrations

```bash  
# Create migration
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Downgrade  
poetry run alembic downgrade -1
```

## 📊 Monitoring

### Health Checks

```bash
# Service health
curl http://localhost:8000/health

# Detailed statistics
curl http://localhost:8000/stats

# Cache performance
curl http://localhost:8000/cache/stats
```

### Metrics

The service provides comprehensive metrics:

- **Request Statistics** - Total, success, failure counts
- **Processing Times** - Average, percentiles by mode
- **Cache Performance** - Hit rates, memory usage
- **API Usage** - Calls per provider, rate limits
- **Error Tracking** - Error rates by type and source

### Logging

Structured logging with correlation IDs:

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "info", 
  "logger": "app.services.geolocation",
  "request_id": "abc-123",
  "message": "Processing completed",
  "processing_time_ms": 1247,
  "hypotheses_count": 3
}
```

## 🤝 Contributing

We welcome contributions! Please follow these guidelines:

### Development Workflow

1. **Fork** the repository
2. **Create** feature branch (`git checkout -b feature/amazing-feature`)
3. **Write** tests for new functionality
4. **Ensure** all tests pass (`make test`)  
5. **Format** code (`make format`)
6. **Commit** changes (`git commit -m 'Add amazing feature'`)
7. **Push** to branch (`git push origin feature/amazing-feature`)
8. **Open** Pull Request

### Code Standards

- Write comprehensive tests for all new features
- Follow existing code style and patterns
- Add docstrings for public methods
- Update documentation for API changes
- Ensure type hints are complete

### Reporting Issues

When reporting bugs, please include:

- Python version and environment
- Complete error traceback  
- Steps to reproduce
- Expected vs actual behavior
- Sample images (if applicable)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Google Cloud Vision API** - Advanced computer vision capabilities
- **FastAPI** - Modern Python web framework  
- **OpenStreetMap** - Open mapping data via Nominatim
- **All geocoding providers** - LocationIQ, OpenCage, Google Maps
- **Open source community** - Libraries and tools that make this possible

## 📞 Support

- 🐛 **Issues**: Open an issue in the repository
- 📖 **Documentation**: See `/docs` endpoint after starting the server

---

**Made with ❤️ for the geolocation community**

*Empowering developers to build location-aware applications with AI-powered photo analysis.*
