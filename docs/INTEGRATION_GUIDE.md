# Vietnamese Market Data Service - Integration Guide

## Overview

This service provides a unified REST API for Vietnamese market data including stocks, mutual funds, indices, and gold prices. Built with FastAPI and powered by the vnstock library, it acts as a bridge between Wealthfolio and Vietnamese market data sources.

## Base URL

```
http://127.0.0.1:8765
```

## Supported Asset Types

1. **Stocks** - Listed companies on HOSE, HNX, and UPCOM
2. **Mutual Funds** - Vietnamese investment funds
3. **Indices** - Market indices (VNINDEX, VN30, HNX, etc.)
4. **Gold** - Multi-provider support (SJC, BTMC, MSN)

## Authentication

No authentication required for local service access.

## Rate Limits

No strict rate limits enforced, but please implement reasonable delays between requests to avoid overwhelming upstream data sources.

## Common Response Fields

All responses include these standard fields:
- `currency` - Asset currency (typically "VND")
- `data_source` - Data source identifier ("VN_MARKET")

## API Endpoints

### Health Check
```
GET /health
```
Returns service status information.

### Generic Search
```
GET /search?query={term}
GET /search/{symbol}
```
Universal search endpoint for all asset types.

### Generic History
```
GET /history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Universal historical data endpoint for all asset types.

### Generic Quote
```
GET /quote/{symbol}
```
Universal quote endpoint for all asset types. Auto-detects asset type and returns the latest price data with an additional `asset_type` field indicating the detected asset category.

### Mutual Funds

#### List All Funds
```
GET /funds
```
Returns a list of all available mutual funds.

#### Search Fund
```
GET /funds/search/{symbol}
```
Get detailed information about a specific fund.

#### Fund Quote
```
GET /funds/quote/{symbol}
```
Get the latest NAV (Net Asset Value) for a fund.

#### Fund History
```
GET /funds/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Get historical NAV data for a fund.

### Stocks

#### Search Stock
```
GET /stocks/search/{symbol}
```
Get company information for a stock.

#### Stock Quote
```
GET /stocks/quote/{symbol}
```
Get the latest price for a stock.

#### Stock History
```
GET /stocks/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Get historical price data for a stock.

### Indices

#### Index Quote
```
GET /indices/quote/{symbol}
```
Get the latest value for an index.

#### Index History
```
GET /indices/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Get historical data for an index.

### Gold (Multi-Provider)

#### Supported Symbols
| Provider | Symbols |
|----------|---------|
| **SJC** | `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC` |
| **BTMC** | `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC` |
| **MSN** | `GOLD_MSN`, `GOLD`, `MSN_GOLD` |

#### Search Gold
```
GET /gold/search/{symbol}
```
Get information about a gold provider.

#### Gold Quote
```
GET /gold/quote/{symbol}
```
Get the latest gold price from a specific provider.

#### Gold History
```
GET /gold/history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
Get historical gold prices from a specific provider.

## Response Formats

### Fund Responses

#### Fund List Response
```json
{
  "funds": [
    {
      "symbol": "SSISCA",
      "fund_name": "SSI Cổ phiếu A",
      "asset_type": "FUND",
      "data_source": "VN_MARKET"
    }
  ],
  "total": 150
}
```

#### Fund Search Response
```json
{
  "symbol": "SSISCA",
  "fund_name": "Quỹ SSI Cổ phiếu A",
  "fund_type": "Open-End Fund",
  "management_company": "SSI Fund Management",
  "inception_date": "2020-01-15",
  "nav_per_unit": 15234.56,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Fund Quote Response
```json
{
  "symbol": "SSISCA",
  "nav": 15234.56,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Fund History Response
```json
{
  "symbol": "SSISCA",
  "history": [
    {
      "date": "2025-10-31",
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

### Stock Responses

#### Stock Search Response
```json
{
  "symbol": "VNM",
  "company_name": "Vinamilk",
  "exchange": "HOSE",
  "industry": "Food Products",
  "company_type": "Listed Company",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Stock Quote Response
```json
{
  "symbol": "VNM",
  "close": 85000,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Stock History Response
```json
{
  "symbol": "VNM",
  "history": [
    {
      "date": "2025-10-31",
      "nav": 85000,
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

### Index Responses

#### Index Quote Response
```json
{
  "symbol": "VNINDEX",
  "close": 1250.45,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Index History Response
```json
{
  "symbol": "VNINDEX",
  "history": [
    {
      "date": "2025-10-31",
      "nav": 1250.45,
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

### Gold Responses

#### Gold Search Response
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

#### Gold Quote Response (SJC/BTMC)
```json
{
  "symbol": "VN_GOLD_SJC",
  "close": 84500000,
  "date": "2025-10-31",
  "buy_price": 84000000,
  "sell_price": 86500000,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

#### Gold Quote Response (MSN)
```json
{
  "symbol": "GOLD_MSN",
  "close": 2100000,
  "date": "2025-10-31",
  "currency": "USD",
  "data_source": "VN_MARKET"
}
```

#### Gold History Response
```json
{
  "symbol": "VN_GOLD_SJC",
  "history": [
    {
      "date": "2025-10-31",
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

### Universal Quote Responses

#### Stock Quote Response
```json
{
  "symbol": "VNM",
  "close": 85000,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET",
  "asset_type": "STOCK"
}
```

#### Fund Quote Response
```json
{
  "symbol": "SSISCA",
  "nav": 15234.56,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET",
  "asset_type": "FUND"
}
```

#### Index Quote Response
```json
{
  "symbol": "VNINDEX",
  "close": 1250.45,
  "date": "2025-10-31",
  "currency": "VND",
  "data_source": "VN_MARKET",
  "asset_type": "INDEX"
}
```

#### Gold Quote Response (SJC/BTMC)
```json
{
  "symbol": "VN_GOLD_SJC",
  "close": 84500000,
  "date": "2025-10-31",
  "buy_price": 84000000,
  "sell_price": 86500000,
  "currency": "VND",
  "data_source": "VN_MARKET",
  "asset_type": "GOLD"
}
```

#### Gold Quote Response (MSN)
```json
{
  "symbol": "GOLD_MSN",
  "close": 2100000,
  "date": "2025-10-31",
  "currency": "USD",
  "data_source": "VN_MARKET",
  "asset_type": "GOLD"
}
```

## Error Handling

All errors follow standard HTTP status codes:
- `404` - Resource not found (invalid symbol)
- `400` - Bad request (invalid parameters)
- `500` - Internal server error (API failure)

Error response format:
```json
{
  "detail": "Error message"
}
```

## Usage Examples

### cURL Examples

```bash
# Get health status
curl http://127.0.0.1:8765/health

# Search for a stock
curl http://127.0.0.1:8765/stocks/search/VNM

# Get latest stock price
curl http://127.0.0.1:8765/stocks/quote/VNM

# Get stock history
curl "http://127.0.0.1:8765/stocks/history/VNM?start_date=2025-10-01&end_date=2025-10-31"

# Search for a fund
curl http://127.0.0.1:8765/funds/search/SSISCA

# Get latest fund NAV
curl http://127.0.0.1:8765/funds/quote/SSISCA

# Get fund history
curl "http://127.0.0.1:8765/funds/history/SSISCA?start_date=2025-10-01&end_date=2025-10-31"

# Get VNINDEX quote
curl http://127.0.0.1:8765/indices/quote/VNINDEX

# Get VNINDEX history
curl "http://127.0.0.1:8765/indices/history/VNINDEX?start_date=2025-10-01&end_date=2025-10-31"

# Search for gold
curl http://127.0.0.1:8765/gold/search/VN_GOLD_SJC

# Get latest gold price (SJC)
curl http://127.0.0.1:8765/gold/quote/VN_GOLD_SJC

# Get gold history (SJC)
curl "http://127.0.0.1:8765/gold/history/VN_GOLD_SJC?start_date=2025-10-01&end_date=2025-10-31"

# Universal search
curl "http://127.0.0.1:8765/search?query=gold"

# Universal history
curl "http://127.0.0.1:8765/history/VNM?start_date=2025-10-01&end_date=2025-10-31"

# Universal quote
curl http://127.0.0.1:8765/quote/VNM
```

### Python Examples

```python
import requests

BASE_URL = "http://127.0.0.1:8765"

# Get stock quote
response = requests.get(f"{BASE_URL}/stocks/quote/VNM")
if response.status_code == 200:
    data = response.json()
    print(f"VNM price: {data['close']} VND on {data['date']}")

# Get fund history
params = {
    "start_date": "2025-10-01",
    "end_date": "2025-10-31"
}
response = requests.get(f"{BASE_URL}/funds/history/SSISCA", params=params)
if response.status_code == 200:
    data = response.json()
    print(f"Retrieved {len(data['history'])} days of fund data")

# Get gold quote
response = requests.get(f"{BASE_URL}/gold/quote/VN_GOLD_SJC")
if response.status_code == 200:
    data = response.json()
    print(f"SJC Gold: Buy {data['buy_price']}, Sell {data['sell_price']}")

# Get universal quote (auto-detects asset type)
response = requests.get(f"{BASE_URL}/quote/VNM")
if response.status_code == 200:
    data = response.json()
    print(f"{data['symbol']} ({data['asset_type']}): {data.get('close') or data.get('nav')} {data['currency']}")
```

## Integration Best Practices

1. **Handle Errors Gracefully** - Always check HTTP status codes
2. **Implement Retry Logic** - For transient failures
3. **Cache Responses** - Especially for fund listings and static data
4. **Respect Rate Limits** - Add small delays between rapid requests
5. **Validate Symbols** - Use search endpoints to verify asset existence
6. **Handle Date Ranges** - Use appropriate start/end dates for historical data

## Support

For integration questions or issues, please refer to:
- Service documentation in `README.md`
- Gold API specifics in `GOLD_API_UPGRADE.md`
- vnstock reference in `VNSTOCK_COMMANDS_REFERENCE.md`
