# Vietnamese Market Data Service – Universal Integration Guide

## Overview

The Vietnamese Market Data Service exposes a single set of REST endpoints that auto-detect asset type and return standardized responses for equities, mutual funds, indices, gold, and additional instruments. The service is backed by `vnstock` and normalizes asset metadata, classifications, and pricing so integrators can rely on the same schema across the entire catalogue.

## Base URL

```
http://127.0.0.1:8765
```

## Authentication

Authentication is not required for local deployments.

## Rate Limits

No formal limits are enforced, but introduce small delays between bursts of requests to protect upstream data sources.

## Universal Endpoint Catalogue

All integration work should target these endpoints. Asset-specific routes remain available but are superseded by the universal interface.

### Health Check
```
GET /health
```
Returns service status and version metadata.

### Universal Search
```
GET /search?query={term}
GET /search/{symbol}
```
- `query` supports partial symbol or name matches.
- Results return an `asset_profile` object per match with normalized classifications.

**Asset profile response example**
```json
{
  "symbol": "VNM",
  "name": "Vinamilk Joint Stock Company",
  "asset_type": "STOCK",
  "asset_class": "Equity",
  "asset_sub_class": "Stock",
  "isin": "VN000000VNM",
  "countries": ["Vietnam"],
  "categories": ["Consumer Staples"],
  "currency": "VND",
  "exchange": "HOSE",
  "data_source": "VN_MARKET"
}
```

### Universal Quote
```
GET /quote/{symbol}
```
- Detects the asset type automatically and returns the latest pricing snapshot.
- `adjclose` is always populated; if a provider omits an adjusted value the service mirrors `close`.
- `data_source` is consistently `VN_MARKET`.

**Quote response example**
```json
{
  "symbol": "SSISCA",
  "asset_type": "FUND",
  "open": 15212.34,
  "high": 15298.76,
  "low": 15180.12,
  "close": 15255.48,
  "adjclose": 15255.48,
  "volume": 0,
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

Provider-specific attributes (e.g., `buy_price`, `sell_price`) are included when applicable, in addition to the universal fields above.

### Universal History
```
GET /history/{symbol}?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```
- Omitting dates returns the service-default lookback window.
- Each entry mirrors the quote schema and keeps `adjclose` in sync with `close` whenever the upstream data does not provide an adjusted figure.

**History response example**
```json
{
  "symbol": "VNINDEX",
  "history": [
    {
      "date": "2025-09-15",
      "open": 1250.4,
      "high": 1260.1,
      "low": 1242.8,
      "close": 1255.6,
      "adjclose": 1255.6,
      "volume": 125678900
    }
  ],
  "currency": "VND",
  "data_source": "VN_MARKET"
}
```

## Asset Classification Reference

| Asset Type | asset_class       | asset_sub_class  |
|------------|-------------------|------------------|
| GOLD       | Commodity          | Precious Metal   |
| STOCK      | Equity             | Stock            |
| FUND       | Investment Fund    | Mutual Fund      |
| INDEX      | Index              | Market Index     |
| OTHER      | Existing mappings  | Existing values  |

The service internally maintains constant mappings so responses never repeat hard-coded literals. Any new asset types inherit their class/sub-class from this configuration.

## Standard Field Reference

- `symbol`: Market identifier for the instrument.
- `asset_type`: Detected category (STOCK, FUND, INDEX, GOLD, ...).
- `asset_class` / `asset_sub_class`: Normalized classification per the table above.
- `currency`: Pricing currency; defaults to `"VND"` unless the source explicitly provides another currency.
- `data_source`: Always `"VN_MARKET"`.
- `history[]`: Time-ordered candles matching the quote schema.
- Provider extensions: Additional keys (e.g., `buy_price`, `sell_price`) may appear but never replace the universal fields.

## Error Handling

```
404 Not Found   – Unknown symbol
400 Bad Request – Invalid parameters (dates, formats, etc.)
500 Server Error – Upstream or internal failure
```
All errors return `{ "detail": "message" }` bodies.

## Usage Examples

### cURL
```bash
# Health
curl http://127.0.0.1:8765/health

# Search by keyword
curl "http://127.0.0.1:8765/search?query=gold"

# Direct symbol lookup
curl http://127.0.0.1:8765/search/VNM

# Latest quote
curl http://127.0.0.1:8765/quote/SSISCA

# Historical window
curl "http://127.0.0.1:8765/history/VNINDEX?start_date=2025-09-01&end_date=2025-09-30"
```

### Python
```python
import requests

BASE_URL = "http://127.0.0.1:8765"

quote = requests.get(f"{BASE_URL}/quote/VNM").json()
print(f"{quote['symbol']} ({quote['asset_type']}): {quote['close']} {quote['currency']}")

history = requests.get(
    f"{BASE_URL}/history/VNINDEX",
    params={"start_date": "2025-09-01", "end_date": "2025-09-30"}
).json()
print(f"Loaded {len(history['history'])} candles for {history['symbol']}")
```

## Integration Best Practices

1. Validate symbols via `/search` before invoking `/quote` or `/history`.
2. Cache search results and slow-moving instruments to reduce repeated upstream calls.
3. Mirror the response schema in downstream systems to benefit from future asset additions without code changes.
4. Apply retry logic for transient failures and back off when upstream sources throttle.

## Supplemental References

- Service README: high-level deployment details.
- `docs/VNSTOCK_COMMANDS_REFERENCE.md`: raw command catalogue for vnstock integrations.
