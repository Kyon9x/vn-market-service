from vnstock import Quote, Listing
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import logging
import pandas as pd
import sys
import os
from app.utils.provider_logger import log_provider_call

# Add current directory to Python path for imports
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Import shared utilities
try:
    from app.utils.market_time_utils import is_weekday, should_update_data
    from app.utils.data_freshness import check_and_update_latest_data
    _has_shared_utils = True
except ImportError as e:
    _has_shared_utils = False

# Import smart caching utilities
try:
    from app.cache import get_stock_historical_cache, get_rate_limiter, get_ttl_manager
    _has_smart_cache = True
except ImportError:
    _has_smart_cache = False

logger = logging.getLogger(__name__)

class StockClient:
    def __init__(self, cache_manager=None, memory_cache=None):
        self._quote = None
        self._listing = Listing()
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
        self._companies_cache = None
        self._cache_timestamp = None
        
        # Initialize smart caching components
        if _has_smart_cache:
            self.historical_cache = get_stock_historical_cache()
            self.rate_limiter = get_rate_limiter()
            self.ttl_manager = get_ttl_manager()
        else:
            self.historical_cache = None
            self.rate_limiter = None
            self.ttl_manager = None
        
        # Exchange mapping for compatibility
        self.exchange_mapping = {
            'HSX': 'HOSE',  # Ho Chi Minh Stock Exchange
            'HNX': 'HNX',   # Hanoi Stock Exchange  
            'UPCOM': 'UPCOM' # Unlisted Public Company Market
        }
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"symbol": lambda r: r[0].get("symbol") if r else None})
    def _fetch_stock_history_from_provider(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        quote = Quote(symbol=symbol, source='VCI')
        history_df = quote.history(start=start_date, end=end_date)
        return history_df

    def _check_and_update_latest_price_fallback(self, symbol: str, cached_data: List[Dict]):
        """Fallback method for latest price check when shared utils not available."""
        if not cached_data:
            return
        
        now = datetime.now()
        latest_record = cached_data[-1]  # Most recent
        
        # Simple weekday/weekend logic without shared utils
        if now.weekday() < 5:  # Monday=0, Friday=4
            # Weekday: Update if older than 30 minutes
            try:
                last_update = datetime.strptime(latest_record['date'], "%Y-%m-%d")
                if len(latest_record['date']) == 10:  # YYYY-MM-DD format
                    last_update = last_update.replace(hour=23, minute=59, second=59)
                
                if (now - last_update).total_seconds() > (30 * 60):
                    self._fetch_and_store_latest_price_fallback(symbol, now)
            except ValueError:
                self._fetch_and_store_latest_price_fallback(symbol, now)
        else:
            # Weekend: Ensure Friday data
            try:
                last_date = datetime.strptime(latest_record['date'], "%Y-%m-%d")
                if last_date.weekday() != 4:  # Not Friday
                    self._fetch_and_store_friday_price_fallback(symbol, now)
            except ValueError:
                self._fetch_and_store_friday_price_fallback(symbol, now)
    
    def _fetch_and_store_latest_price_fallback(self, symbol: str, dt: datetime):
        """Fallback method to fetch and store latest price."""
        try:
            today_str = dt.strftime("%Y-%m-%d")
            fresh_data = self._fetch_stock_history_raw(symbol, today_str, today_str)
            
            if fresh_data and self.historical_cache:
                self.historical_cache.store_historical_records(symbol, 'STOCK', fresh_data)
                logger.info(f"Updated latest stock data for {symbol}")
        except Exception as e:
            logger.error(f"Error updating latest stock data for {symbol}: {e}")
    
    def _fetch_and_store_friday_price_fallback(self, symbol: str, dt: datetime):
        """Fallback method to fetch and store Friday price."""
        try:
            # Get most recent Friday
            days_since_friday = (dt.weekday() - 4) % 7  # Friday=4
            friday = dt - timedelta(days=days_since_friday)
            friday_str = friday.strftime("%Y-%m-%d")
            
            fresh_data = self._fetch_stock_history_raw(symbol, friday_str, friday_str)
            
            if fresh_data and self.historical_cache:
                self.historical_cache.store_historical_records(symbol, 'STOCK', fresh_data)
                logger.info(f"Updated Friday stock data for {symbol}")
        except Exception as e:
            logger.error(f"Error updating Friday stock data for {symbol}: {e}")

    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Get stock history with simple cache → vnstock → store flow."""
        
        # 1. Check cache first
        if self.historical_cache:
            try:
                cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, 'STOCK')
                
                if cached_data:
                    # 2. Check latest price update using shared utility
                    if _has_shared_utils:
                        check_and_update_latest_data(
                            symbol=symbol,
                            asset_type='STOCK',
                            cached_data=cached_data,
                            client_instance=self,
                            update_threshold_minutes=30
                        )
                    else:
                        # Fallback: Simple latest price check without shared utils
                        self._check_and_update_latest_price_fallback(symbol, cached_data)
                    
                    return cached_data
            except Exception as e:
                logger.warning(f"Cache check failed, falling back to direct fetch: {e}")
        
        # 3. No cache - fetch from vnstock and store
        fresh_data = self._fetch_stock_history_raw(symbol, start_date, end_date)
        
        if fresh_data and self.historical_cache:
            try:
                self.historical_cache.store_historical_records(symbol, 'STOCK', fresh_data)
                logger.info(f"Fetched and stored {len(fresh_data)} stock records for {symbol}")
            except Exception as e:
                logger.warning(f"Failed to store fresh data in cache: {e}")
        
        return fresh_data
    
    def _get_stock_history_incremental(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Get stock history using incremental caching."""
        # Check what dates are already cached
        cached_dates = self.historical_cache.get_cached_dates(symbol, start_date, end_date, 'STOCK')
        
        # Calculate missing date ranges
        missing_ranges = self.historical_cache.calculate_missing_date_ranges(
            start_date=start_date,
            end_date=end_date,
            cached_dates=cached_dates
        )
        
        # If no missing ranges, return cached data
        if not missing_ranges:
            logger.info(f"All historical data for {symbol} found in cache")
            cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, 'STOCK')
            return cached_data
        
        # Fetch only missing data with rate limiting
        all_new_records = []
        fetched_ranges = []
        
        for missing_start, missing_end in missing_ranges:
            logger.info(f"Fetching missing stock data for {symbol}: {missing_start} to {missing_end}")
            
            # Apply rate limiting
            if self.rate_limiter:
                self.rate_limiter.wait_for_slot()
            
            # Fetch missing data
            new_data = self._fetch_stock_history_raw(symbol, missing_start, missing_end)
            
            # Store in cache
            if new_data:
                self.historical_cache.store_historical_records(symbol, 'STOCK', new_data)
                all_new_records.extend(new_data)
                
                # Record API call for rate limiting
                if self.rate_limiter:
                    self.rate_limiter.record_call('stock_history')
            
            # Track fetched range
            fetched_ranges.append((missing_start, missing_end))
        
        # Mark all fetched ranges as attempted (creates null records for no-data dates)
        for missing_start, missing_end in fetched_ranges:
            self.historical_cache.mark_date_range_as_fetched(symbol, 'STOCK', missing_start, missing_end)
        
        # Merge cached and new data
        cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, 'STOCK')
        return self.historical_cache.merge_historical_data(cached_data, all_new_records)
    
    def _fetch_stock_history_raw(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch stock history from API without caching logic."""
        try:
            history_df = self._fetch_stock_history_from_provider(symbol, start_date, end_date)
            
            if history_df is None or history_df.empty:
                return []
            
            history = []
            for _, row in history_df.iterrows():
                date_val = row.get("time") or row.get("tradingDate")
                if pd.isna(date_val):
                    continue
                    
                date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                
                # Convert from shortened VND format (e.g., 12) to actual VND (e.g., 12000)
                open_val = float(row.get("open", 0.0)) * 1000 if not pd.isna(row.get("open")) else 0.0
                high_val = float(row.get("high", 0.0)) * 1000 if not pd.isna(row.get("high")) else 0.0
                low_val = float(row.get("low", 0.0)) * 1000 if not pd.isna(row.get("low")) else 0.0
                close_val = float(row.get("close", 0.0)) * 1000 if not pd.isna(row.get("close")) else 0.0
                volume_val = float(row.get("volume", 0.0)) if not pd.isna(row.get("volume")) else 0.0
                
                history.append({
                    "symbol": symbol,
                    "date": date_str,
                    "nav": close_val,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "close": close_val,
                    "adjclose": close_val,
                    "volume": volume_val
                })
            
            return history
        except Exception as e:
            logger.error(f"Error fetching stock history for {symbol}: {e}")
            return []
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"symbol": lambda r: r.get("symbol") if isinstance(r, dict) else None})
    def _fetch_latest_quote_from_provider(self, symbol: str) -> Optional[Dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        quote = Quote(symbol=symbol, source='VCI')
        quote_df = quote.history(start=today, end=today)
        return quote_df
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Get latest stock quote with asset-specific TTL and rate limiting."""
        # Check memory cache first (now uses 1-hour TTL for stocks)
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "STOCK")
            if cached_quote:
                logger.debug(f"Using cached quote for {symbol}")
                return cached_quote
        
        # Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "STOCK")
            if cached_quote:
                logger.debug(f"Using persistent cached quote for {symbol}")
                # Also store in memory cache for faster access (will use 1-hour TTL)
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "STOCK", cached_quote)
                return cached_quote
        
        # Apply rate limiting before API call
        if self.rate_limiter:
            self.rate_limiter.wait_for_slot()
        
        # Try to fetch current quote, catch API exceptions separately
        quote_df = None
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Apply rate limiting before API call
        if self.rate_limiter:
            self.rate_limiter.wait_for_slot()
        
        # Try to fetch current quote, catch API exceptions separately
        quote_df = None
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            quote_df = self._fetch_latest_quote_from_provider(symbol)
            
            # Record API call for rate limiting
            if self.rate_limiter:
                self.rate_limiter.record_call('stock_latest_quote')
        except Exception as e:
            logger.warning(f"API call failed for {symbol}: {e}, will try fallback")
            quote_df = None
        
        # Check if we got valid data, otherwise use fallback
        if quote_df is None or quote_df.empty:
            logger.debug(f"No current data for {symbol}, checking historical fallback")
            
            # Fallback 1: Check historical cache for most recent record
            if self.historical_cache:
                recent_record = self.historical_cache.get_most_recent_record(symbol, 'STOCK', lookback_days=30)
                if recent_record:
                    logger.info(f"Using historical fallback for {symbol} from {recent_record.get('date')}")
                    # Cache this fallback quote
                    if self.memory_cache:
                        self.memory_cache.set_quote(symbol, "STOCK", recent_record)
                    if self.cache_manager and self.ttl_manager:
                        ttl = self.ttl_manager.get_ttl_for_asset("STOCK")
                        self.cache_manager.set_quote(symbol, "STOCK", recent_record, ttl_seconds=ttl)
                    return recent_record
                
                # Fallback 2: Fetch last week's data to populate cache
                logger.info(f"No historical cache for {symbol}, fetching last week's data")
                one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                today_str = datetime.now().strftime("%Y-%m-%d")
                history = self.get_stock_history(symbol, one_week_ago, today_str)
                
                if history:
                    most_recent = history[-1]
                    # Ensure symbol is in the record
                    if 'symbol' not in most_recent:
                        most_recent['symbol'] = symbol
                    logger.info(f"Using last week's most recent data for {symbol} from {most_recent.get('date')}")
                    # Cache this fallback quote
                    if self.memory_cache:
                        self.memory_cache.set_quote(symbol, "STOCK", most_recent)
                    if self.cache_manager and self.ttl_manager:
                        ttl = self.ttl_manager.get_ttl_for_asset("STOCK")
                        self.cache_manager.set_quote(symbol, "STOCK", most_recent, ttl_seconds=ttl)
                    return most_recent
            
            return None
        
        # Process successful API response
        try:
            info = quote_df.iloc[-1]
            date_val = info.get("time") or info.get("tradingDate")
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val) if date_val else datetime.now().strftime("%Y-%m-%d")
            
            # Convert from shortened VND format (e.g., 12) to actual VND (e.g., 12000)
            open_val = float(info.get("open", 0.0)) * 1000 if not pd.isna(info.get("open")) else 0.0
            high_val = float(info.get("high", 0.0)) * 1000 if not pd.isna(info.get("high")) else 0.0
            low_val = float(info.get("low", 0.0)) * 1000 if not pd.isna(info.get("low")) else 0.0
            close_val = float(info.get("close", 0.0)) * 1000 if not pd.isna(info.get("close")) else 0.0
            volume_val = float(info.get("volume", 0.0)) if not pd.isna(info.get("volume")) else 0.0
            
            quote_data = {
                "symbol": symbol,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "adjclose": close_val,  # For stocks, adjclose is typically the same as close
                "volume": volume_val,
                "date": date_str
            }
            
            # Cache the quote (memory cache will automatically use 1-hour TTL for STOCK)
            if self.memory_cache:
                self.memory_cache.set_quote(symbol, "STOCK", quote_data)
            if self.cache_manager:
                # Get TTL from TTL manager (1 hour for stocks)
                ttl = self.ttl_manager.get_ttl_for_asset("STOCK") if self.ttl_manager else 3600
                self.cache_manager.set_quote(symbol, "STOCK", quote_data, ttl_seconds=ttl)
            
            # Record API call for rate limiting
            if self.rate_limiter:
                self.rate_limiter.record_call('stock_quote')
            
            return quote_data
        except Exception as e:
            logger.error(f"Error processing quote data for {symbol}: {e}")
            return None
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"count": lambda r: len(r) if r is not None else 0})
    def _fetch_companies_from_provider(self) -> Optional[pd.DataFrame]:
        return self._listing.symbols_by_exchange()
    
    def _get_companies_df(self):
        """Get companies DataFrame with caching and filtering."""
        # Simple in-memory cache for companies data (refresh every hour)
        import time
        current_time = time.time()
        
        if (self._companies_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < 3600):  # 1 hour cache
            return self._companies_cache
        
        try:
            companies_df = self._fetch_companies_from_provider()
            
            # Filter for active stocks only: type='STOCK' and exchange != 'DELISTED'
            if companies_df is not None and not companies_df.empty:
                # Apply filters
                filtered_df = companies_df[
                    (companies_df['type'] == 'STOCK') & 
                    (companies_df['exchange'] != 'DELISTED')
                ].copy()
                
                self._companies_cache = filtered_df
                self._cache_timestamp = current_time
                logger.info(f"Refreshed companies cache: {len(filtered_df)} active stocks (filtered from {len(companies_df)} total)")
                return filtered_df
            else:
                self._companies_cache = companies_df
                self._cache_timestamp = current_time
                return companies_df
                
        except Exception as e:
            logger.error(f"Error fetching companies data: {e}")
            return self._companies_cache  # Return stale cache if available
    
    def search_stock(self, symbol: str) -> Optional[Dict]:
        # Check cache first
        if self.cache_manager:
            cached_asset = self.cache_manager.get_asset(symbol)
            if cached_asset and cached_asset.get('asset_type') == 'STOCK':
                logger.debug(f"Using cached asset info for {symbol}")
                return {
                    "symbol": cached_asset['symbol'],
                    "company_name": cached_asset['name'],
                    "exchange": cached_asset.get('exchange', ''),
                    "industry": cached_asset['metadata'].get('industry', '') if cached_asset.get('metadata') else '',
                    "company_type": cached_asset['metadata'].get('company_type', '') if cached_asset.get('metadata') else ''
                }
        
        try:
            # Try to get company info from listing (with caching)
            companies_df = self._get_companies_df()
            if companies_df is not None and not companies_df.empty:
                company_row = companies_df[companies_df['symbol'] == symbol]
                if not company_row.empty:
                    info = company_row.iloc[0]
                    company_name = str(info.get("organ_name", symbol))
                    industry = str(info.get("organ_type", ""))
                    company_type = str(info.get("exchange", ""))  # Use exchange as company_type fallback
                    
                    raw_exchange = str(info.get("exchange", ""))
                    mapped_exchange = self.exchange_mapping.get(raw_exchange, raw_exchange)
                    
                    result = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": mapped_exchange,
                        "industry": industry,
                        "company_type": company_type
                    }
                    
                    # Cache the result
                    if self.cache_manager:
                        self.cache_manager.set_asset(
                            symbol=symbol,
                            name=company_name,
                            asset_type="STOCK",
                            asset_class="Equity",
                            asset_sub_class="Stock",
                            exchange=mapped_exchange,
                            currency="VND",
                            metadata={"industry": industry, "company_type": company_type}
                        )
                    
                    return result
            
            # Stock not found in listing
            return None
        except Exception as e:
            logger.error(f"Error searching stock {symbol}: {e}")
            return None
    
    def search_stocks_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """Search stocks by partial name match (case-insensitive)."""
        # Check cache first
        if self.cache_manager:
            cached_results = self.cache_manager.search_assets_by_name(query, limit)
            stock_results = [r for r in cached_results if r.get('asset_type') == 'STOCK']
            if stock_results:
                logger.debug(f"Using cached search results for stocks '{query}'")
                return [
                    {
                        "symbol": r['symbol'],
                        "company_name": r['name'],
                        "exchange": r.get('exchange', ''),
                        "industry": r.get('metadata', {}).get('industry', '') if r.get('metadata') else '',
                        "company_type": r.get('metadata', {}).get('company_type', '') if r.get('metadata') else ''
                    }
                    for r in stock_results[:limit]
                ]
        
        try:
            companies_df = self._get_companies_df()
            if companies_df is None or companies_df.empty:
                return []
            
            query_lower = query.lower()
            results = []
            
            for _, row in companies_df.iterrows():
                symbol = str(row.get("symbol", ""))
                company_name = str(row.get("organ_name", ""))
                
                # Match on symbol or company name
                if query_lower in symbol.lower() or query_lower in company_name.lower():
                    industry = str(row.get("organ_short_name", ""))
                    company_type = str(row.get("exchange", ""))  # Use exchange as company_type fallback
                    
                    raw_exchange = str(row.get("exchange", ""))
                    mapped_exchange = self.exchange_mapping.get(raw_exchange, raw_exchange)
                    
                    result = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": mapped_exchange,
                        "industry": industry,
                        "company_type": company_type
                    }
                    results.append(result)
                    
                    # Cache individual asset
                    if self.cache_manager:
                        self.cache_manager.set_asset(
                            symbol=symbol,
                            name=company_name,
                            asset_type="STOCK",
                            asset_class="Equity",
                            asset_sub_class="Stock",
                            exchange=mapped_exchange,
                            currency="VND",
                            metadata={"industry": industry, "company_type": company_type}
                        )
                    
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as e:
            logger.error(f"Error searching stocks by name '{query}': {e}")
            return []
