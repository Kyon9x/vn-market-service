"""
Vietnamese Market Service Cache Module

Provides comprehensive caching functionality including:
- SQLite persistent cache with TTL support
- In-memory cache for high-speed access
- Search optimization with parallel execution
- Background cache management
- Data seeding for initial population
- Smart caching with asset-specific TTL
- Incremental historical data fetching
- Rate limit protection
"""

from .cache_manager import CacheManager
from .memory_cache import MemoryCache, QuoteCache, SearchCache, quote_cache, search_cache, general_cache
from .search_optimizer import SearchOptimizer, get_search_optimizer
from .background_manager import BackgroundCacheManager, start_cache_background_tasks, stop_cache_background_tasks
from .data_seeder import DataSeeder, get_data_seeder
from .migrations import CacheMigration, migrate_database, check_migration_status
from .quote_ttl_manager import QuoteTTLManager, get_ttl_manager, get_ttl_for_asset
from .historical_cache import HistoricalCacheManager, get_historical_cache
from .rate_limit_protector import RateLimitProtector, get_rate_limiter

__all__ = [
    # Core caching
    'CacheManager',
    'MemoryCache', 
    'QuoteCache', 
    'SearchCache',
    'quote_cache',
    'search_cache', 
    'general_cache',
    
    # Search optimization
    'SearchOptimizer',
    'get_search_optimizer',
    
    # Background tasks
    'BackgroundCacheManager',
    'start_cache_background_tasks',
    'stop_cache_background_tasks',
    
    # Data seeding
    'DataSeeder',
    'get_data_seeder',
    
    # Migrations
    'CacheMigration',
    'migrate_database',
    'check_migration_status',
    
    # Smart caching
    'QuoteTTLManager',
    'get_ttl_manager',
    'get_ttl_for_asset',
    
    # Historical data
    'HistoricalCacheManager',
    'get_historical_cache',
    
    # Rate limiting
    'RateLimitProtector',
    'get_rate_limiter'
]