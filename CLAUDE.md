# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **FastAPI microservice** that provides Vietnamese market data (stocks, mutual funds, indices, and gold) to the Wealthfolio Rust/Tauri application. It acts as a local API gateway between Wealthfolio and Vietnamese market data using the `vnstock` library.

**Key Statistics:**
- FastAPI service running on port 8765
- Multi-layer caching (SQLite persistent + in-memory LRU)
- Database-backed historical data with SQLite (`db/assets.db`)
- Rate limiting and retry logic with Vietnamese error handling
- Auto-started by Tauri when Wealthfolio launches

## Common Development Commands

### Running the Service

```bash
# Standard startup (uses .venv if available)
./start.sh

# Or directly with uvicorn
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765

# With virtual environment
source .venv/bin/activate
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level info
```

### Docker Operations

```bash
# Start with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f vn-market-service

# Stop
docker-compose down

# Run tests with Docker
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

### Database Management

```bash
# Run database migrations/management script
./manage_db.sh

# Check if service is running on port 8765
lsof -i :8765

# View application logs
tail -f logs/app.log  # (if logging is configured)
```

### Installing Dependencies

```bash
# Create virtual environment with Python 3.12+
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify vnstock version (requires 3.2.6+)
pip list | grep vnstock
```

## Architecture Overview

### High-Level Architecture

```
┌─────────────┐      HTTP      ┌──────────────────┐      vnstock      ┌─────────────┐
│  Wealthfolio │ ◄──────────────► │  FastAPI Service │ ◄────────────────► │  Market Data│
│  (Rust/Tauri)│                 │   (Python 3.12+) │                   │  (vnstock)  │
└─────────────┘                 └──────────────────┘                   └─────────────┘
                                      │
                                      ▼
                               ┌──────────────┐
                               │   SQLite DB  │
                               │  (assets.db) │
                               └──────────────┘
```

### Core Components

#### 1. **API Layer** (`app/main.py`)
- FastAPI application with 4 main asset type endpoints
- CORS enabled for Tauri integration
- Global exception handling and validation
- Asset classification validation functions

**Key Endpoints:**
- `GET /health` - Health check
- `/funds/*` - Mutual fund data
- `/stocks/*` - Stock data
- `/indices/*` - Market indices
- `/gold/*` - Gold prices (multi-provider)
- `/search/*` - Cross-asset search

#### 2. **Client Layer** (`app/clients/`)
Domain-specific clients that interface with vnstock:

- **fund_client.py** - Mutual fund listings, NAV, and history
- **stock_client.py** - Stock quotes and historical data
- **index_client.py** - Index tracking (VNINDEX, etc.)
- **gold_client.py** - Multi-provider gold data (SJC/BTMC/MSN)

Each client has:
- Provider call logging with `@log_provider_call` decorator
- Rate limiting and retry logic
- Database-first approach for historical data
- Memory cache integration

#### 3. **Caching System** (`app/cache/`)
Multi-layer intelligent caching:

- **cache_manager.py** - SQLite persistent cache with TTL
- **memory_cache.py** - High-speed LRU in-memory cache
- **historical_cache.py** - Immutable historical data cache
- **rate_limit_protector.py** - Vietnamese error detection & adaptive backoff
- **quote_ttl_manager.py** - Asset-type-specific TTL rules
- **search_optimizer.py** - Parallel search execution
- **background_manager.py** - Automatic cleanup and refresh tasks
- **data_seeder.py** - Pre-populates popular assets on startup
- **gold_static_seeder.py** - One-time historical gold data seeding (2016-present)

**TTL Configuration** (from `app/config.py`):
- FUND: 24 hours (daily NAV updates)
- STOCK: 1 hour
- INDEX: 1 hour
- GOLD: 1 hour
- DEFAULT: 1 hour

#### 4. **Models** (`app/models.py`)
Pydantic models for API responses and request validation:
- Response models for each asset type
- Structured data validation
- Type safety across the API

#### 5. **Configuration** (`app/config.py`)
- Port/Host settings: 8765/127.0.0.1
- CORS origins: `tauri://localhost`, `http://localhost:1420`
- Rate limiting: 60 calls/min, 500 calls/hour
- Database path: `db/assets.db`
- Background task intervals

#### 6. **Utils** (`app/utils/`)
- **provider_logger.py** - Decorator for logging vnstock API calls with `[provider=call]` tags

## Key Development Patterns

### 1. Provider Call Logging
All vnstock API calls use the `@log_provider_call` decorator:

```python
@log_provider_call(provider_name="vnstock", metadata_fields={"rows": lambda r: len(r) if r is not None else 0})
def _fetch_stock_history_from_provider(self, symbol: str, start_date: str, end_date: str):
    # Implementation
```

### 2. Database-First Architecture
Historical data queries check the database first, falling back to API only when necessary:
- Eliminates API rate limiting for historical requests
- Provides offline capability
- Reduces response times

### 3. Rate Limiting & Retry Logic
Intelligent rate limiting with Vietnamese error detection:
- Detects Vietnamese rate limit messages: "quá nhiều request", "thử lại sau 15 giây"
- Parses wait times from error messages
- Implements exponential backoff
- Adaptive delays based on consecutive errors

### 4. Smart Caching Strategy
- **Persistent Cache (SQLite)**: Long-term storage with TTL
- **Memory Cache (LRU)**: Hot data for instant access
- **Historical Cache**: Immutable data that never expires
- **Background Tasks**: Automatic cleanup and refresh

### 5. Asset Classification Validation
The system validates asset classifications:
- STOCK → Equity/Stock
- FUND → Investment Fund/Mutual Fund
- INDEX → Index/Market Index
- GOLD → Commodity/Precious Metal

## Gold API Provider Architecture

The Gold API supports **three independent providers** with different data sources:

| Provider | API Source | Data Format | Typical Price Range |
|----------|-----------|-------------|-------------------|
| **SJC** | `sjc_gold_price()` | Buy/Sell prices in VND per tael | ~84M-86.5M VND |
| **BTMC** | `btmc_goldprice()` | Buy/Sell + karat details | ~82M-85M VND |
| **MSN** | `world_index(symbol='GOLD', source='MSN')` | Global commodity OHLCV | ~2.1M VND |

**Symbol Mapping:**
- SJC: `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC`
- BTMC: `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC`
- MSN: `GOLD_MSN`, `GOLD`, `MSN_GOLD`

**Backward Compatibility:**
- Old code using `VN_GOLD` automatically routes to SJC provider
- Full backward compatibility maintained

## Important Implementation Notes

### Python Version Requirement
- **Python 3.12+ required** (for vnstock 3.x compatibility)
- Check with: `python3 --version`
- The `.venv` contains Python 3.14

### vnstock Configuration
- Timeout configured in `app/vnstock_config.py` before importing clients
- All clients use the shared configuration

### Database Schema
- SQLite database at `db/assets.db`
- Tables: `assets`, `quotes`, `historical_records`, `search_cache`
- Automatic migrations via `app/cache/migrations.py`

### Health Check Endpoint
```bash
curl http://127.0.0.1:8765/health
```

Response:
```json
{
  "status": "healthy",
  "service": "vn-market-service",
  "version": "2.0.0"
}
```

### Testing Approach
- **No traditional unit tests** in the project
- Integration testing via `docker-compose.test.yml`
- Manual testing with `curl` commands
- Provider call logging for debugging

### Logging Format
Provider calls are logged with structured format:
```
[provider=call] [provider_name=vnstock] method=stock_client._fetch_stock_history_from_provider status=success duration=245ms
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application, all endpoints, startup/shutdown logic |
| `app/config.py` | All configuration (ports, TTL, rate limits, database) |
| `app/clients/*.py` | Domain-specific data clients (fund, stock, index, gold) |
| `app/cache/cache_manager.py` | SQLite persistent cache manager |
| `app/cache/memory_cache.py` | In-memory LRU cache with TTL |
| `app/cache/rate_limit_protector.py` | Vietnamese rate limit detection & retry logic |
| `app/cache/historical_cache.py` | Database-first historical data architecture |
| `app/utils/provider_logger.py` | Decorator for logging vnstock API calls |
| `manage_db.sh` | Database management operations |
| `start.sh` | Service startup script |
| `docker-compose.yml` | Production deployment config |

## Recent Major Changes

### Gold Client Refactor (Latest)
- Simplified to SJC-only provider architecture
- Created `gold_static_seeder.py` for historical gold data (2016-present, ~2,566 trading days)
- Database-first approach for all historical gold queries
- Intelligent rate limiting with Vietnamese error detection
- **Estimated seeding time**: 1.5-3 hours (one-time operation)

### Smart Caching System
- Multi-layer caching with SQLite + Memory
- Parallel search execution with deduplication
- Background cache cleanup and refresh
- Asset-type-specific TTL rules

### Provider Logging
- Decorator-based logging for all vnstock API calls
- Structured format with `[provider=call]` tags
- Execution time tracking
- Success/error status logging

## Troubleshooting

### Service Won't Start
```bash
# Check Python version (need 3.10+)
python3 --version

# Verify dependencies
pip3 list | grep fastapi

# Check port availability
lsof -i :8765

# Run directly to see errors
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level debug
```

### vnstock Errors
- Update vnstock: `pip3 install --upgrade vnstock`
- Check internet connection
- Verify symbol exists: `/search/{symbol}`

### Rate Limiting
- Vietnamese error messages automatically detected
- Adaptive backoff implemented
- Check logs for `[provider=call]` entries
- Reduce rate: `RATE_LIMIT_CONFIG['max_calls_per_minute']` in `config.py`

### Database Issues
```bash
# Reset database
rm db/assets.db
./manage_db.sh  # Re-run migrations
```

## Integration with Wealthfolio

The Rust provider in `src-core/src/market_data/providers/vn_market_provider.rs` consumes these endpoints to:
1. Search and validate Vietnamese asset symbols
2. Fetch asset profiles during symbol search
3. Retrieve historical data for portfolio calculations
4. Get latest quotes for real-time valuations

The service is **auto-started by Tauri** when Wealthfolio launches (see `src-tauri/src/main.rs`).
