import logging

import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_cache(key: str) -> str | None:
    try:
        return await redis_client.get(key)
    except Exception as exc:
        logger.warning("Redis get failed for key %s: %s", key, exc)
        return None


async def set_cache(key: str, value: str, expire: int = 3600) -> bool:
    try:
        return bool(await redis_client.setex(key, expire, value))
    except Exception as exc:
        logger.warning("Redis set failed for key %s: %s", key, exc)
        return False


async def delete_cache(key: str) -> int:
    try:
        return await redis_client.delete(key)
    except Exception as exc:
        logger.warning("Redis delete failed for key %s: %s", key, exc)
        return 0


async def delete_cache_by_prefix(prefix: str) -> int:
    try:
        keys = [key async for key in redis_client.scan_iter(match=f"{prefix}*")]
        if not keys:
            return 0
        return await redis_client.delete(*keys)
    except Exception as exc:
        logger.warning("Redis prefix delete failed for prefix %s: %s", prefix, exc)
        return 0


async def exists_cache(key: str) -> bool:
    try:
        return bool(await redis_client.exists(key))
    except Exception as exc:
        logger.warning("Redis exists failed for key %s: %s", key, exc)
        return False
