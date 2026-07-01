# backend/app/core/cache_decorators.py
from functools import wraps
from backend.app.core.cache import cache_manager

def cached(ttl: int = 3600, key_prefix: str = ""):
    """Decorator to cache asynchronous function results."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Parse arguments cleanly for unique key generation
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            cached_val = await cache_manager.get(cache_key)
            if cached_val is not None:
                return cached_val
                
            result = await func(*args, **kwargs)
            if result is not None:
                await cache_manager.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator
