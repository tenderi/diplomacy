"""
Response caching system for Diplomacy API endpoints.

This module provides comprehensive response caching for API endpoints to improve
performance and reduce database load for frequently accessed data.

Features:
- In-memory caching with TTL (Time To Live)
- Cache invalidation strategies
- Cache statistics and monitoring
- Configurable cache policies per endpoint
"""

import time
import hashlib
import json
import logging
from typing import Dict, Any, Optional, Callable, Union
from functools import wraps
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

class ResponseCache:
    """High-performance response cache with TTL and invalidation support."""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        """
        Initialize response cache.
        
        Args:
            default_ttl: Default time-to-live in seconds (5 minutes)
            max_size: Maximum number of cached responses
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, float] = {}
        self.hit_count = 0
        self.miss_count = 0
        self.lock = threading.RLock()
        
        logger.info(f"📦 Response cache initialized: TTL={default_ttl}s, MaxSize={max_size}")
    
    def _generate_key(self, endpoint: str, params: Dict[str, Any] = None) -> str:
        """Generate cache key from endpoint and parameters."""
        key_data = {
            "endpoint": endpoint,
            "params": params or {}
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, endpoint: str, params: Dict[str, Any] = None) -> Optional[Any]:
        """Get cached response if available and not expired."""
        with self.lock:
            key = self._generate_key(endpoint, params)
            
            if key not in self.cache:
                self.miss_count += 1
                return None
            
            cached_data = self.cache[key]
            current_time = time.time()
            
            # Check if expired
            if current_time > cached_data["expires_at"]:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                self.miss_count += 1
                return None
            
            # Update access time
            self.access_times[key] = current_time
            self.hit_count += 1
            
            logger.debug(f"✅ Cache hit for {endpoint}")
            return cached_data["data"]
    
    def put(self, endpoint: str, data: Any, ttl: Optional[int] = None, params: Dict[str, Any] = None) -> None:
        """Cache response data with TTL."""
        with self.lock:
            key = self._generate_key(endpoint, params)
            current_time = time.time()
            expires_at = current_time + (ttl or self.default_ttl)
            
            # Cleanup if cache is full
            if len(self.cache) >= self.max_size:
                self._cleanup_oldest()
            
            self.cache[key] = {
                "data": data,
                "expires_at": expires_at,
                "created_at": current_time,
                "endpoint": endpoint
            }
            self.access_times[key] = current_time
            
            logger.debug(f"💾 Cached response for {endpoint} (TTL: {ttl or self.default_ttl}s)")
    
    def invalidate(self, endpoint: str, params: Dict[str, Any] = None) -> None:
        """Invalidate cached response."""
        with self.lock:
            key = self._generate_key(endpoint, params)
            if key in self.cache:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
                logger.debug(f"🗑️  Invalidated cache for {endpoint}")
    
    def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all cached responses matching pattern."""
        with self.lock:
            keys_to_remove = []
            for key, cached_data in self.cache.items():
                if pattern in cached_data["endpoint"]:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            logger.debug(f"🗑️  Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")
    
    def clear(self) -> None:
        """Clear all cached responses."""
        with self.lock:
            self.cache.clear()
            self.access_times.clear()
            logger.info("🗑️  Response cache cleared")
    
    def _cleanup_oldest(self) -> None:
        """Remove oldest accessed items when cache is full."""
        if not self.access_times:
            return
        
        # Sort by access time (oldest first)
        sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])
        
        # Remove oldest 10% of items
        items_to_remove = max(1, len(sorted_items) // 10)
        for i in range(items_to_remove):
            key_to_remove = sorted_items[i][0]
            if key_to_remove in self.cache:
                del self.cache[key_to_remove]
            if key_to_remove in self.access_times:
                del self.access_times[key_to_remove]
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items."""
        with self.lock:
            current_time = time.time()
            expired_keys = []
            
            for key, cached_data in self.cache.items():
                if current_time > cached_data["expires_at"]:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                if key in self.access_times:
                    del self.access_times[key]
            
            if expired_keys:
                logger.debug(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hit_count + self.miss_count
            hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "cache_size": len(self.cache),
                "max_size": self.max_size,
                "hit_count": self.hit_count,
                "miss_count": self.miss_count,
                "hit_rate": round(hit_rate, 2),
                "total_requests": total_requests,
                "oldest_entry": min(self.access_times.values()) if self.access_times else None,
                "newest_entry": max(self.access_times.values()) if self.access_times else None
            }

# Global response cache instance
_response_cache = ResponseCache()

def cached_response(ttl: int = None, key_params: list = None, invalidate_on: list = None):
    """
    Decorator for caching API responses.
    
    Args:
        ttl: Time-to-live in seconds (uses default if None)
        key_params: List of parameter names to include in cache key
        invalidate_on: List of endpoints that should invalidate this cache
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract endpoint name from function
            endpoint = f"{func.__module__}.{func.__name__}"
            
            # Build cache key parameters
            cache_params = {}
            if key_params:
                for param_name in key_params:
                    if param_name in kwargs:
                        cache_params[param_name] = kwargs[param_name]
            
            # Try to get from cache
            cached_result = _response_cache.get(endpoint, cache_params)
            if cached_result is not None:
                return cached_result
            
            # Cache miss - execute function
            result = func(*args, **kwargs)
            
            # Cache the result
            _response_cache.put(endpoint, result, ttl, cache_params)
            
            return result
        
        return wrapper
    return decorator

def invalidate_cache(endpoint_pattern: str) -> None:
    """Invalidate cache entries matching pattern."""
    _response_cache.invalidate_pattern(endpoint_pattern)

def clear_response_cache() -> None:
    """Clear all cached responses."""
    _response_cache.clear()

def get_cache_stats() -> Dict[str, Any]:
    """Get response cache statistics."""
    return _response_cache.get_stats()

def cleanup_expired_cache() -> int:
    """Cleanup expired cache entries."""
    return _response_cache.cleanup_expired()

# Cache policies for different endpoint types
CACHE_POLICIES = {
    # Game state - cache for 30 seconds (frequently changing)
    "game_state": {"ttl": 30, "key_params": ["game_id"]},
    
    # Game list - cache for 2 minutes (changes less frequently)
    "game_list": {"ttl": 120, "key_params": []},
    
    # Player info - cache for 1 minute
    "player_info": {"ttl": 60, "key_params": ["game_id", "power"]},
    
    # Order history - cache for 5 minutes (rarely changes)
    "order_history": {"ttl": 300, "key_params": ["game_id"]},
    
    # Map cache stats - cache for 1 minute
    "map_cache_stats": {"ttl": 60, "key_params": []},
    
    # Connection pool status - cache for 30 seconds
    "pool_status": {"ttl": 30, "key_params": []},
}

# Auto-cleanup thread for expired entries
def _cleanup_thread():
    """Background thread to cleanup expired cache entries."""
    while True:
        try:
            time.sleep(60)  # Run every minute
            expired_count = cleanup_expired_cache()
            if expired_count > 0:
                logger.debug(f"🧹 Auto-cleanup removed {expired_count} expired cache entries")
        except Exception as e:
            logger.error(f"❌ Cache cleanup thread error: {e}")

# Start cleanup thread
cleanup_thread = threading.Thread(target=_cleanup_thread, daemon=True)
cleanup_thread.start()
logger.info("🧹 Response cache cleanup thread started")
