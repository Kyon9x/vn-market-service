# Vietnamese Market Data Service

FastAPI microservice providing comprehensive market data for Vietnamese assets (stocks, mutual
funds, indices) using the vnstock library.

## Overview

This service acts as a local API gateway between Wealthfolio and Vietnamese market data, exposing
REST endpoints that the Rust core can consume. It supports stocks, mutual funds, and indices.

## Features

- ✅ **Stocks**: Search, quotes, and historical data for Vietnamese stocks
- ✅ **Mutual Funds**: List, search, quotes, and historical NAV data
- ✅ **Indices**: Quotes and historical data for Vietnamese market indices
- ✅ **Gold**: Multi-provider support (SJC, BTMC, MSN) with search, quotes, and history
- ✅ 24-hour caching for fund listings
- ✅ NAV-to-OHLC mapping for chart compatibility
- ✅ CORS enabled for Tauri integration

## Architecture

```
┌─────────────┐      HTTP      ┌──────────────────┐      vnstock      ┌─────────────┐
│  Wealthfolio │ ◄──────────────► │  FastAPI Service │ ◄────────────────► │  Market Data│
│  (Rust/Tauri)│                 │   (Python 3.x)   │                   │  (vnstock)  │
└─────────────┘                 └──────────────────┘                   └─────────────┘
```

## Installation

### Prerequisites

- Python 3.12 or higher (required for vnstock 3.x compatibility)
- pip3

> **Note**: vnstock 3.x requires Python 3.12+. If you're using an older Python version, you'll need
> to upgrade.

### Setup

```bash
cd services/vn-market-service

# Install dependencies
pip3 install -r requirements.txt

# Make start script executable
chmod +x start.sh
```

## Running the Service

### Manual Start

```bash
./start.sh
```

Or:

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

### Auto-start with Tauri

The service is automatically started by Tauri when Wealthfolio launches. See `src-tauri/src/main.rs`
for implementation details.

## API Endpoints

Base URL: `http://127.0.0.1:8765`

### Health Check

```
GET /health
```

**Response:**

```json
{
  "status": "healthy",
  "service": "vn-market-service",
  "version": "2.0.0"
}
```

### Mutual Funds

#### List All Funds

```
GET /funds
```

**Response:**

```json
{
  "funds": [
    {
      "symbol": "VFMVF1",
      "fund_name": "Vietnam Mutual Fund 1",
      "asset_type": "MUTUAL_FUND",
      "data_source": "VN_MARKET"
    }
  ],
  "total": 150
}
```

#### Search Fund by Symbol

```
GET /funds/search/{symbol}
```

**Response:**

```json
{
  "symbol": "VFMVF1",
  "fund_name": "Vietnam Mutual Fund 1",
  "fund_type": "Open-End Fund",
  "management_company": "VFM Fund Management",
  "inception_date": "2020-01-15",
  "nav_per_unit": 15234.56,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Fund Quote

```
GET /funds/quote/{symbol}
```

**Response:**

```json
{
  "symbol": "VFMVF1",
  "nav": 15234.56,
  "date": "2024-10-26",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Fund History

```
GET /funds/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Response:**

```json
{
  "symbol": "VFMVF1",
  "history": [
    {
      "date": "2024-10-26",
      "nav": 15234.56,
      "open": 15234.56,
      "high": 15234.56,
      "low": 15234.56,
      "close": 15234.56,
      "adjclose": 15234.56,
      "volume": 0.0
    }
  ],
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

### Stocks

#### Search Stock

```
GET /stocks/search/{symbol}
```

**Response:**

```json
{
  "symbol": "VNM",
  "company_name": "Vietnam Dairy Products JSC",
  "exchange": "HOSE",
  "industry": "Food Products",
  "company_type": "Listed Company",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Stock Quote

```
GET /stocks/quote/{symbol}
```

**Response:**

```json
{
  "symbol": "VNM",
  "close": 85000,
  "date": "2024-10-26",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Stock History

```
GET /stocks/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Response:**

```json
{
  "symbol": "VNM",
  "history": [
    {
      "date": "2024-10-26",
      "open": 84500,
      "high": 85500,
      "low": 84000,
      "close": 85000,
      "adjclose": 85000,
      "volume": 1234567
    }
  ],
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

### Indices

#### Get Index Quote

```
GET /indices/quote/{symbol}
```

**Response:**

```json
{
  "symbol": "VNINDEX",
  "close": 1250.45,
  "date": "2024-10-26",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Index History

```
GET /indices/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Response:**

```json
{
  "symbol": "VNINDEX",
  "history": [
    {
      "date": "2024-10-26",
      "open": 1248.3,
      "high": 1252.8,
      "low": 1245.2,
      "close": 1250.45,
      "adjclose": 1250.45,
      "volume": 123456789
    }
  ],
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

### Gold (Multi-Provider)

Supports 3 gold providers: **SJC** (Saigon Jewelry Company), **BTMC** (Bao Tin Minh Chau), and
**MSN** (Global Commodity).

**Supported Symbols:**

| Provider | Symbols |
|----------|---------|
| **SJC** | `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC` |
| **BTMC** | `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC` |
| **MSN** | `GOLD_MSN`, `GOLD`, `MSN_GOLD` |

#### Search Gold

```
GET /gold/search/{symbol}
```

**Examples:**

```
GET /gold/search/VN_GOLD_SJC    # SJC provider
GET /gold/search/BTMC_GOLD      # BTMC provider
GET /gold/search/GOLD_MSN       # MSN provider
GET /gold/search/VN_GOLD        # Backward compatible (defaults to SJC)
```

**Response:**

```json
{
  "symbol": "VN_GOLD_SJC",
  "name": "Gold - Saigon Jewelry Company",
  "provider": "sjc",
  "provider_name": "Saigon Jewelry Company",
  "asset_type": "Commodity",
  "exchange": "SJC",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Gold Quote

```
GET /gold/quote/{symbol}
```

**Examples:**

```
GET /gold/quote/VN_GOLD_SJC     # SJC: Buy/Sell prices
GET /gold/quote/BTMC_GOLD       # BTMC: Buy/Sell prices
GET /gold/quote/GOLD_MSN        # MSN: Close price
```

**Response (SJC):**

```json
{
  "symbol": "VN_GOLD_SJC",
  "close": 84500000,
  "date": "2024-10-26",
  "buy_price": 84000000,
  "sell_price": 86500000,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

**Response (MSN):**

```json
{
  "symbol": "GOLD_MSN",
  "close": 2100000,
  "date": "2024-10-26",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Get Gold History

```
GET /gold/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Examples:**

```
GET /gold/history/VN_GOLD_SJC?start_date=2024-10-01&end_date=2024-10-26
GET /gold/history/BTMC_GOLD?start_date=2024-10-01&end_date=2024-10-26
GET /gold/history/GOLD_MSN?start_date=2024-10-01&end_date=2024-10-26
```

**Response:**

```json
{
  "symbol": "VN_GOLD_SJC",
  "history": [
    {
      "date": "2024-10-26",
      "nav": 84500000,
      "open": 84500000,
      "high": 84500000,
      "low": 84500000,
      "close": 84500000,
      "adjclose": 84500000,
      "volume": 0.0,
      "buy_price": 84000000,
      "sell_price": 86500000
    }
  ],
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

### Search & History (Generic Endpoints)

#### Search Any Asset by Symbol

```
GET /search/{symbol}
```

**Examples:**

```
GET /search/VNM           # Stock
GET /search/VFMVF1        # Fund
GET /search/VNINDEX       # Index
GET /search/VN_GOLD_SJC   # Gold (SJC)
GET /search/BTMC_GOLD     # Gold (BTMC)
```

#### Search All Assets by Query

```
GET /search?query={query}
```

**Examples:**

```
GET /search?query=gold              # Returns all 3 gold providers
GET /search?query=vnm               # Stock and gold results
GET /search?query=vn-index          # Index results
```

#### Get Any Asset History

```
GET /history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Examples:**

```
GET /history/VNM?start_date=2024-10-01&end_date=2024-10-26                    # Stock
GET /history/VFMVF1?start_date=2024-10-01&end_date=2024-10-26                 # Fund
GET /history/VNINDEX?start_date=2024-10-01&end_date=2024-10-26                # Index
GET /history/GOLD_MSN?start_date=2024-10-01&end_date=2024-10-26               # Gold (MSN)
```

## Gold API Provider Information

### About Gold Providers

The Gold API supports three independent gold price providers:

| Provider | API Source | Data | Fallback |
|----------|-----------|------|----------|
| **SJC** | vnstock `sjc_gold_price()` | Buy/Sell prices in VND per tael | 84M/86.5M VND |
| **BTMC** | vnstock `btmc_goldprice()` | Buy/Sell prices, karat details | 82M/85M VND |
| **MSN** | vnstock `world_index(symbol='GOLD', source='MSN')` | OHLCV global commodity prices | ~2.1M VND |

### Backward Compatibility

✅ **Full backward compatibility maintained!**

- Old code using `VN_GOLD` continues to work without changes
- Automatically routes to SJC provider (primary Vietnamese gold)
- Gradual migration to explicit provider symbols recommended

**Migration Examples:**

```bash
# Old (still works)
GET /gold/quote/VN_GOLD

# New (recommended - explicit provider)
GET /gold/quote/VN_GOLD_SJC
```

### Quick Start: Gold Price Monitoring

```bash
# Get current SJC gold price
curl http://127.0.0.1:8765/gold/quote/VN_GOLD_SJC

# Get current BTMC gold price
curl http://127.0.0.1:8765/gold/quote/BTMC_GOLD

# Get 30-day SJC history
curl "http://127.0.0.1:8765/gold/history/VN_GOLD_SJC?start_date=$(date -d '30 days ago' +%Y-%m-%d)&end_date=$(date +%Y-%m-%d)"

# Search all gold providers
curl "http://127.0.0.1:8765/search?query=gold"
```

## Configuration

Environment variables (see `.env` or `app/config.py`):

```python
VN_MARKET_SERVICE_PORT = 8765
VN_MARKET_SERVICE_HOST = "127.0.0.1"
CORS_ORIGINS = [
    "tauri://localhost",
    "http://localhost:1420"
]
```

## Integration with Wealthfolio

The Rust provider in `src-core/src/market_data/providers/vn_market_provider.rs` consumes these
endpoints to:

1. Search and validate Vietnamese asset symbols (stocks, funds, indices)
2. Fetch asset profiles during symbol search
3. Retrieve historical data for portfolio calculations
4. Get latest quotes for real-time valuations

## Troubleshooting

### Migration to vnstock 3.x

If you're upgrading from vnstock 2.x to 3.x, note the following changes:

- **Python Requirement**: vnstock 3.x requires Python 3.12 or higher
- **API Changes**: The vnstock API has been updated. All clients (stock, fund, index) have been
  migrated to use the new API
- **Virtual Environment**: Recommended to create a fresh virtual environment with Python 3.12+

To migrate:

```bash
# Create new virtual environment with Python 3.12+
python3.12 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install updated dependencies
pip install -r requirements.txt

# Verify vnstock version
pip list | grep vnstock  # Should show 3.2.6 or higher
```

### Service won't start

- Check Python version: `python3 --version` (need 3.10+)
- Verify dependencies: `pip3 list | grep fastapi`
- Verify vnstock version: `pip3 list | grep vnstock` (need 3.2.6+)
- Check port availability: `lsof -i :8765`

### vnstock errors

- Update vnstock: `pip3 install --upgrade vnstock`
- Check internet connection
- Verify symbol exists

## Dependencies

- **fastapi**: Web framework
- **uvicorn**: ASGI server
- **vnstock**: Vietnamese market data library
- **pydantic**: Data validation

## License

Same as Wealthfolio project.
