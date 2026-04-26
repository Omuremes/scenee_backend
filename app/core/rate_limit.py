import hashlib

from fastapi import HTTPException, Request, status

from app.core.cache import redis_client


def get_client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    scope: str,
    identifier: str,
    limit: int,
    window_seconds: int,
) -> None:
    normalized_identifier = identifier.strip().lower()
    key_hash = hashlib.sha256(normalized_identifier.encode("utf-8")).hexdigest()
    cache_key = f"rate_limit:{scope}:{key_hash}"

    try:
        attempt_count = await redis_client.incr(cache_key)
        if attempt_count == 1:
            await redis_client.expire(cache_key, window_seconds)
        retry_after = await redis_client.ttl(cache_key)
    except Exception:
        return

    if attempt_count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
