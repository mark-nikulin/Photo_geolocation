import json
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import Any, Optional, Dict
import redis.asyncio as redis
import structlog

from app.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class CacheManager:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = settings.cache_ttl

    async def connect(self) -> None:
        try:
            if not settings.redis_url:
                logger.info("Redis URL not configured, using in-memory cache")
                return
            self.redis_client = redis.from_url(settings.redis_url)
            await self.redis_client.ping()
            logger.info("Redis connected successfully")
        except Exception as e:
            logger.warning("Redis connection failed, using memory cache", error=str(e))
            self.redis_client = None

    async def disconnect(self) -> None:
        if self.redis_client:
            await self.redis_client.close()

    def generate_key(self, data: Any, prefix: str = "geo") -> str:
        if isinstance(data, str):
            content = data
        elif isinstance(data, dict):
            content = json.dumps(data, sort_keys=True)
        else:
            content = str(data)

        hash_obj = hashlib.sha256(content.encode())
        return f"{prefix}:{hash_obj.hexdigest()[:16]}"

    async def get(self, key: str) -> Optional[Any]:
        try:
            if self.redis_client:
                data = await self.redis_client.get(key)
                if data:
                    return pickle.loads(data)

            cached_item = self.memory_cache.get(key)
            if cached_item:
                if datetime.now() < cached_item["expires_at"]:
                    return cached_item["value"]
                else:
                    del self.memory_cache[key]

            return None
        except Exception as e:
            logger.error("Cache get error", error=str(e), key=key)
            return None

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        try:
            ttl = ttl or self.ttl

            if self.redis_client:
                serialized = pickle.dumps(value)
                await self.redis_client.setex(key, ttl, serialized)

            self.memory_cache[key] = {
                "value": value,
                "expires_at": datetime.now() + timedelta(seconds=ttl)
            }

            return True
        except Exception as e:
            logger.error("Cache set error", error=str(e), key=key)
            return False

    async def delete(self, key: str) -> bool:
        try:
            if self.redis_client:
                await self.redis_client.delete(key)

            if key in self.memory_cache:
                del self.memory_cache[key]

            return True
        except Exception as e:
            logger.error("Cache delete error", error=str(e), key=key)
            return False

    async def clear(self) -> bool:
        try:
            if self.redis_client:
                await self.redis_client.flushall()

            self.memory_cache.clear()
            return True
        except Exception as e:
            logger.error("Cache clear error", error=str(e))
            return False

    async def get_stats(self) -> Dict[str, Any]:
        stats = {
            "memory_cache_size": len(self.memory_cache),
            "redis_connected": self.redis_client is not None
        }

        if self.redis_client:
            try:
                info = await self.redis_client.info()
                stats["redis_memory"] = info.get("used_memory_human", "Unknown")
                stats["redis_keys"] = await self.redis_client.dbsize()
            except Exception:
                stats["redis_error"] = "Failed to get Redis info"

        return stats


cache_manager = CacheManager()
