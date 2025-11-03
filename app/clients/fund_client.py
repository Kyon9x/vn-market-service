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

# Import LazyFetchManager separately to avoid circular import issues
try:
    from app.cache.lazy_fetch_manager import LazyFetchManager
    LAZY_FETCH_AVAILABLE = True
except ImportError:
    LazyFetchManager = None
    LAZY_FETCH_AVAILABLE = False

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
        
        # Lazy fetch manager for background data enrichment
        self.lazy_fetch_manager = LazyFetchManager(db_path="db/assets.db", fund_client=self) if LazyFetchManager else None
        
        # Fund inception date cache for smart date range adjustment
        self._inception_dates: Dict[str, str] = {}  # symbol -> inception_date
        self._inception_cache_ttl = timedelta(days=7)  # Cache inception dates for 7 days
    
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
    
    def _get_fund_inception_date(self, symbol: str) -> Optional[str]:
        """
        Get fund inception date (earliest available NAV date).
        
        Uses cached inception dates to avoid repeated API calls.
        Returns None if inception date cannot be determined.
        """
        # Check cache first
        if symbol.upper() in self._inception_dates:
            logger.debug(f"Using cached inception date for {symbol}: {self._inception_dates[symbol.upper()]}")
            return self._inception_dates[symbol.upper()]
        
        try:
            # Get fund ID first
            fund_id = self._get_fund_id(symbol)
            if not fund_id:
                logger.warning(f"Fund ID not found for inception date lookup: {symbol}")
                return None
            
            # Use vnstock nav_report to get full history
            if self._ensure_fund_api_initialized() and self._fund_api is not None:
                fund_api = self._fund_api  # Local variable for type checker
                nav_df = fund_api.nav_report(fund_id)
                
                if nav_df is not None and not nav_df.empty:
                    # Find earliest date in the data
                    nav_df['date'] = pd.to_datetime(nav_df['date'])
                    earliest_record = nav_df.loc[nav_df['date'].idxmin()]
                    inception_date = earliest_record['date'].strftime("%Y-%m-%d")
                    
                    # Cache the inception date
                    self._inception_dates[symbol.upper()] = inception_date
                    logger.info(f"Discovered inception date for {symbol}: {inception_date}")
                    return inception_date
                else:
                    logger.warning(f"No NAV data available for inception date lookup: {symbol}")
                    return None
            else:
                logger.warning(f"Fund API not initialized for inception date lookup: {symbol}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting inception date for {symbol}: {e}")
            return None
    
    def _adjust_date_range_for_inception(self, symbol: str, start_date: str, end_date: str) -> tuple[str, str]:
        """
        Adjust date range based on fund's inception date.
        
        Returns tuple of (adjusted_start_date, adjusted_end_date).
        If adjustment was made, logs the change.
        """
        inception_date = self._get_fund_inception_date(symbol)
        
        if inception_date is None:
            # Could not determine inception date, use original range
            return start_date, end_date
        
        # Use the later of requested start date or inception date
        if start_date < inception_date:
            adjusted_start = inception_date
            logger.info(f"Adjusted start date for {symbol}: {start_date} → {adjusted_start} (fund inception)")
            return adjusted_start, end_date
        else:
            # No adjustment needed
            return start_date, end_date
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"count": lambda r: len(r) if r is not None else 0})
    def _fetch_funds_listing_from_provider(self) -> Optional[pd.DataFrame]:
        if not self._ensure_fund_api_initialized():
            return None
        fund_api = self._fund_api  # Local variable for type checker
        return fund_api.listing()

    @log_provider_call(provider_name="vnstock", metadata_fields={"fund_id": lambda r: r.get("fund_id", 0)})
    def _fetch_fund_nav_report_from_provider(self, fund_id: int) -> Optional[pd.DataFrame]:
        if not self._ensure_fund_api_initialized():
            return None
        fund_api = self._fund_api  # Local variable for type checker
        return fund_api.nav_report(fund_id)

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
    
    def get_fund_nav_history(self, symbol: str, start_date: str, end_date: str, 
                            max_retries: int = 2, use_lazy_fetch: bool = True) -> List[Dict]:
        """Fetch NAV history with smart date range adjustment and lazy fetch support by default."""
        
        # Step 1: Adjust date range based on fund inception date
        adjusted_start, adjusted_end = self._adjust_date_range_for_inception(symbol, start_date, end_date)
        
        # Step 2: Use lazy fetch by default (non-blocking, immediate response)
        if use_lazy_fetch and self.historical_cache:
            try:
                return self._get_fund_history_lazy_fetch(symbol, adjusted_start, adjusted_end)
            except Exception as e:
                logger.warning(f"Lazy fetch failed for {symbol}, falling back to incremental: {e}")
        
        # Step 3: Fallback to incremental caching (current behavior)
        if self.historical_cache:
            try:
                return self._get_fund_nav_history_incremental(symbol, adjusted_start, adjusted_end, max_retries)
            except Exception as e:
                logger.warning(f"Incremental caching failed for {symbol}, falling back to full fetch: {e}")
        
        # Step 4: Last resort: full fetch with adjusted dates
        return self._fetch_fund_nav_history_raw(symbol, adjusted_start, adjusted_end, max_retries)
    
    def _get_fund_history_lazy_fetch(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """
        Cache-first hybrid approach: Check cache first, then vnstock as fallback.
        
        This method:
        1. Check cache first (prioritize cached data to minimize vnstock calls)
        2. If cache is sufficient (>80% complete), return immediately
        3. Only if cache insufficient, try vnstock native method
        4. Trigger background fetch for any remaining gaps
        5. Never blocks waiting for API calls
        """
        try:
            # Step 1: Check cache FIRST to minimize vnstock calls
            cached_records = self.historical_cache.get_cached_records(symbol, start_date, end_date, "FUND")
            logger.info(f"Cache check for {symbol}: {len(cached_records)} records found")
            
            # Step 2: Assess cache completeness - if sufficient, return immediately
            if not self._needs_lazy_fetch_hybrid(start_date, end_date, cached_records):
                logger.info(f"Cache sufficient for {symbol} ({len(cached_records)} records), returning cached data")
                
                # Still trigger background fetch for any minor gaps if needed
                if self.lazy_fetch_manager and self._needs_lazy_fetch(start_date, end_date, cached_records):
                    logger.info(f"Triggering lazy fetch for minor gaps in {symbol}")
                    try:
                        self.lazy_fetch_manager.trigger_lazy_fetch(symbol, start_date, end_date, "FUND")
                    except Exception as e:
                        logger.warning(f"Failed to trigger lazy fetch: {e}")
                
                return self._format_nav_records(cached_records)
            
            # Step 3: Cache insufficient, try vnstock native method as fallback
            logger.info(f"Cache insufficient for {symbol}, trying vnstock native method")
            complete_records = self._get_complete_nav_history_vnstock(symbol)
            if complete_records is not None and not complete_records.empty:
                logger.info(f"Got {len(complete_records)} records from vnstock nav_report for {symbol}")
                
                # Filter to requested date range
                complete_records['date'] = pd.to_datetime(complete_records['date'])
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                
                mask = (complete_records['date'] >= start_dt) & (complete_records['date'] <= end_dt)
                filtered_records = complete_records.loc[mask]
                
                if not filtered_records.empty:
                    # Convert to standard format
                    formatted_records = []
                    for _, row in filtered_records.iterrows():
                        nav_value = row.get("nav_per_unit", 0.0)
                        nav = float(nav_value) if nav_value else 0.0
                        date_val = row.get("date")
                        date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                        
                        formatted_records.append({
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
                    
                    # Store in cache for future requests (reduces future vnstock calls)
                    if self.historical_cache:
                        try:
                            self.historical_cache.store_historical_records(symbol, "FUND", formatted_records)
                            logger.info(f"Stored {len(formatted_records)} vnstock records in cache for {symbol}")
                        except Exception as e:
                            logger.warning(f"Failed to store vnstock records in cache: {e}")
                    
                    # Check if we need additional lazy fetch for any remaining gaps
                    if self.lazy_fetch_manager and self._needs_lazy_fetch_hybrid(start_date, end_date, formatted_records):
                        logger.info(f"Triggering additional lazy fetch for gaps in {symbol}")
                        try:
                            self.lazy_fetch_manager.trigger_lazy_fetch(symbol, start_date, end_date, "FUND")
                        except Exception as e:
                            logger.warning(f"Failed to trigger additional lazy fetch: {e}")
                    
                    return formatted_records
            
            # Step 4: Both cache and vnstock failed/insufficient, use cache + background fetch
            logger.info(f"Both cache and vnstock insufficient for {symbol}, using cache + background fetch")
            
            # Trigger background fetch if needed (non-blocking)
            if self.lazy_fetch_manager and self._needs_lazy_fetch(start_date, end_date, cached_records):
                logger.info(f"Triggering lazy fetch for {symbol} ({start_date} to {end_date})")
                try:
                    self.lazy_fetch_manager.trigger_lazy_fetch(symbol, start_date, end_date, "FUND")
                except Exception as e:
                    logger.warning(f"Failed to trigger lazy fetch: {e}")
            
            # Step 5: Return whatever cached data we have (don't wait for background)
            return self._format_nav_records(cached_records)
            
        except Exception as e:
            logger.error(f"Error in cache-first hybrid lazy fetch for {symbol}: {e}")
            # Fallback to empty response rather than blocking
            return []

    def _get_complete_nav_history_vnstock(self, symbol: str) -> Optional[pd.DataFrame]:
        """Try to get complete NAV history using vnstock native method."""
        try:
            # Get fund ID first
            fund_id = self._get_fund_id(symbol)
            if not fund_id:
                logger.warning(f"Fund ID not found for symbol: {symbol}")
                return None
                
            if self._ensure_fund_api_initialized() and self._fund_api is not None:
                fund_api = self._fund_api  # Local variable for type checker
                return fund_api.nav_report(fund_id)
            else:
                logger.warning(f"Fund API not initialized for {symbol}")
                return None
        except Exception as e:
            logger.warning(f"vnstock nav_report failed for {symbol}: {e}")
            return None

    def _needs_lazy_fetch_hybrid(self, start_date: str, end_date: str, complete_records: List[Dict]) -> bool:
        """
        Enhanced logic for hybrid approach.
        
        Args:
            start_date: Start date string
            end_date: End date string
            complete_records: Records from vnstock native method
            
        Returns:
            True if lazy fetch should be triggered
        """
        # If we got complete data from vnstock native method
        if complete_records:
            # Check if coverage is sufficient (>80% of expected trading days)
            expected_days = sum(1 for day in range((datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days + 1)
                                  if (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=day)).weekday() < 5)
            completeness = len(complete_records) / expected_days if expected_days > 0 else 0
            return completeness < 0.8
        
        # If no complete data, always use lazy fetch
        return True

    def _calculate_trading_days(self, start_date: str, end_date: str) -> int:
        """Calculate expected trading days (weekdays only) for date range."""
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        return sum(1 for day in range((end_dt - start_dt).days + 1)
                      if (start_dt + timedelta(days=day)).weekday() < 5)

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
        
        # Calculate expected trading days (weekdays only)
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        expected_days = sum(1 for day in range((end_dt - start_dt).days + 1)
                          if (start_dt + timedelta(days=day)).weekday() < 5)
        
        # If we have less than 60% of expected data, trigger lazy fetch
        completeness = len(cached_records) / expected_days if expected_days > 0 else 0
        return completeness < 0.6
    
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
                if not self._ensure_fund_api_initialized():
                    return None
                fund_api = self._fund_api  # Local variable for type checker
                nav_df = fund_api.nav_report(fund_id)
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
                        history = self.get_fund_nav_history(symbol, one_week_ago, today_str)
                        
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
