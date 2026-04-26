import redis.asyncio as redis
from app.core.config import settings

# Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)


async def get_cache(key: str) -> str:
    """Получить значение из кэша"""
    return await redis_client.get(key)


async def set_cache(key: str, value: str, expire: int = 3600) -> bool:
    """Установить значение в кэш с временем жизни"""
    return await redis_client.setex(key, expire, value)


async def delete_cache(key: str) -> int:
    """Удалить значение из кэша"""
    return await redis_client.delete(key)


async def exists_cache(key: str) -> bool:
    """Проверить существование ключа в кэше"""
    return await redis_client.exists(key)