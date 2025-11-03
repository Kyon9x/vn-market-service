from vnstock import Fund
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import pandas as pd
import time
from requests.exceptions import Timeout, ConnectionError
from vnstock.core.utils import client
from vnstock.core.utils.user_agent import get_headers
from app.cache import get_fund_historical_cache, get_rate_limiter, get_ttl_manager
from app.utils.provider_logger import log_provider_call

logger = logging.getLogger(__name__)

class FundClient:
    def __init__(self, cache_manager=None, memory_cache=None):
        self._funds_cache: Optional[List[Dict]] = None
        self._funds_map: Dict[str, int] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_duration = timedelta(hours=24)
        self._fund_api = None  # Lazy initialization
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache

        # Initialize API components for direct API calls
        self.base_url = 'https://api.fmarket.vn/res/products'
        self.headers = get_headers(data_source="fmarket", random_agent=False)

        # Smart caching components
        self.historical_cache = get_fund_historical_cache()
        self.rate_limiter = get_rate_limiter()
        self.ttl_manager = get_ttl_manager()
    
    def _initialize_fund_api(self, max_retries: int = 3) -> Fund:
        """Initialize Fund API with retry logic for timeout handling."""
        last_error = None
        for attempt in range(max_retries):
            try:
                logger.info(f"Initializing Fund API (attempt {attempt + 1}/{max_retries})...")
                fund_api = Fund()
                logger.info("Fund API initialized successfully")
                return fund_api
            except (Timeout, ConnectionError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Fund API initialization timeout/connection error. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Fund API initialization failed after {max_retries} retries: {e}")
            except Exception as e:
                logger.error(f"Fund API initialization error: {e}")
                last_error = e
                break
        
        if last_error:
            raise last_error
        
        raise RuntimeError("Fund API initialization failed - no error details available")

    def _ensure_fund_api_initialized(self, max_retries: int = 3) -> bool:
        """Ensure the Fund API is initialized. Returns True if successful, False otherwise."""
        if self._fund_api is not None:
            return True

        try:
            self._fund_api = self._initialize_fund_api(max_retries)
            return True
        except Exception as e:
            logger.error(f"Failed to initialize Fund API: {e}")
            self._fund_api = None
            return False

    def _is_cache_valid(self) -> bool:
        if self._cache_timestamp is None:
            return False
        return datetime.now() - self._cache_timestamp < self._cache_duration
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"count": lambda r: len(r) if r is not None else 0})
    def _fetch_funds_listing_from_provider(self) -> Optional[pd.DataFrame]:
        if not self._ensure_fund_api_initialized():
            return None
        return self._fund_api.listing()

    @log_provider_call(provider_name="vnstock", metadata_fields={"fund_id": lambda r: r.get("fund_id", 0)})
    def _fetch_fund_nav_report_from_provider(self, fund_id: int) -> Optional[pd.DataFrame]:
        if not self._ensure_fund_api_initialized():
            return None
        return self._fund_api.nav_report(fund_id)

    @log_provider_call(provider_name="vnstock", metadata_fields={"fund_id": lambda r: r.get("fund_id", 0), "rows": lambda r: len(r) if r is not None else 0})
    def _fetch_fund_nav_history_from_provider(self, fund_id: int, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        """Fetch NAV history for a specific date range directly from FMarket API."""
        # Convert date format from YYYY-MM-DD to YYYYMMDD
        from_date = start_date.replace('-', '')
        to_date = end_date.replace('-', '')

        url = f"{self.base_url[:-1]}/get-nav-history"
        payload = {
            "isAllData": 0,  # Don't fetch all data, use date range
            "productId": fund_id,
            "fromDate": from_date,
            "toDate": to_date,
        }

        try:
            response_data = client.send_request(
                url=url,
                method="POST",
                headers=self.headers,
                payload=payload,
                show_log=False
            )

            if response_data and response_data.get('data'):
                # The API returns data as a list of records
                df = pd.json_normalize(response_data, record_path=["data"])

                if not df.empty:
                    # Rename columns to match expected format
                    column_mapping = {
                        'navDate': 'date',
                        'netAssetValue': 'nav_per_unit',
                        'nav': 'nav_per_unit'  # Handle both 'nav' and 'netAssetValue' column names
                    }

                    # Apply renaming for existing columns
                    existing_columns = {k: v for k, v in column_mapping.items() if k in df.columns}
                    df = df.rename(columns=existing_columns)

                    logger.info(f"Successfully fetched {len(df)} NAV records for fund {fund_id} from {start_date} to {end_date}")
                    return df
                else:
                    logger.info(f"No NAV data returned for fund {fund_id} from {start_date} to {end_date}")
            else:
                logger.warning(f"Invalid or empty response from API for fund {fund_id}")

            return None

        except Exception as e:
            logger.error(f"Error fetching NAV history for fund {fund_id} from {start_date} to {end_date}: {e}")
            return None
    
    def _refresh_funds_cache(self, max_retries: int = 3):
        """Fetch fresh fund list from vnstock with retry logic."""
        logger.info("Fetching fresh fund list from vnstock")
        
        last_error = None
        for attempt in range(max_retries):
            try:
                logger.info(f"Fetching fund listing (attempt {attempt + 1}/{max_retries})...")
                funds_df = self._fetch_funds_listing_from_provider()

                if funds_df is None or funds_df.empty:
                    raise Exception("Empty or None response from fund listing API")

                funds: List[Dict] = []
                self._funds_map = {}
                for _, row in funds_df.iterrows():
                    fund_code = row.get("fund_code", "")
                    short_name = row.get("short_name", "")
                    fund_id_value = row.get("fund_id_fmarket", 0)
                    fund_id = int(fund_id_value) if fund_id_value else 0
                    funds.append({
                        "symbol": short_name if short_name else fund_code,
                        "fund_name": row.get("name", ""),
                        "asset_type": "MUTUAL_FUND"
                    })
                    if fund_code:
                        self._funds_map[fund_code.upper()] = fund_id
                    if short_name:
                        self._funds_map[short_name.upper()] = fund_id
                
                self._funds_cache = funds
                self._cache_timestamp = datetime.now()
                logger.info(f"Cached {len(funds)} funds successfully")
                return
                
            except (Timeout, ConnectionError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(f"Fund listing fetch timeout/connection error. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Fund listing fetch failed after {max_retries} retries: {e}")
            except Exception as e:
                logger.error(f"Error fetching fund list: {e}")
                raise
        
        if last_error:
            raise last_error
    
    def get_funds_list(self) -> List[Dict]:
        if self._is_cache_valid() and self._funds_cache:
            logger.info("Using cached fund list")
            return self._funds_cache
        
        try:
            self._refresh_funds_cache()
            return self._funds_cache if self._funds_cache else []
        except Exception as e:
            logger.error(f"Error fetching funds list: {e}")
            if self._funds_cache:
                logger.warning("Returning stale cache due to error")
                return self._funds_cache
            raise
    
    def _get_fund_id(self, symbol: str) -> Optional[int]:
        if not self._is_cache_valid() or not self._funds_map:
            try:
                self._refresh_funds_cache()
            except Exception as e:
                logger.error(f"Error refreshing cache: {e}")
                return None
        
        return self._funds_map.get(symbol.upper())
    
    def search_fund_by_symbol(self, symbol: str) -> Optional[Dict]:
        try:
            fund_id = self._get_fund_id(symbol)
            if not fund_id:
                logger.warning(f"Fund ID not found for symbol: {symbol}")
                return None
            
            fund_info = self._fetch_fund_nav_report_from_provider(fund_id)
            if fund_info is None or fund_info.empty:
                return None
            
            info = fund_info.iloc[-1]
            nav_value = info.get("nav_per_unit", 0.0)
            
            fund_name = symbol
            if self._funds_cache:
                for fund in self._funds_cache:
                    if fund.get("symbol", "").upper() == symbol.upper():
                        fund_name = fund.get("fund_name", symbol)
                        break
            
            result = {
                "symbol": symbol,
                "fund_name": fund_name,
                "fund_type": "MUTUAL_FUND",
                "management_company": "",
                "inception_date": "",
                "nav_per_unit": float(nav_value) if nav_value else 0.0,
            }
            return result
        except Exception as e:
            logger.error(f"Error searching fund {symbol}: {e}")
            return None
    
    def get_fund_nav_history(self, symbol: str, start_date: str, end_date: str, max_retries: int = 2) -> List[Dict]:
        """Fetch NAV history with incremental caching support."""
        # Try incremental caching first
        if self.historical_cache:
            try:
                return self._get_fund_nav_history_incremental(symbol, start_date, end_date, max_retries)
            except Exception as e:
                logger.warning(f"Incremental caching failed for {symbol}, falling back to full fetch: {e}")
        
        # Fallback to full fetch
        return self._fetch_fund_nav_history_raw(symbol, start_date, end_date, max_retries)
    
    def _get_fund_nav_history_incremental(self, symbol: str, start_date: str, end_date: str, max_retries: int = 2) -> List[Dict]:
        """Fetch NAV history using incremental caching."""
        # Check what dates are already cached
        cached_dates = self.historical_cache.get_cached_dates(symbol, start_date, end_date, "FUND")
        
        # Calculate missing date ranges
        missing_ranges = self.historical_cache.calculate_missing_date_ranges(
            start_date=start_date,
            end_date=end_date,
            cached_dates=cached_dates
        )
        
        # If no missing ranges, return cached data
        if not missing_ranges:
            logger.info(f"All historical data for {symbol} found in cache")
            cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, "FUND")
            return self._format_nav_records(cached_data)
        
        # Fetch missing ranges
        logger.info(f"Fetching {len(missing_ranges)} missing date ranges for {symbol}")
        all_new_records = []
        
        for missing_start, missing_end in missing_ranges:
            records = self._fetch_fund_nav_history_raw(symbol, missing_start, missing_end, max_retries)
            if records:
                all_new_records.extend(records)
        
        # Store new records in cache first (real data takes priority)
        if all_new_records:
            self.historical_cache.store_historical_records(symbol, "FUND", all_new_records)
        
        # Mark all fetched ranges as attempted (creates null records for no-data dates)
        for missing_start, missing_end in missing_ranges:
            self.historical_cache.mark_date_range_as_fetched(symbol, "FUND", missing_start, missing_end)
        
        # Merge with existing cached data and return
        cached_data = self.historical_cache.get_cached_records(symbol, start_date, end_date, "FUND")
        all_data = self.historical_cache.merge_historical_data(cached_data, all_new_records)
        
        return self._format_nav_records(all_data)
    
    def _fetch_fund_nav_history_raw(self, symbol: str, start_date: str, end_date: str, max_retries: int = 2) -> List[Dict]:
        """Fetch NAV history from API with retry logic."""
        last_error = None
        
        for attempt in range(max_retries):
            try:
                fund_id = self._get_fund_id(symbol)
                if not fund_id:
                    logger.warning(f"Fund ID not found for symbol: {symbol}")
                    return []
                
                # Rate limiting
                if self.rate_limiter:
                    self.rate_limiter.wait_for_slot()
                
                logger.info(f"Fetching NAV history for {symbol} from {start_date} to {end_date} (attempt {attempt + 1}/{max_retries})...")
                history_df = self._fetch_fund_nav_history_from_provider(fund_id, start_date, end_date)

                # Record API call for rate limiting
                if self.rate_limiter:
                    self.rate_limiter.record_call('fund_nav_history')

                if history_df is None or history_df.empty:
                    return []

                # The data is already filtered by the API, but ensure date parsing
                history_df['date'] = pd.to_datetime(history_df['date'])
                
                history = []
                for _, row in history_df.iterrows():
                    nav_value = row.get("nav_per_unit", 0.0)
                    nav = float(nav_value) if nav_value else 0.0
                    date_val = row.get("date")
                    date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                    history.append({
                        "symbol": symbol,
                        "date": date_str,
                        "nav": nav,
                        "open": nav,
                        "high": nav,
                        "low": nav,
                        "close": nav,
                        "adjclose": nav,
                        "volume": 0.0
                    })
                
                return history
                
            except (Timeout, ConnectionError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(f"NAV history fetch timeout/connection error for {symbol}. Retrying in {wait_time}s... (Attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    logger.error(f"NAV history fetch failed after {max_retries} retries for {symbol}: {e}")
            except Exception as e:
                logger.error(f"Error fetching NAV history for {symbol}: {e}")
                return []
        
        if last_error:
            logger.error(f"NAV history fetch failed for {symbol} after {max_retries} retries")
        
        return []
    
    def _format_nav_records(self, records: List[Dict]) -> List[Dict]:
        """Format historical records for NAV data."""
        formatted = []
        for record in records:
            # Extract NAV value - it could be in 'close' or 'nav' field
            nav = record.get("nav") or record.get("close", 0.0)
            formatted.append({
                "date": record.get("date"),
                "nav": nav,
                "open": nav,
                "high": nav,
                "low": nav,
                "close": nav,
                "adjclose": nav,
                "volume": 0.0
            })
        return formatted
    
    def get_latest_nav(self, symbol: str, max_retries: int = 2) -> Optional[Dict]:
        """Get latest NAV with retry logic and smart caching."""
        # Check memory cache first (will use 24-hour TTL automatically)
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "FUND")
            if cached_quote:
                logger.debug(f"Using cached NAV for {symbol}")
                return cached_quote
        
        # Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "FUND")
            if cached_quote:
                logger.debug(f"Using persistent cached NAV for {symbol}")
                # Also store in memory cache for faster access (will use 24-hour TTL)
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "FUND", cached_quote)
                return cached_quote
        
        last_error = None
        for attempt in range(max_retries):
            try:
                fund_id = self._get_fund_id(symbol)
                if not fund_id:
                    logger.warning(f"Fund ID not found for symbol: {symbol}")
                    return None
                
                logger.info(f"Fetching latest NAV for {symbol} (attempt {attempt + 1}/{max_retries})...")
                nav_df = self._fund_api.nav_report(fund_id)
                if nav_df is None or nav_df.empty:
                    logger.debug(f"No current NAV data for {symbol}, checking historical fallback")
                    
                    # Fallback 1: Check historical cache for most recent record
                    if self.historical_cache:
                        recent_record = self.historical_cache.get_most_recent_record(symbol, 'FUND', lookback_days=30)
                        if recent_record:
                            logger.info(f"Using historical fallback for fund {symbol} from {recent_record.get('date')}")
                            # Cache this fallback quote
                            if self.memory_cache:
                                self.memory_cache.set_quote(symbol, "FUND", recent_record)
                            if self.cache_manager and self.ttl_manager:
                                ttl = self.ttl_manager.get_ttl_for_asset("FUND")
                                self.cache_manager.set_quote(symbol, "FUND", recent_record, ttl_seconds=ttl)
                            return recent_record
                        
                        # Fallback 2: Fetch last week's data to populate cache
                        logger.info(f"No historical cache for fund {symbol}, fetching last week's data")
                        one_week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        history = self.get_fund_history(symbol, one_week_ago, today_str)
                        
                        if history:
                            most_recent = history[-1]
                            logger.info(f"Using last week's most recent data for fund {symbol} from {most_recent.get('date')}")
                            # Ensure symbol is present in the fallback record
                            if "symbol" not in most_recent:
                                most_recent["symbol"] = symbol
                            # Cache this fallback quote
                            if self.memory_cache:
                                self.memory_cache.set_quote(symbol, "FUND", most_recent)
                            if self.cache_manager and self.ttl_manager:
                                ttl = self.ttl_manager.get_ttl_for_asset("FUND")
                                self.cache_manager.set_quote(symbol, "FUND", most_recent, ttl_seconds=ttl)
                            return most_recent
                    
                    return None
                
                # Process successful API response
                info = nav_df.iloc[-1]
                date_val = info.get("date")
                if isinstance(date_val, pd.Timestamp):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val) if date_val else datetime.now().strftime("%Y-%m-%d")
                
                nav_value = info.get("nav_per_unit", 0.0)
                nav_float = float(nav_value) if nav_value else 0.0
                
                # For funds, we'll set OHLC values to the NAV since that's the primary price metric
                quote_data = {
                    "symbol": symbol,
                    "open": nav_float,
                    "high": nav_float,
                    "low": nav_float,
                    "close": nav_float,
                    "adjclose": nav_float,
                    "volume": 0.0,  # Funds typically don't have volume data
                    "nav": nav_float,
                    "date": date_str
                }
                
                # Cache the quote (memory cache will auto-use 24-hour TTL for FUND)
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "FUND", quote_data)
                
                # Cache in persistent storage with TTL from TTL manager
                if self.cache_manager and self.ttl_manager:
                    ttl = self.ttl_manager.get_ttl_for_asset("FUND")
                    self.cache_manager.set_quote(symbol, "FUND", quote_data, ttl_seconds=ttl)
                
                return quote_data
                
            except Exception as e:
                logger.error(f"Error processing fund NAV for {symbol}: {e}")
                return None
        
        if last_error:
            logger.error(f"Latest NAV fetch failed for {symbol} after {max_retries} retries")
        
        return None
    
    def search_funds_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """Search funds by partial name or symbol match (case-insensitive)."""
        try:
            funds = self.get_funds_list()
            query_lower = query.lower()
            results = []
            
            for fund in funds:
                symbol = fund.get("symbol", "")
                fund_name = fund.get("fund_name", "")
                
                # Match on symbol or fund name
                if query_lower in symbol.lower() or query_lower in fund_name.lower():
                    results.append({
                        "symbol": symbol,
                        "fund_name": fund_name,
                        "asset_type": "MUTUAL_FUND"
                    })
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as e:
            logger.error(f"Error searching funds by name '{query}': {e}")
            return []
