from vnstock.explorer.misc import sjc_gold_price
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import pandas as pd
import sqlite3
from pathlib import Path
from app.cache import get_gold_historical_cache, get_rate_limiter, get_ttl_manager
from app.utils.provider_logger import log_provider_call

# Import LazyFetchManager separately to avoid circular import issues
try:
    from app.cache.lazy_fetch_manager import LazyFetchManager
    LAZY_FETCH_AVAILABLE = True
except ImportError:
    LazyFetchManager = None
    LAZY_FETCH_AVAILABLE = False

logger = logging.getLogger(__name__)

class GoldClient:
    # Provider configurations - Only SJC as source of truth
    PROVIDERS = {
        "sjc": {
            "name": "Saigon Jewelry Company",
            "symbols": ["VN.GOLD", "VN.GOLD.C"],
            "api_func": "sjc_gold_price"
        }
    }
    
    def __init__(self, cache_manager=None, memory_cache=None, db_path: str = "db/assets.db"):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
        self.db_path = Path(db_path)
        
        # Smart caching components
        self.historical_cache = get_gold_historical_cache()
        self.rate_limiter = get_rate_limiter()
        self.ttl_manager = get_ttl_manager()
        
        # Lazy fetch manager for background data enrichment
        self.lazy_fetch_manager = LazyFetchManager(db_path=db_path, gold_client=self) if LazyFetchManager else None
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"rows": lambda r: len(r) if r is not None else 0})
    def _fetch_sjc_gold_from_provider(self, date: str):
        try:
            result = sjc_gold_price(date=date)
            # Handle case where vnstock returns Series instead of DataFrame
            if result is not None and hasattr(result, 'to_frame'):
                return result.to_frame()
            return result
        except Exception as e:
            logger.error(f"Error fetching SJC gold data for {date}: {e}")
            return None
    
    
    
    def parse_symbol(self, symbol: str) -> Tuple[str, str]:
        """
        Parse gold symbol and return (normalized_symbol, provider).
        Supports VN.GOLD (Lượng) and VN.GOLD.C (Chỉ) symbols.
        Raises ValueError if symbol is not a valid gold provider symbol.
        """
        symbol_upper = symbol.upper()
        
        for provider, config in self.PROVIDERS.items():
            if symbol_upper in [s.upper() for s in config["symbols"]]:
                # Normalize to base symbol for data fetching (always use VN.GOLD for storage)
                normalized_symbol = "VN.GOLD" if symbol_upper.endswith('.C') else symbol_upper
                return normalized_symbol, provider
        
        raise ValueError(f"Invalid gold symbol: {symbol}. Valid symbols: {self._get_all_valid_symbols()}")
    
    def _get_all_valid_symbols(self) -> List[str]:
        """Get all valid gold symbols across providers."""
        all_symbols = []
        for provider_config in self.PROVIDERS.values():
            all_symbols.extend(provider_config["symbols"])
        return all_symbols
    
    def _get_historical_from_database(self, start_date: str, end_date: str, requested_symbol: Optional[str] = None) -> List[Dict]:
        """
        Fetch historical gold data directly from database.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            requested_symbol: The originally requested symbol (for alias mapping)
            
        Returns:
            List of historical gold data
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT symbol, date, open, high, low, close, adjclose, 
                           volume, nav, buy_price, sell_price
                    FROM historical_records 
                    WHERE asset_type = 'GOLD' 
                    AND date BETWEEN ? AND ?
                    ORDER BY date ASC
                ''', (start_date, end_date))
                
                rows = cursor.fetchall()
                history = []
                
                for row in rows:
                    history.append({
                        "symbol": requested_symbol or row["symbol"],  # Use requested symbol for aliases
                        "date": row["date"],
                        "nav": float(row["nav"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "adjclose": float(row["adjclose"]),
                        "volume": float(row["volume"]),
                        "buy_price": float(row["buy_price"]) if row["buy_price"] is not None else None,
                        "sell_price": float(row["sell_price"]) if row["sell_price"] is not None else None
                    })
                
                logger.info(f"Retrieved {len(history)} gold records from database ({start_date} to {end_date})")
                return history
                
        except Exception as e:
            logger.error(f"Error fetching historical data from database: {e}")
            return []
    
    def _get_latest_from_database(self, symbol: str) -> Optional[Dict]:
        """
        Fetch latest gold data from database.
        
        Args:
            symbol: Gold symbol
            
        Returns:
            Latest gold data or None
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT symbol, date, open, high, low, close, adjclose,
                           volume, nav, buy_price, sell_price
                    FROM historical_records 
                    WHERE asset_type = 'GOLD' 
                    AND (symbol = ? OR symbol = 'VN.GOLD')
                    ORDER BY date DESC
                    LIMIT 1
                ''', (symbol,))
                
                row = cursor.fetchone()
                if row:
                    return {
                        "symbol": symbol,  # Return requested symbol
                        "date": row["date"],
                        "nav": float(row["nav"]),
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "adjclose": float(row["adjclose"]),
                        "volume": float(row["volume"]),
                        "buy_price": float(row["buy_price"]) if row["buy_price"] is not None else None,
                        "sell_price": float(row["sell_price"]) if row["sell_price"] is not None else None,
                        "currency": "VND"
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error fetching latest data from database: {e}")
            return None
    
    def _database_has_data(self, start_date: str, end_date: str) -> bool:
        """
        Check if database has complete data for the date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            True if complete data exists, False otherwise
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Count expected trading days (weekdays only)
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                expected_days = sum(1 for day in range((end_dt - start_dt).days + 1)
                                 if (start_dt + timedelta(days=day)).weekday() < 5)
                
                # Count actual records in database
                cursor.execute('''
                    SELECT COUNT(*) FROM historical_records 
                    WHERE asset_type = 'GOLD' 
                    AND date BETWEEN ? AND ?
                ''', (start_date, end_date))
                
                actual_days = cursor.fetchone()[0]
                
                # Consider complete if we have at least 80% of expected trading days
                completeness = actual_days / expected_days if expected_days > 0 else 0
                logger.debug(f"Database completeness: {actual_days}/{expected_days} ({completeness:.1%})")
                
                return completeness >= 0.8
                
        except Exception as e:
            logger.error(f"Error checking database completeness: {e}")
            return False
    
    def get_gold_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch historical gold prices using lazy fetch approach - return cached data immediately."""
        try:
            normalized_symbol, provider = self.parse_symbol(symbol)
            
            # Only SJC provider supported
            if provider != "sjc":
                logger.error(f"Unsupported provider: {provider}. Only SJC is supported.")
                return []
            
            # LAZY FETCH: Return cached data immediately
            return self._get_history_lazy_fetch(normalized_symbol, symbol, start_date, end_date)
            
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching gold history for {symbol}: {e}")
            return []
    
    def _get_history_lazy_fetch(self, normalized_symbol: str, original_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Simplified lazy fetch approach: Return cached data immediately.
        
        This method:
        1. Returns whatever cached data exists RIGHT NOW
        2. Triggers background fetch if needed
        3. Applies unit conversion if needed
        4. Never blocks waiting for API calls
        """
        try:
            # Step 1: Get cached records immediately
            cached_records = self.historical_cache.get_cached_records(normalized_symbol, start_date, end_date, "GOLD")
            logger.info(f"Returning {len(cached_records)} cached records for {normalized_symbol}")
            
            # Step 2: Trigger background fetch if needed (non-blocking) - overlap detection disabled
            if self.lazy_fetch_manager and self._needs_lazy_fetch(start_date, end_date, cached_records):
                logger.info(f"Triggering lazy fetch for {normalized_symbol} ({start_date} to {end_date})")
                try:
                    self.lazy_fetch_manager.trigger_lazy_fetch(normalized_symbol, start_date, end_date, "GOLD")
                except Exception as e:
                    logger.warning(f"Failed to trigger lazy fetch: {e}")
            
            # Step 3: Apply unit conversion and return immediately
            return self._apply_unit_conversion(cached_records, original_symbol)
            
        except Exception as e:
            logger.error(f"Error in lazy fetch for {normalized_symbol}: {e}")
            # Fallback to empty response rather than blocking
            return []
    
    def _needs_lazy_fetch(self, start_date: str, end_date: str, cached_records: List[Dict]) -> bool:
        """
        Simple determination if lazy fetch is needed.
        
        Args:
            start_date: Start date string
            end_date: End date string
            cached_records: Currently cached records
            
        Returns:
            True if lazy fetch should be triggered
        """
        if not cached_records:
            return True  # No data at all, definitely need fetch
        
        # Calculate expected trading days
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        expected_days = sum(1 for day in range((end_dt - start_dt).days + 1)
                          if (start_dt + timedelta(days=day)).weekday() < 5)
        
        # If we have less than 60% of expected data, trigger lazy fetch
        completeness = len(cached_records) / expected_days if expected_days > 0 else 0
        return completeness < 0.6
    
    def _should_trigger_lazy_fetch(self, symbol: str, start_date: str, end_date: str, cached_records: List[Dict]) -> bool:
        """
        Comprehensive check before triggering lazy fetch to avoid duplicates and overlaps.
        
        Args:
            symbol: Asset symbol
            start_date: Start date string
            end_date: End date string
            cached_records: Currently cached records
            
        Returns:
            True if lazy fetch should be triggered
        """
        # Quick check: Is lazy fetch manager available?
        if not self.lazy_fetch_manager:
            return False
            
        # Quick check: Is data already sufficient?
        if not self._needs_lazy_fetch(start_date, end_date, cached_records):
            return False
            
        # Quick check: Is this range already being fetched?
        fetch_key = f"{symbol}_{start_date}_{end_date}"
        if fetch_key in self.lazy_fetch_manager._active_fetches:
            logger.debug(f"Lazy fetch already active for {fetch_key}")
            return False
            
        # DISABLED: Overlap detection causes deadlocks, using basic duplicate prevention only
        # if self.lazy_fetch_manager._check_overlapping_ranges(symbol, start_date, end_date):
        #     logger.info(f"Requested range overlaps with active lazy fetch for {symbol} ({start_date} to {end_date})")
        #     return False
            
        return True
    
    def _get_history_cache_first(self, normalized_symbol: str, original_symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch historical gold prices using cache-first incremental approach.
        
        This method:
        1. Checks what dates are already cached
        2. Identifies missing date ranges
        3. Fetches only missing data from API
        4. Merges cached and new data
        """
        try:
            # Step 1: Get cached dates
            cached_dates = self.historical_cache.get_cached_dates(normalized_symbol, start_date, end_date, "GOLD")
            logger.info(f"Found {len(cached_dates)} cached dates for {normalized_symbol} ({start_date} to {end_date})")
            
            # Step 2: Calculate missing date ranges
            missing_ranges = self.historical_cache.calculate_missing_date_ranges(start_date, end_date, cached_dates)
            
            if not missing_ranges:
                # All data is cached, return cached records
                logger.info(f"All data cached for {normalized_symbol}, returning cached records")
                cached_records = self.historical_cache.get_cached_records(normalized_symbol, start_date, end_date, "GOLD")
                return self._apply_unit_conversion(cached_records, original_symbol)
            
            # Step 3: Decide fetch strategy
            total_days = (datetime.strptime(end_date, '%Y-%m-%d') - 
                         datetime.strptime(start_date, '%Y-%m-%d')).days + 1
            
            fetch_full_range = self.historical_cache.should_fetch_full_range(missing_ranges, total_days)
            
            if fetch_full_range:
                logger.info(f"Fetching full range for {normalized_symbol} (missing > 80% of data)")
                new_records = self._get_sjc_history(start_date, end_date)
            else:
                logger.info(f"Fetching {len(missing_ranges)} missing ranges for {normalized_symbol}")
                new_records = []
                for range_start, range_end in missing_ranges:
                    range_records = self._get_sjc_history(range_start, range_end)
                    new_records.extend(range_records)
            
            # Step 4: Store new records in historical cache
            if new_records:
                stored_count = self.historical_cache.store_historical_records(normalized_symbol, "GOLD", new_records)
                logger.info(f"Stored {stored_count} new records for {normalized_symbol}")
                
                # Mark date range as fetched (including weekends/holidays)
                self.historical_cache.mark_date_range_as_fetched(normalized_symbol, "GOLD", start_date, end_date)
            
            # Step 5: Get complete merged data
            cached_records = self.historical_cache.get_cached_records(normalized_symbol, start_date, end_date, "GOLD")
            merged_records = self.historical_cache.merge_historical_data(cached_records, new_records)
            
            # Step 6: Apply unit conversion if needed
            return self._apply_unit_conversion(merged_records, original_symbol)
            
        except Exception as e:
            logger.error(f"Error in cache-first history fetch for {normalized_symbol}: {e}")
            # Fallback to old method
            return self._get_historical_from_database(start_date, end_date, original_symbol)
    
    def _apply_unit_conversion(self, records: List[Dict], symbol: str) -> List[Dict]:
        """
        Apply unit conversion to records if symbol is VN.GOLD.C (Chỉ).
        
        Args:
            records: List of historical records
            symbol: Original symbol requested
            
        Returns:
            Records with unit conversion applied if needed
        """
        converted_records = []
        
        for record in records:
            converted_record = record.copy()
            # Always update symbol to the requested symbol
            converted_record['symbol'] = symbol
            
            if symbol.endswith('.C'):
                # Convert from Lượng to Chỉ (divide by 10)
                for field in ['nav', 'open', 'high', 'low', 'close', 'adjclose', 'buy_price', 'sell_price']:
                    if field in converted_record and converted_record[field] is not None:
                        converted_record[field] = converted_record[field] / 10.0
            
            converted_records.append(converted_record)
        
        if symbol.endswith('.C'):
            logger.info(f"Applied L→C conversion to {len(converted_records)} records for {symbol}")
        
        return converted_records
    
    def _get_sjc_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch SJC gold historical prices with rate limiting."""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            history = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                
                try:
                    # Rate limiting before each API call
                    if self.rate_limiter:
                        self.rate_limiter.wait_for_slot()
                    
                    df = self._fetch_sjc_gold_from_provider(date_str)
                    
                    # Record API call for rate limiting
                    if self.rate_limiter:
                        self.rate_limiter.record_call('sjc_gold_history')
                    
                    if df is not None and not df.empty:
                        info = df.iloc[0]
                        buy_price = float(info.get("buy_price", 0.0)) if not pd.isna(info.get("buy_price")) else 0.0
                        sell_price = float(info.get("sell_price", 0.0)) if not pd.isna(info.get("sell_price")) else 0.0
                        price = sell_price if sell_price > 0 else buy_price
                        
                        if price > 0:
                            history.append({
                                "date": date_str,
                                "nav": price,
                                "open": price,
                                "high": price,
                                "low": price,
                                "close": price,
                                "adjclose": 0,
                                "volume": 0.0,
                                "buy_price": buy_price,
                                "sell_price": sell_price
                            })
                            current_dt += timedelta(days=1)
                            continue
                except Exception as date_error:
                    logger.warning(f"API error for {date_str}: {date_error}, skipping date")
                
                # Skip this date and continue to next
                current_dt += timedelta(days=1)
            
            return history
        except Exception as e:
            logger.error(f"Error in _get_sjc_history: {e}")
            return []
    
    
    
    

    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch the latest gold price using database-first approach with unit conversion."""
        try:
            normalized_symbol, provider = self.parse_symbol(symbol)
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return None
        
        # Only SJC provider supported
        if provider != "sjc":
            logger.error(f"Unsupported provider: {provider}. Only SJC is supported.")
            return None
        
        # DATABASE-FIRST: Check database for latest data (use normalized symbol)
        today_str = datetime.now().strftime("%Y-%m-%d")
        latest_db = self._get_latest_from_database(normalized_symbol)
        
        if latest_db:
            # Check if data is recent (within 1 day)
            db_date = datetime.strptime(latest_db["date"], "%Y-%m-%d")
            days_old = (datetime.now() - db_date).days
            
            if days_old <= 1:
                logger.info(f"Using database-first quote for {symbol} from {latest_db['date']}")
                
                # Apply unit conversion and update symbol
                quote_data = self._apply_unit_conversion([latest_db], symbol)[0]
                
                # Cache the quote
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "GOLD", quote_data)
                
                if self.cache_manager and self.ttl_manager:
                    ttl = self.ttl_manager.get_ttl_for_asset("GOLD")
                    self.cache_manager.set_quote(symbol, "GOLD", quote_data, ttl_seconds=ttl)
                
                return quote_data
            else:
                logger.debug(f"Database data for {symbol} is {days_old} days old, fetching fresh data")
        
        # FALLBACK 1: Check memory cache
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "GOLD")
            if cached_quote:
                logger.debug(f"Using memory cached gold quote for {symbol}")
                return cached_quote
        
        # FALLBACK 2: Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "GOLD")
            if cached_quote:
                logger.debug(f"Using persistent cached gold quote for {symbol}")
                # Also store in memory cache for faster access
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "GOLD", cached_quote)
                return cached_quote
        
        # LAST RESORT: Fetch from API
        logger.info(f"Fetching fresh quote for {symbol} from API")
        
        # Rate limiting before API call
        if self.rate_limiter:
            self.rate_limiter.wait_for_slot()
        
        quote_data = None
        try:
            quote_data = self._get_sjc_quote(normalized_symbol)
            
            # Record API call for rate limiting
            if self.rate_limiter and quote_data:
                self.rate_limiter.record_call('gold_sjc_quote')
                
        except Exception as e:
            logger.warning(f"API call failed for gold {symbol}: {e}, will try fallback")
            quote_data = None
        
        # If API failed, try historical fallback
        if not quote_data:
            logger.debug(f"No current data for gold {symbol}, checking historical fallback")
            
            # Fallback: Check historical cache for most recent record
            if self.historical_cache:
                recent_record = self.historical_cache.get_most_recent_record(normalized_symbol, 'GOLD', lookback_days=30)
                if recent_record:
                    logger.info(f"Using historical fallback for gold {symbol} from {recent_record.get('date')}")
                    quote_data = recent_record
                else:
                    # Last resort: Fetch last week's data
                    logger.info(f"No historical cache for gold {symbol}, fetching last week's data")
                    one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                    history = self.get_gold_history(symbol, one_week_ago, today_str)
                    
                    if history:
                        most_recent = history[-1]
                        logger.info(f"Using last week's most recent data for gold {symbol} from {most_recent.get('date')}")
                        quote_data = most_recent
        
        # Apply unit conversion if needed
        if quote_data:
            quote_data = self._apply_unit_conversion([quote_data], symbol)[0]
            
            # Cache the final result
            if self.memory_cache:
                self.memory_cache.set_quote(symbol, "GOLD", quote_data)
            
            if self.cache_manager and self.ttl_manager:
                ttl = self.ttl_manager.get_ttl_for_asset("GOLD")
                self.cache_manager.set_quote(symbol, "GOLD", quote_data, ttl_seconds=ttl)
        
        return quote_data
    
    def _get_sjc_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest SJC gold price."""
        try:
            df = sjc_gold_price()
            
            if df is None or df.empty:
                logger.warning("SJC API returned empty data")
                return None
            
            info = df.iloc[0]
            date_val = info.get("date")
            date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d") if date_val else datetime.now().strftime("%Y-%m-%d")
            
            buy_price = float(info.get("buy_price", 0.0)) if not pd.isna(info.get("buy_price")) else 0.0
            sell_price = float(info.get("sell_price", 0.0)) if not pd.isna(info.get("sell_price")) else 0.0
            close_price = sell_price if sell_price > 0 else buy_price
            
            # For gold, we'll set OHLC values to the close price since gold typically trades at a single price
            return {
                "symbol": symbol,
                "open": close_price,
                "high": close_price,
                "low": close_price,
                "close": close_price,
                "adjclose": close_price,
                "volume": 0.0,  # Gold typically doesn't have volume data in this context
                "buy_price": buy_price,
                "sell_price": sell_price,
                "date": date_str,
                "currency": "VND"
            }
        except Exception as e:
            logger.error(f"Error fetching SJC quote: {e}")
            return None

    
    

    
    

    
    def search_gold(self, symbol: str) -> Optional[Dict]:
        """Return gold asset information for search results with unit information."""
        try:
            normalized_symbol, provider = self.parse_symbol(symbol)
            config = self.PROVIDERS[provider]
            
            # Determine unit and description
            if symbol.upper().endswith('.C'):
                unit = "Chỉ"
                unit_description = "1 Chỉ = 0.1 Lượng"
                name_suffix = " (Chỉ)"
            else:
                unit = "Lượng"
                unit_description = "1 Lượng = 10 Chỉ"
                name_suffix = " (Lượng)"
            
            return {
                "symbol": symbol.upper(),
                "name": f"Gold - {config['name']}{name_suffix}",
                "provider": provider,
                "provider_name": config["name"],
                "asset_type": "Commodity",
                "exchange": provider.upper(),
                "currency": "VND",
                "unit": unit,
                "unit_description": unit_description
            }
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching gold: {e}")
            return None
    
    def get_all_gold_providers(self) -> List[Dict]:
        """Return all available gold providers with their information including both units."""
        providers = []
        
        # Add VN.GOLD (Lượng)
        providers.append({
            "symbol": "VN.GOLD",
            "name": "Gold - Saigon Jewelry Company (Lượng)",
            "provider": "sjc",
            "provider_name": "Saigon Jewelry Company",
            "asset_type": "Commodity",
            "exchange": "SJC",
            "currency": "VND",
            "unit": "Lượng",
            "unit_description": "1 Lượng = 10 Chỉ"
        })
        
        # Add VN.GOLD.C (Chỉ)
        providers.append({
            "symbol": "VN.GOLD.C",
            "name": "Gold - Saigon Jewelry Company (Chỉ)",
            "provider": "sjc",
            "provider_name": "Saigon Jewelry Company",
            "asset_type": "Commodity",
            "exchange": "SJC",
            "currency": "VND",
            "unit": "Chỉ",
            "unit_description": "1 Chỉ = 0.1 Lượng"
        })
        
        return providers
