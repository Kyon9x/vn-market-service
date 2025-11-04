import os

PORT = int(os.getenv("VN_MARKET_SERVICE_PORT", "8765"))
HOST = os.getenv("VN_MARKET_SERVICE_HOST", "127.0.0.1")
CORS_ORIGINS = ["tauri://localhost", "http://localhost:1420"]

# ============================================================================
# Smart Caching Configuration
# ============================================================================

# Quote Cache TTL Configuration (seconds)
# Different asset types have different update frequencies
QUOTE_TTL_CONFIG = {
    'FUND': 86400,      # 24 hours - NAV updates once daily after market close
    'STOCK': 3600,      # 1 hour - Real-time during market, hourly sufficient for most use
    'INDEX': 3600,      # 1 hour - Market indices update frequently but stable
    'GOLD': 3600,       # 1 hour - Commodity prices change throughout day
    'CRYPTO': 900,      # 15 minutes - High volatility (future support)
    'DEFAULT': 3600     # 1 hour - Default fallback for unknown types
}

# Historical Cache Configuration
HISTORICAL_CACHE_CONFIG = {
    'max_gap_for_partial_fetch': 7,    # Days - Fetch only missing if gap <= 7 days
    'min_gap_for_full_fetch': 30,      # Days - Fetch full range if gap >= 30 days
    'auto_fill_today': True,            # Auto-fill today's quote as historical record
    'never_expire': True,               # Historical data never expires (immutable)
    'enable_incremental': True          # Enable incremental fetching feature
}

# Rate Limit Protection Configuration
RATE_LIMIT_CONFIG = {
    'max_calls_per_minute': 6000,         # Maximum API calls per minute
    'max_calls_per_hour': 36000,          # Maximum API calls per hour
    'delay_between_calls_ms': 100,      # Minimum delay between calls (milliseconds)
    'queue_max_size': 100,              # Maximum queued requests
    'enable_throttling': True           # Enable rate limit protection
}

# Database Configuration
DATABASE_CONFIG = {
    'path': os.getenv('VN_MARKET_DB_PATH', 'db/assets.db'),
    'backup_enabled': True,
    'backup_interval_hours': 24
}

# IP-Based Rate Limit Configuration
IP_RATE_LIMIT_CONFIG = {
    'max_calls_per_minute': 60,          # Maximum API calls per minute per IP
    'max_calls_per_hour': 600,           # Maximum API calls per hour per IP
    'delay_between_calls_ms': 200,       # Minimum delay between calls per IP (milliseconds)
    'enable_throttling': True,           # Enable IP-based rate limiting
    'max_tracked_ips': 10000,            # Maximum number of IPs to track (memory protection)
    'cleanup_interval_seconds': 300      # Cleanup inactive IPs every 5 minutes
}

# Request Timeout Configuration
TIMEOUT_CONFIG = {
    'request_timeout_seconds': 30,       # Maximum time for request processing
    'enable_timeout': True               # Enable request timeout protection
}

# Background Tasks Configuration
BACKGROUND_TASKS_CONFIG = {
    'cache_cleanup_interval': 3600,     # Cleanup expired cache every hour
    'quote_refresh_interval': 1800,     # Refresh popular quotes every 30 minutes
    'historical_refresh_interval': 86400,  # Refresh historical data daily
    'enable_auto_seeding': False        # Auto-seed popular assets on startup
}
