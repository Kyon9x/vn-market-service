# Provider Call Logging Guide

## Overview
This implementation adds reusable provider call logging with `[provider=call]` tags across all data clients for easy filtering and monitoring.

## Architecture

### Core Component: `app/utils/provider_logger.py`
A reusable decorator-based logger that captures:
- Provider name (e.g., "vnstock")
- Method being called (e.g., "Quote.history")
- Execution time (in milliseconds)
- Success/Error status
- Custom metadata fields

### Log Format
```
[provider=call] [provider_name=vnstock] method=<method> status=<status> duration=<ms> [optional_metadata]
```

### Example Logs
```
[provider=call] [provider_name=vnstock] method=stock_client._fetch_stock_history_from_provider status=success duration=245ms
[provider=call] [provider_name=vnstock] method=fund_client._fetch_funds_listing_from_provider status=success duration=1234ms count=150
[provider=call] [provider_name=vnstock] method=gold_client._fetch_sjc_gold_from_provider status=success duration=156ms rows=1
[provider=call] [provider_name=vnstock] method=index_client._fetch_index_history_from_provider status=error duration=500ms error_type=TimeoutError
```

## Integration by Client

### StockClient (3 decorators)
1. `_fetch_stock_history_from_provider()` - Logs Quote.history() calls for historical data
2. `_fetch_latest_quote_from_provider()` - Logs Quote.history() calls for daily quotes
3. `_fetch_companies_from_provider()` - Logs Listing.symbols_by_exchange() calls

### FundClient (2 decorators)
1. `_fetch_funds_listing_from_provider()` - Logs Fund.listing() calls
2. `_fetch_fund_nav_report_from_provider()` - Logs Fund.nav_report() calls (used for search, history, latest nav)

### GoldClient (3 decorators)
1. `_fetch_sjc_gold_from_provider()` - Logs sjc_gold_price() calls
2. `_fetch_btmc_gold_from_provider()` - Logs btmc_goldprice() calls
3. `_fetch_msn_gold_from_provider()` - Logs Vnstock.world_index() calls for MSN gold

### IndexClient (2 decorators)
1. `_fetch_index_history_from_provider()` - Logs Quote.history() calls for historical index data
2. `_fetch_latest_index_quote_from_provider()` - Logs Quote.history() calls for daily index quotes

## Usage in Logs

### Filtering for Provider Calls
```bash
# View all provider calls
grep "\[provider=call\]" application.log

# Filter by specific provider
grep "\[provider=call\].*vnstock" application.log

# Filter by method
grep "\[provider=call\].*Fund.listing" application.log

# Filter by status
grep "\[provider=call\].*status=error" application.log

# Filter by duration (slow calls)
grep "\[provider=call\].*duration=[1-9][0-9][0-9][0-9]" application.log
```

## Extending for New Providers

When integrating a new data provider (e.g., different stock API, forex provider, etc.):

```python
from app.utils.provider_logger import log_provider_call

@log_provider_call(
    provider_name="your_provider_name",
    metadata_fields={
        "symbol": lambda r: r.get("symbol") if isinstance(r, dict) else None,
        "count": lambda r: len(r) if isinstance(r, list) else 0
    }
)
def _fetch_data_from_provider(self, symbol: str):
    # Your API call here
    return api_client.fetch_data(symbol)
```

## Benefits

1. **Performance Monitoring**: Track execution time for each provider call to identify slow APIs
2. **Error Tracking**: Easily identify which provider calls are failing
3. **Debugging**: Understand which providers are being used in your application
4. **Metrics**: Count provider call frequency and patterns
5. **Reusable**: Simple to add to new providers and data sources
6. **Centralized**: All provider logging follows the same format for consistency

## Configuration

Logging configuration is controlled by the main app logging settings in `app/main.py`:

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

Provider logs are emitted at INFO level for successful calls and WARNING level for errors.
