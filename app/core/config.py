from functools import lru_cache
from typing import Optional, List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Photo Geolocation Service"
    version: str = "1.0.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    # По умолчанию SQLite для локальной разработки без PostgreSQL
    database_url: str = Field(
        default="sqlite+aiosqlite:///./geolocation.db",
        validation_alias="DATABASE_URL"
    )
    # Redis необязателен — используется in-memory кэш как fallback
    redis_url: Optional[str] = Field(default=None, validation_alias="REDIS_URL")

    google_cloud_credentials_path: Optional[str] = Field(
        default=None, validation_alias="GOOGLE_APPLICATION_CREDENTIALS"
    )
    google_maps_api_key: Optional[str] = Field(
        default=None, validation_alias="GOOGLE_MAPS_API_KEY"
    )

    locationiq_api_key: Optional[str] = Field(
        default=None, validation_alias="LOCATIONIQ_API_KEY"
    )
    opencage_api_key: Optional[str] = Field(
        default=None, validation_alias="OPENCAGE_API_KEY"
    )

    # Секретный ключ — может быть сгенерирован по умолчанию для dev
    secret_key: str = Field(
        default="dev-secret-key-change-in-production-32chars!",
        validation_alias="SECRET_KEY"
    )
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    max_file_size: int = 10 * 1024 * 1024
    allowed_extensions: List[str] = [".jpg", ".jpeg", ".png", ".webp", ".tiff"]
    upload_path: str = "uploads"

    cache_ttl: int = 3600

    landmark_confidence_threshold: float = 0.6
    geocoding_confidence_threshold: float = 0.7

    cors_origins: List[str] = ["*"]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        valid_prefixes = (
            "postgresql://",
            "postgresql+asyncpg://",
            "sqlite:///",
            "sqlite+aiosqlite://",
        )
        if not v.startswith(valid_prefixes):
            raise ValueError(
                f"Database URL must be PostgreSQL (postgresql+asyncpg://) or SQLite (sqlite+aiosqlite://). Got: {v}"
            )
        return v

    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()
