from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.database import init_db
from app.api.endpoints import router
from app.utils.cache import cache_manager

settings = get_settings()

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Photo Geolocation Service", version=settings.version)

    await init_db()
    await cache_manager.connect()

    logger.info("Service started successfully")

    yield

    await cache_manager.disconnect()
    logger.info("Service shutdown completed")


app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description="""
    🌍 **Photo Geolocation Service** - AI-powered geolocation from photos

    This service determines geographic coordinates from photographs using:
    - **EXIF GPS Data** extraction
    - **AI Landmark Recognition** via Google Cloud Vision
    - **OCR + Geocoding** for text-based location hints  
    - **Multi-provider Geocoding** (Google Maps, LocationIQ, OpenCage, Nominatim)

    ## Features
    - Multiple processing modes (fast/standard/comprehensive)
    - Intelligent caching for performance
    - Batch processing support
    - Detailed metadata and confidence scores
    - RESTful API with OpenAPI documentation

    ## Quick Start
    1. Upload image via `/upload` endpoint
    2. Get location hypotheses with coordinates and confidence scores
    3. View interactive demo at `/demo`
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Роутер подключён один раз без префикса, чтобы /upload, /health, /demo работали напрямую
app.include_router(router)

try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except RuntimeError:
    pass


@app.get("/")
async def root():
    return RedirectResponse(url="/demo")


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info"
    )
