import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Import TTL manager for asset-specific TTL configuration
try:
    from .quote_ttl_manager import get_ttl_manager
    _has_ttl_manager = True
except ImportError:
    logger.warning("QuoteTTLManager not available, using default TTL")
    _has_ttl_manager = False

class MemoryCache:
    """High-performance in-memory cache with TTL support for frequently accessed data."""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl: Dict[str, float] = {}
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        with self._lock:
            if key in self._cache:
                expires_at = self._ttl.get(key, 0)
                if time.time() < expires_at:
                    self._hits += 1
                    # Update access time for LRU
                    self._cache[key]['accessed_at'] = time.time()
                    return self._cache[key]['value']
                else:
                    # Expired, remove it
                    self._remove_key(key)
            
            self._misses += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL."""
        with self._lock:
            # Remove oldest items if cache is full
            if len(self._cache) >= self.max_size:
                self._evict_lru()
            
            ttl_seconds = ttl if ttl is not None else self.default_ttl
            expires_at = time.time() + ttl_seconds
            
            self._cache[key] = {
                'value': value,
                'created_at': time.time(),
                'accessed_at': time.time()
            }
            self._ttl[key] = expires_at
    
    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            return self._remove_key(key)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._ttl.clear()
            self._hits = 0
            self._misses = 0
    
    def _remove_key(self, key: str) -> bool:
        """Remove key from cache dictionaries."""
        removed = False
        if key in self._cache:
            del self._cache[key]
            removed = True
        if key in self._ttl:
            del self._ttl[key]
            removed = True
        return removed
    
    def _evict_lru(self) -> None:
        """Evict least recently used items."""
        if not self._cache:
            return
        
        # Sort by access time and remove oldest 10% of items
        items_by_access = sorted(
            self._cache.items(), 
            key=lambda x: x[1]['accessed_at']
        )
        
        evict_count = max(1, len(items_by_access) // 10)
        for key, _ in items_by_access[:evict_count]:
            self._remove_key(key)
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed items."""
        with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, expires_at in self._ttl.items() 
                if current_time >= expires_at
            ]
            
            for key in expired_keys:
                self._remove_key(key)
            
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': round(hit_rate, 2),
                'default_ttl': self.default_ttl
            }
    
    def get_keys(self) -> list:
        """Get all cache keys."""
        with self._lock:
            return list(self._cache.keys())
    
    def set_many(self, items: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """Set multiple items in cache."""
        with self._lock:
            for key, value in items.items():
                self.set(key, value, ttl)
    
    def get_many(self, keys: list) -> Dict[str, Any]:
        """Get multiple items from cache."""
        result = {}
        for key in keys:
            value = self.get(key)
            if value is not None:
                result[key] = value
        return result

class QuoteCache(MemoryCache):
    """Specialized cache for quote data with asset-specific TTL."""
    
    def __init__(self, default_ttl: int = 300, max_size: int = 500):
        super().__init__(default_ttl=default_ttl, max_size=max_size)
        # Initialize TTL manager if available
        self._ttl_manager = get_ttl_manager() if _has_ttl_manager else None
    
    def get_quote(self, symbol: str, asset_type: str) -> Optional[Dict]:
        """Get quote for specific symbol and asset type."""
        key = f"quote:{symbol}:{asset_type}"
        return self.get(key)
    
    def set_quote(self, symbol: str, asset_type: str, quote_data: Dict, ttl: Optional[int] = None) -> None:
        """
        Set quote for specific symbol and asset type with asset-specific TTL.
        
        Args:
            symbol: Asset symbol
            asset_type: Asset type (FUND, STOCK, INDEX, GOLD, etc.)
            quote_data: Quote data dictionary
            ttl: Optional custom TTL (overrides asset-specific TTL)
        """
        key = f"quote:{symbol}:{asset_type}"
        
        # Use asset-specific TTL if no custom TTL provided
        if ttl is None and self._ttl_manager:
            ttl = self._ttl_manager.get_ttl_for_asset(asset_type)
            logger.debug(f"Using asset-specific TTL for {symbol} ({asset_type}): {ttl}s")
        
        self.set(key, quote_data, ttl)
    
    def invalidate_symbol(self, symbol: str) -> None:
        """Invalidate all quotes for a symbol."""
        keys_to_remove = []
        for key in self.get_keys():
            if key.startswith(f"quote:{symbol}:"):
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            self.delete(key)

class SearchCache(MemoryCache):
    """Specialized cache for search results with medium TTL."""
    
    def __init__(self, default_ttl: int = 1800, max_size: int = 200):
        super().__init__(default_ttl=default_ttl, max_size=max_size)
    
    def get_search_results(self, query: str) -> Optional[list]:
        """Get search results for query."""
        key = f"search:{query.upper()}"
        return self.get(key)
    
    def set_search_results(self, query: str, results: list, ttl: Optional[int] = None) -> None:
        """Set search results for query."""
        key = f"search:{query.upper()}"
        self.set(key, results, ttl)

# Global cache instances
quote_cache = QuoteCache(default_ttl=300, max_size=500)  # 5 minutes for quotes
search_cache = SearchCache(default_ttl=1800, max_size=200)  # 30 minutes for searches
general_cache = MemoryCache(default_ttl=600, max_size=1000)  # 10 minutes for general data

def cleanup_expired_caches():
    """Clean up expired entries in all caches."""
    total_cleaned = 0
    total_cleaned += quote_cache.cleanup_expired()
    total_cleaned += search_cache.cleanup_expired()
    total_cleaned += general_cache.cleanup_expired()
    
    if total_cleaned > 0:
        logger.info(f"Cleaned up {total_cleaned} expired cache entries")

def get_cache_stats() -> Dict[str, Any]:
    """Get statistics for all caches."""
    return {
        'quote_cache': quote_cache.get_stats(),
        'search_cache': search_cache.get_stats(),
        'general_cache': general_cache.get_stats()
    }