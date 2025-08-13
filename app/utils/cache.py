import time
import threading
from typing import Any, Optional, Tuple, Dict
from collections import OrderedDict

from ..settings import settings


class TTLCache:
    """Thread-safe LRU cache with TTL (Time To Live) support."""
    
    def __init__(self, max_size: int = 1000, default_ttl_seconds: int = None):
        """
        Initialize TTL cache.
        
        Args:
            max_size: Maximum number of items to store
            default_ttl_seconds: Default TTL in seconds (uses CACHE_TTL_MIN from settings if None)
        """
        self.max_size = max_size
        self.default_ttl_seconds = default_ttl_seconds or (settings.CACHE_TTL_MIN * 60)
        
        # Cache storage: key -> (value, expiry_time)
        self._cache: OrderedDict[str, Tuple[Any, float]] = OrderedDict()
        self._lock = threading.RLock()
    
    def _generate_key(self, retailer: str, query: str, postcode: str) -> str:
        """Generate cache key from retailer, query, and postcode."""
        # Normalize inputs for consistent caching
        normalized_query = query.lower().strip()
        normalized_postcode = postcode.strip()
        return f"{retailer}:{normalized_query}:{normalized_postcode}"
    
    def _is_expired(self, expiry_time: float) -> bool:
        """Check if an item has expired."""
        return time.time() > expiry_time
    
    def _evict_expired(self) -> None:
        """Remove expired items from cache (called with lock held)."""
        current_time = time.time()
        expired_keys = []
        
        for key, (_, expiry_time) in self._cache.items():
            if current_time > expiry_time:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
    
    def _enforce_size_limit(self) -> None:
        """Ensure cache doesn't exceed max_size (called with lock held)."""
        while len(self._cache) > self.max_size:
            # Remove least recently used item
            self._cache.popitem(last=False)
    
    def get(self, retailer: str, query: str, postcode: str) -> Optional[Any]:
        """
        Get item from cache.
        
        Args:
            retailer: Retailer name ("woolworths", "coles")
            query: Search query
            postcode: Australian postcode
            
        Returns:
            Cached value if found and not expired, None otherwise
        """
        key = self._generate_key(retailer, query, postcode)
        
        with self._lock:
            if key not in self._cache:
                return None
            
            value, expiry_time = self._cache[key]
            
            if self._is_expired(expiry_time):
                del self._cache[key]
                return None
            
            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            return value
    
    def put(self, retailer: str, query: str, postcode: str, value: Any, ttl_seconds: int = None) -> None:
        """
        Store item in cache.
        
        Args:
            retailer: Retailer name ("woolworths", "coles")
            query: Search query  
            postcode: Australian postcode
            value: Value to cache
            ttl_seconds: TTL in seconds (uses default if None)
        """
        key = self._generate_key(retailer, query, postcode)
        ttl = ttl_seconds or self.default_ttl_seconds
        expiry_time = time.time() + ttl
        
        with self._lock:
            # Clean up expired items periodically
            if len(self._cache) % 100 == 0:  # Every 100 operations
                self._evict_expired()
            
            # Store the item
            self._cache[key] = (value, expiry_time)
            
            # Move to end (mark as recently used)
            self._cache.move_to_end(key)
            
            # Enforce size limit
            self._enforce_size_limit()
    
    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()
    
    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            current_time = time.time()
            expired_count = 0
            
            for _, expiry_time in self._cache.values():
                if current_time > expiry_time:
                    expired_count += 1
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "expired_items": expired_count,
                "default_ttl_seconds": self.default_ttl_seconds
            }


# Global cache instance
_cache_instance = None
_cache_lock = threading.Lock()


def get_cache() -> TTLCache:
    """Get or create the global cache instance (thread-safe singleton)."""
    global _cache_instance
    
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = TTLCache()
    
    return _cache_instance


def clear_cache() -> None:
    """Clear the global cache (useful for testing)."""
    cache = get_cache()
    cache.clear()