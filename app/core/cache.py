import json
from typing import Any, Optional
import redis
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def set_json(key: str, value: Any, ttl_seconds: int = 300) -> None:
    try:
        get_redis().setex(key, ttl_seconds, json.dumps(value))
    except Exception as e:
        logger.warning(f"Redis set failed for key={key}: {e}")


def get_json(key: str) -> Optional[Any]:
    try:
        raw = get_redis().get(key)
        return json.loads(raw) if raw else None
    except Exception as e:
        logger.warning(f"Redis get failed for key={key}: {e}")
        return None


def delete(key: str) -> None:
    try:
        get_redis().delete(key)
    except Exception as e:
        logger.warning(f"Redis delete failed for key={key}: {e}")


def ping() -> bool:
    try:
        return get_redis().ping()
    except Exception:
        return False
