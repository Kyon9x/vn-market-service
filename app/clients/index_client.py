from vnstock import Quote
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import pandas as pd
from app.cache import get_historical_cache, get_rate_limiter, get_ttl_manager

logger = logging.getLogger(__name__)

class IndexClient:
    def __init__(self, cache_manager=None, memory_cache=None):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
        
        # Smart caching components
        self.historical_cache = get_historical_cache()
        self.rate_limiter = get_rate_limiter()
        self.ttl_manager = get_ttl_manager()
    
    def get_index_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch index history with incremental caching support."""
        # Try incremental caching first
        if self.historical_cache:
            try:
                return self._get_index_history_incremental(symbol, start_date, end_date)
            except Exception as e:
                logger.warning(f"Incremental caching failed for {symbol}, falling back to full fetch: {e}")
        
        # Fallback to full fetch
        return self._fetch_index_history_raw(symbol, start_date, end_date)
    
    def _get_index_history_incremental(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch index history using incremental caching."""
        # Check what dates are already cached
        cached_dates = self.historical_cache.get_cached_dates(symbol, start_date, end_date, "INDEX")
        
        # Calculate missing date ranges
        missing_ranges = self.historical_cache.calculate_missing_date_ranges(
            start_date=start_date,
            end_date=end_date,
            cached_dates=cached_dates
        )
        
        # If no missing ranges, return cached data
        if not missing_ranges:
            logger.info(f"All historical data for {symbol} found in cache")
            cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, "INDEX")
            return cached_data
        
        # Fetch missing ranges
        logger.info(f"Fetching {len(missing_ranges)} missing date ranges for {symbol}")
        all_new_records = []
        
        for missing_start, missing_end in missing_ranges:
            records = self._fetch_index_history_raw(symbol, missing_start, missing_end)
            if records:
                all_new_records.extend(records)
        
        # Store new records in cache first (real data takes priority)
        if all_new_records:
            self.historical_cache.store_historical_records(symbol, "INDEX", all_new_records)
        
        # Mark all fetched ranges as attempted (creates null records for no-data dates)
        for missing_start, missing_end in missing_ranges:
            self.historical_cache.mark_date_range_as_fetched(symbol, "INDEX", missing_start, missing_end)
        
        # Merge with existing cached data and return
        cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, "INDEX")
        all_data = self.historical_cache.merge_historical_data(cached_data, all_new_records)
        
        return all_data
    
    def _fetch_index_history_raw(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch index history from API."""
        try:
            # Rate limiting
            if self.rate_limiter:
                self.rate_limiter.wait_for_slot()
            
            quote = Quote(symbol=symbol, source='VCI')
            history_df = quote.history(start=start_date, end=end_date)
            
            # Record API call for rate limiting
            if self.rate_limiter:
                self.rate_limiter.record_call('index_history')
            
            if history_df is None or history_df.empty:
                return []
            
            history = []
            for _, row in history_df.iterrows():
                date_val = row.get("time") or row.get("tradingDate")
                if pd.isna(date_val):
                    continue
                    
                date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                
                open_val = float(row.get("open", 0.0)) if not pd.isna(row.get("open")) else 0.0
                high_val = float(row.get("high", 0.0)) if not pd.isna(row.get("high")) else 0.0
                low_val = float(row.get("low", 0.0)) if not pd.isna(row.get("low")) else 0.0
                close_val = float(row.get("close", 0.0)) if not pd.isna(row.get("close")) else 0.0
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
            logger.error(f"Error fetching index history for {symbol}: {e}")
            return []
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Get latest index quote with smart caching and rate limiting."""
        # Check memory cache first (will use 1-hour TTL automatically)
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "INDEX")
            if cached_quote:
                logger.debug(f"Using cached index quote for {symbol}")
                return cached_quote
        
        # Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "INDEX")
            if cached_quote:
                logger.debug(f"Using persistent cached index quote for {symbol}")
                # Also store in memory cache for faster access (will use 1-hour TTL)
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "INDEX", cached_quote)
                return cached_quote
        
        # Rate limiting before API call
        if self.rate_limiter:
            self.rate_limiter.wait_for_slot()
        
        # Try to fetch current quote, catch API exceptions separately
        quote_df = None
        today = datetime.now().strftime("%Y-%m-%d")
        
        try:
            quote = Quote(symbol=symbol, source='VCI')
            quote_df = quote.history(start=today, end=today)
            
            # Record API call for rate limiting
            if self.rate_limiter:
                self.rate_limiter.record_call('index_latest_quote')
        except Exception as e:
            logger.warning(f"API call failed for index {symbol}: {e}, will try fallback")
            quote_df = None
        
        # Check if we got valid data, otherwise use fallback
        if quote_df is None or quote_df.empty:
            logger.debug(f"No current data for index {symbol}, checking historical fallback")
            
            # Fallback 1: Check historical cache for most recent record
            if self.historical_cache:
                recent_record = self.historical_cache.get_most_recent_record(symbol, 'INDEX', lookback_days=30)
                if recent_record:
                    logger.info(f"Using historical fallback for index {symbol} from {recent_record.get('date')}")
                    # Cache this fallback quote
                    if self.memory_cache:
                        self.memory_cache.set_quote(symbol, "INDEX", recent_record)
                    if self.cache_manager and self.ttl_manager:
                        ttl = self.ttl_manager.get_ttl_for_asset("INDEX")
                        self.cache_manager.set_quote(symbol, "INDEX", recent_record, ttl_seconds=ttl)
                    return recent_record
                
                # Fallback 2: Fetch last week's data to populate cache
                logger.info(f"No historical cache for index {symbol}, fetching last week's data")
                one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                today_str = datetime.now().strftime("%Y-%m-%d")
                history = self.get_index_history(symbol, one_week_ago, today_str)
                
                if history:
                    most_recent = history[-1]
                    logger.info(f"Using last week's most recent data for index {symbol} from {most_recent.get('date')}")
                    # Ensure symbol is present in the fallback record
                    if "symbol" not in most_recent:
                        most_recent["symbol"] = symbol
                    # Cache this fallback quote
                    if self.memory_cache:
                        self.memory_cache.set_quote(symbol, "INDEX", most_recent)
                    if self.cache_manager and self.ttl_manager:
                        ttl = self.ttl_manager.get_ttl_for_asset("INDEX")
                        self.cache_manager.set_quote(symbol, "INDEX", most_recent, ttl_seconds=ttl)
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
            
            open_val = float(info.get("open", 0.0)) if not pd.isna(info.get("open")) else 0.0
            high_val = float(info.get("high", 0.0)) if not pd.isna(info.get("high")) else 0.0
            low_val = float(info.get("low", 0.0)) if not pd.isna(info.get("low")) else 0.0
            close_val = float(info.get("close", 0.0)) if not pd.isna(info.get("close")) else 0.0
            volume_val = float(info.get("volume", 0.0)) if not pd.isna(info.get("volume")) else 0.0
            
            quote_data = {
                "symbol": symbol,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "adjclose": close_val,  # For indices, adjclose is typically the same as close
                "volume": volume_val,
                "date": date_str
            }
            
            # Cache the quote (memory cache will auto-use 1-hour TTL for INDEX)
            if self.memory_cache:
                self.memory_cache.set_quote(symbol, "INDEX", quote_data)
            
            # Cache in persistent storage with TTL from TTL manager
            if self.cache_manager and self.ttl_manager:
                ttl = self.ttl_manager.get_ttl_for_asset("INDEX")
                self.cache_manager.set_quote(symbol, "INDEX", quote_data, ttl_seconds=ttl)
            
            return quote_data
        except Exception as e:
            logger.error(f"Error processing quote data for index {symbol}: {e}")
            return None
