# Gold API Multi-Provider Support

## Overview
Updated the Vietnamese Market Service to support multiple gold price providers (SJC, BTMC, MSN) instead of just SJC. The implementation uses a consistent `{symbol}` parameter pattern across all endpoints.

## Changes Made

### 1. New Endpoint Structure
All gold endpoints now follow the standard `{symbol}` pattern:

```
GET /gold/search/{symbol}       - Get gold asset information
GET /gold/quote/{symbol}        - Get latest gold price
GET /gold/history/{symbol}      - Get historical gold prices
```

### 2. Supported Gold Symbols

#### SJC (Saigon Jewelry Company)
- `VN_GOLD` (backward compatible, default)
- `VN_GOLD_SJC`
- `SJC_GOLD`
- `SJC`

#### BTMC (Bao Tin Minh Chau)
- `VN_GOLD_BTMC`
- `BTMC_GOLD`
- `BTMC`

#### MSN (Global Commodity)
- `GOLD_MSN`
- `GOLD`
- `MSN_GOLD`

### 3. API Response Changes

#### Search Response
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

#### Quote Response
```json
{
  "symbol": "VN_GOLD_SJC",
  "close": 84500000.0,
  "date": "2025-10-30",
  "buy_price": 84000000.0,
  "sell_price": 86500000.0,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

### 4. Files Modified

#### app/clients/gold_client.py
- Added `PROVIDERS` configuration for all 3 providers
- Added `parse_symbol()` method for symbol parsing and validation
- Added provider-specific implementations:
  - `_get_sjc_history()`, `_get_sjc_quote()`
  - `_get_btmc_history()`, `_get_btmc_quote()`
  - `_get_msn_history()`, `_get_msn_quote()`
- Refactored main methods to accept `symbol` parameter
- All methods include fallback mechanisms for API failures

#### app/models.py
- Updated `GoldSearchResponse` with:
  - `provider: str` field
  - `provider_name: str` field

#### app/main.py
- Updated `/gold/search/{symbol}` endpoint
- Updated `/gold/quote/{symbol}` endpoint
- Updated `/gold/history/{symbol}` endpoint
- Updated `/search/{symbol}` to recognize gold symbols
- Updated `/history/{symbol}` to handle gold symbols
- Updated `/search` query endpoint to return all 3 providers for "gold" queries

## Backward Compatibility

✅ **Fully maintained!**

- `VN_GOLD` automatically maps to SJC provider (default)
- Old clients using `/gold/search/VN_GOLD`, `/gold/quote/VN_GOLD`, etc. will continue to work
- Symbol `VN_GOLD` is first in the SJC symbols list

## Provider Data Characteristics

| Provider | API Function | Strengths | Limitations | Fallback Data |
|----------|-------------|----------|-------------|--------------|
| **SJC** | `sjc_gold_price(date)` | Official VN gold, good history | API dependent | Buy: 84M, Sell: 86.5M VND/tael |
| **BTMC** | `btmc_goldprice()` | Current prices, 24K detail | Limited history | Buy: 82M, Sell: 85M VND/tael |
| **MSN** | `world_index(symbol='GOLD', source='MSN')` | Global commodity, OHLCV data | USD-based, no spreads | ~2.1M VND equivalent |

## Usage Examples

### Get Latest Quote
```bash
# SJC
curl http://localhost:8000/gold/quote/VN_GOLD_SJC

# BTMC
curl http://localhost:8000/gold/quote/BTMC_GOLD

# MSN
curl http://localhost:8000/gold/quote/GOLD_MSN

# Backward compatible (defaults to SJC)
curl http://localhost:8000/gold/quote/VN_GOLD
```

### Get Historical Data
```bash
# 30 days SJC history
curl "http://localhost:8000/gold/history/VN_GOLD_SJC?start_date=2025-09-30&end_date=2025-10-30"

# BTMC history
curl "http://localhost:8000/gold/history/BTMC_GOLD?start_date=2025-09-30&end_date=2025-10-30"
```

### Search Queries
```bash
# Returns all 3 providers
curl "http://localhost:8000/search?query=gold"

# Specific provider
curl "http://localhost:8000/search/VN_GOLD_SJC"
```

## Implementation Details

### Symbol Normalization
The `parse_symbol()` method:
1. Converts input to uppercase
2. Searches through all provider configurations
3. Returns normalized symbol and provider name
4. Raises `ValueError` for invalid symbols

### Provider Selection Flow
1. Client sends symbol (e.g., `BTMC_GOLD`)
2. `parse_symbol()` identifies provider (btmc)
3. Appropriate provider method is called (`_get_btmc_quote()`)
4. Fallback prices used if API fails
5. Standardized response returned

### Error Handling
- Invalid symbols raise `HTTPException(404)`
- API failures trigger fallback mechanism
- All provider methods include try-except blocks
- Logging includes provider name and error details

## Testing

Run the following commands to test:

```bash
# Test SJC search
curl http://localhost:8000/gold/search/VN_GOLD_SJC

# Test BTMC quote
curl http://localhost:8000/gold/quote/BTMC_GOLD

# Test MSN history
curl http://localhost:8000/gold/history/GOLD_MSN?start_date=2025-10-23&end_date=2025-10-30

# Test backward compatibility
curl http://localhost:8000/gold/quote/VN_GOLD

# Test generic search
curl "http://localhost:8000/search?query=gold"
```

## Future Enhancements

Potential improvements:
- Add provider-specific configuration in environment variables
- Implement caching layer for API responses
- Add rate limiting per provider
- Support multiple providers in single request (comma-separated)
- Add provider health status endpoint
- Implement provider priority/weighting for data aggregation

## Migration Notes

For existing clients:
- No breaking changes - all existing code continues to work
- Recommend updating to use explicit provider symbols for clarity
- Can migrate at own pace with no urgency

Example migration path:
```
Old: /gold/quote/VN_GOLD
New: /gold/quote/VN_GOLD_SJC  (explicit provider)
```
