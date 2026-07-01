import redis.asyncio as redis
import json
import time
import datetime
import uuid
import os
from typing import Any, Optional
from backend.app.core.logging_config import log as logger
from backend.app.core.metrics import cache_hits_total, cache_misses_total

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return super().default(obj)

def parse_datetime_strings(val):
    if isinstance(val, dict):
        return {k: parse_datetime_strings(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [parse_datetime_strings(v) for v in val]
    elif isinstance(val, str):
        if len(val) >= 10 and val[4] == '-' and val[7] == '-':
            try:
                return datetime.datetime.fromisoformat(val)
            except ValueError:
                pass
    return val

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.fallback_cache = {}  # Format: {key: (expire_time, value)}
    
    async def connect(self):
        try:
            self.redis = await redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
            )
            await self.redis.ping()
            logger.info("Connected to Redis caching server successfully.")
        except Exception as e:
            logger.warning(f"Redis connection failed, using local memory fallback: {e}")
            self.redis = None
            
    async def disconnect(self):
        if self.redis:
            await self.redis.close()
            
    async def get(self, key: str) -> Optional[Any]:
        if self.redis:
            try:
                value = await self.redis.get(key)
                if value is not None:
                    cache_hits_total.labels(cache_type='redis').inc()
                    try:
                        return parse_datetime_strings(json.loads(value))
                    except json.JSONDecodeError:
                        return value
                cache_misses_total.labels(cache_type='redis').inc()
            except Exception as e:
                logger.error(f"Redis GET error for key '{key}': {e}")
                cache_misses_total.labels(cache_type='redis').inc()
        
        # Fallback to local memory cache with TTL validation
        if key in self.fallback_cache:
            expire_time, val = self.fallback_cache[key]
            if time.time() < expire_time:
                cache_hits_total.labels(cache_type='memory').inc()
                return val
            else:
                del self.fallback_cache[key]
                
        cache_misses_total.labels(cache_type='memory').inc()
        return None
        
    async def set(self, key: str, value: Any, ttl: int = 3600):
        serialized = json.dumps(value, cls=DateTimeEncoder) if not isinstance(value, str) else value
        
        if self.redis:
            try:
                await self.redis.setex(key, ttl, serialized)
                return
            except Exception as e:
                logger.error(f"Redis SET error for key '{key}': {e}")
                
        # Local memory cache write
        self.fallback_cache[key] = (time.time() + ttl, value)
        
    async def delete(self, key: str):
        if self.redis:
            try:
                await self.redis.delete(key)
                return
            except Exception as e:
                logger.error(f"Redis DELETE error for key '{key}': {e}")
                
        self.fallback_cache.pop(key, None)
        
    async def delete_pattern(self, pattern: str):
        """Perform scan and delete by match pattern (e.g. 'prefix:*')."""
        if self.redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern)
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
                return
            except Exception as e:
                logger.error(f"Redis SCAN/DELETE pattern '{pattern}' error: {e}")
                
        import fnmatch
        for key in list(self.fallback_cache.keys()):
            if fnmatch.fnmatch(key, pattern):
                self.fallback_cache.pop(key, None)

cache_manager = CacheManager(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

