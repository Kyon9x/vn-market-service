from vnstock.explorer.misc import sjc_gold_price
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import pandas as pd
import sqlite3
from pathlib import Path
from app.cache import get_historical_cache, get_rate_limiter, get_ttl_manager
from app.utils.provider_logger import log_provider_call

logger = logging.getLogger(__name__)

class GoldClient:
    # Provider configurations - Only SJC as source of truth
    PROVIDERS = {
        "sjc": {
            "name": "Saigon Jewelry Company",
            "symbols": ["VN.GOLD", "SJC.GOLD"],
            "api_func": "sjc_gold_price"
        }
    }
    
    def __init__(self, cache_manager=None, memory_cache=None, db_path: str = "db/assets.db"):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
        self.db_path = Path(db_path)
        
        # Smart caching components
        self.historical_cache = get_historical_cache()
        self.rate_limiter = get_rate_limiter()
        self.ttl_manager = get_ttl_manager()
    
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
        Raises ValueError if symbol is not a valid gold provider symbol.
        """
        symbol_upper = symbol.upper()
        
        for provider, config in self.PROVIDERS.items():
            if symbol_upper in [s.upper() for s in config["symbols"]]:
                return symbol_upper, provider
        
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
        """Fetch historical gold prices using database-first approach."""
        try:
            _, provider = self.parse_symbol(symbol)
            
            # Only SJC provider supported
            if provider != "sjc":
                logger.error(f"Unsupported provider: {provider}. Only SJC is supported.")
                return []
            
            # DATABASE-FIRST: Check database first
            if self._database_has_data(start_date, end_date):
                logger.info(f"Using database-first approach for {symbol} ({start_date} to {end_date})")
                history = self._get_historical_from_database(start_date, end_date, symbol)
                
                # Cache the results for faster future access
                if history and self.cache_manager:
                    self.cache_manager.set_historical_data(symbol, start_date, end_date, "GOLD", history)
                
                return history
            
            # FALLBACK: Check cache first
            if self.cache_manager:
                cached_history = self.cache_manager.get_historical_data(symbol, start_date, end_date, "GOLD")
                if cached_history:
                    logger.debug(f"Using cached historical data for {symbol}")
                    return cached_history
            
            # LAST RESORT: Fetch from API (only if database is incomplete)
            logger.warning(f"Database incomplete for {symbol}, fetching from API ({start_date} to {end_date})")
            history = self._get_sjc_history(start_date, end_date)
            
            # Cache the results
            if history and self.cache_manager:
                self.cache_manager.set_historical_data(symbol, start_date, end_date, "GOLD", history)
            
            return history
            
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching gold history for {symbol}: {e}")
            return []
    
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
        """Fetch the latest gold price using database-first approach."""
        try:
            _, provider = self.parse_symbol(symbol)
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return None
        
        # Only SJC provider supported
        if provider != "sjc":
            logger.error(f"Unsupported provider: {provider}. Only SJC is supported.")
            return None
        
        # DATABASE-FIRST: Check database for latest data
        today_str = datetime.now().strftime("%Y-%m-%d")
        latest_db = self._get_latest_from_database(symbol)
        
        if latest_db:
            # Check if data is recent (within 1 day)
            db_date = datetime.strptime(latest_db["date"], "%Y-%m-%d")
            days_old = (datetime.now() - db_date).days
            
            if days_old <= 1:
                logger.info(f"Using database-first quote for {symbol} from {latest_db['date']}")
                
                # Cache the quote
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "GOLD", latest_db)
                
                if self.cache_manager and self.ttl_manager:
                    ttl = self.ttl_manager.get_ttl_for_asset("GOLD")
                    self.cache_manager.set_quote(symbol, "GOLD", latest_db, ttl_seconds=ttl)
                
                return latest_db
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
            quote_data = self._get_sjc_quote(symbol)
            
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
                recent_record = self.historical_cache.get_most_recent_record(symbol, 'GOLD', lookback_days=30)
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
                        if "symbol" not in most_recent:
                            most_recent["symbol"] = symbol
                        quote_data = most_recent
        
        # Cache the final result
        if quote_data:
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
        """Return gold asset information for search results."""
        try:
            _, provider = self.parse_symbol(symbol)
            config = self.PROVIDERS[provider]
            
            return {
                "symbol": symbol,
                "name": f"Gold - {config['name']}",
                "provider": provider,
                "provider_name": config["name"],
                "asset_type": "Commodity",
                "exchange": provider.upper(),
                "currency": "VND"  # SJC gold is always in VND
            }
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return None
        except Exception as e:
            logger.error(f"Error searching gold: {e}")
            return None
    
    def get_all_gold_providers(self) -> List[Dict]:
        """Return all available gold providers with their information."""
        providers = []
        for provider_key, config in self.PROVIDERS.items():
            # Use the primary symbol for each provider
            primary_symbol = config["symbols"][0]
            providers.append({
                "symbol": primary_symbol,
                "name": f"Gold - {config['name']}",
                "provider": provider_key,
                "provider_name": config["name"],
                "asset_type": "Commodity",
                "exchange": provider_key.upper(),
                "currency": "VND"  # SJC gold is always in VND
            })
        return providers
