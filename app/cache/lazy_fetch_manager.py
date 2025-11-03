"""
Lazy Fetch Manager - Background data enrichment for historical cache.

This module implements progressive data fetching in the background:
- Triggers after user requests return cached data
- Fetches missing data in small chunks
- Rate limiting aware with adaptive delays
- Non-blocking user experience
"""

import sqlite3
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)

class LazyFetchManager:
    """
    Manages background fetching of missing historical data.
    
    Key features:
    - Non-blocking background threads
    - Small chunk fetching (1-2 weeks at a time)
    - Rate limiting aware delays
    - Progress tracking and status monitoring
    """
    
    def __init__(self, db_path: str = "db/assets.db", gold_client=None, fund_client=None):
        self.db_path = Path(db_path)
        self.gold_client = gold_client
        self.fund_client = fund_client
        self._lock = threading.Lock()
        self._active_fetches: Set[str] = set()  # Track active fetch tasks
        self._fetch_status: Dict[str, Dict] = {}  # Track fetch progress
        
    def trigger_lazy_fetch(self, symbol: str, start_date: str, end_date: str, asset_type: str = "GOLD"):
        """
        Trigger background fetch for missing data.
        
        Args:
            symbol: Asset symbol
            start_date: Start date string
            end_date: End date string  
            asset_type: Asset type (GOLD, STOCK, etc.)
        """
        fetch_key = f"{symbol}_{start_date}_{end_date}"
        
        with self._lock:
            # Check for exact duplicate
            if fetch_key in self._active_fetches:
                logger.debug(f"Lazy fetch already active for {fetch_key}")
                return
            
            # DISABLED: Overlap detection causes deadlocks, using basic duplicate prevention only
            # if self._check_overlapping_ranges(symbol, start_date, end_date):
            #     logger.info(f"Lazy fetch range overlaps with active task for {symbol} ({start_date} to {end_date})")
            #     return
            
            self._active_fetches.add(fetch_key)
            self._fetch_status[fetch_key] = {
                "started": datetime.now().isoformat(),
                "status": "queued",
                "total_chunks": 0,
                "completed_chunks": 0
            }
        
        # Start background thread
        thread = threading.Thread(
            target=self._background_fetch_worker,
            args=(symbol, start_date, end_date, asset_type, fetch_key),
            daemon=True
        )
        thread.start()
        
        logger.info(f"Triggered lazy fetch for {symbol} ({start_date} to {end_date})")
    
    def _background_fetch_worker(self, symbol: str, start_date: str, end_date: str, 
                               asset_type: str, fetch_key: str):
        """
        Background worker that fetches missing data in chunks.
        
        Args:
            symbol: Asset symbol
            start_date: Start date string
            end_date: End date string
            asset_type: Asset type
            fetch_key: Unique fetch identifier
        """
        try:
            self._update_fetch_status(fetch_key, "running", 0, 0)
            
            # Get missing date ranges
            missing_ranges = self._get_missing_date_ranges(symbol, start_date, end_date, asset_type)
            
            if not missing_ranges:
                logger.info(f"No missing data for {symbol}, skipping lazy fetch")
                self._update_fetch_status(fetch_key, "completed", 0, 0)
                return
            
            # Calculate chunks (3 days per chunk for gold, 14 days for funds)
            chunk_days = 3 if asset_type == "GOLD" else 14
            chunks = self._create_chunks(missing_ranges, chunk_days=chunk_days, asset_type=asset_type)
            total_chunks = len(chunks)
            
            self._update_fetch_status(fetch_key, "running", total_chunks, 0)
            
            # Fetch chunks with delays
            for i, (chunk_start, chunk_end) in enumerate(chunks):
                try:
                    logger.info(f"Fetching chunk {i+1}/{total_chunks} for {symbol}: {chunk_start} to {chunk_end}")
                    
                    # Fetch data using appropriate client
                    if self.gold_client and asset_type == "GOLD":
                        new_records = self.gold_client._get_sjc_history(chunk_start, chunk_end)
                    elif self.fund_client and asset_type == "FUND":
                        new_records = self._fetch_fund_chunk(symbol, chunk_start, chunk_end)
                    else:
                        new_records = []
                        
                    if new_records:
                        # Store in database
                        stored_count = self._store_records(symbol, asset_type, new_records)
                        logger.info(f"Stored {stored_count} records for {symbol} chunk {i+1}")
                    
                    # Update progress
                    self._update_fetch_status(fetch_key, "running", total_chunks, i + 1)
                    
                    # Rate limiting delay between chunks (more conservative for background processing)
                    if i < total_chunks - 1:  # Don't delay after last chunk
                        delay = self._calculate_adaptive_delay()
                        # Add extra conservative delay for lazy fetch (always wait at least 2s)
                        conservative_delay = max(delay, 2.0)
                        logger.info(f"Waiting {conservative_delay}s before next chunk (adaptive: {delay}s)...")
                        time.sleep(conservative_delay)
                        
                except Exception as e:
                    logger.error(f"Error fetching chunk {i+1} for {symbol}: {e}")
                    continue
            
            self._update_fetch_status(fetch_key, "completed", total_chunks, total_chunks)
            logger.info(f"Completed lazy fetch for {symbol} ({total_chunks} chunks)")
            
        except Exception as e:
            logger.error(f"Lazy fetch worker failed for {symbol}: {e}")
            self._update_fetch_status(fetch_key, "failed", 0, 0)
        
        finally:
            with self._lock:
                self._active_fetches.discard(fetch_key)
    
    def _check_overlapping_ranges(self, symbol: str, start_date: str, end_date: str) -> bool:
        """
        Simplified overlap detection - only checks for exact symbol matches.
        
        Args:
            symbol: Asset symbol
            start_date: Start date string
            end_date: End date string
            
        Returns:
            True if range overlaps with active fetch, False otherwise
        """
        with self._lock:
            if not self._active_fetches:
                return False  # No active fetches, no overlap possible
                
            # Simple check: if any active fetch exists for this symbol, assume overlap
            # This is conservative but prevents complex parsing that could cause deadlocks
            for active_key in self._active_fetches:
                if active_key.startswith(f"{symbol}_"):
                    logger.info(f"Conservative overlap detection: active fetch exists for {symbol}")
                    return True
        
        return False
    
    def _get_missing_date_ranges(self, symbol: str, start_date: str, end_date: str, asset_type: str) -> List[tuple]:
        """Get missing date ranges from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Get existing dates
                cursor.execute('''
                    SELECT DISTINCT date FROM historical_records 
                    WHERE symbol = ? AND asset_type = ?
                    AND date BETWEEN ? AND ?
                    ORDER BY date
                ''', (symbol, asset_type, start_date, end_date))
                
                existing_dates = {row[0] for row in cursor.fetchall()}
                
                # Generate all dates in range
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                
                all_dates = []
                current_dt = start_dt
                while current_dt <= end_dt:
                    # Skip weekends (assuming stock market data)
                    if current_dt.weekday() < 5:  # Monday=0, Friday=4
                        all_dates.append(current_dt.strftime("%Y-%m-%d"))
                    current_dt += timedelta(days=1)
                
                # Find missing dates
                missing_dates = [date for date in all_dates if date not in existing_dates]
                
                # Convert to ranges
                return self._dates_to_ranges(missing_dates)
                
        except Exception as e:
            logger.error(f"Error getting missing date ranges: {e}")
            return []
    
    def _dates_to_ranges(self, dates: List[str]) -> List[tuple]:
        """Convert list of dates to list of (start_date, end_date) ranges."""
        if not dates:
            return []
        
        ranges = []
        start_date = dates[0]
        prev_date = dates[0]
        
        for date in dates[1:]:
            curr_dt = datetime.strptime(date, "%Y-%m-%d")
            prev_dt = datetime.strptime(prev_date, "%Y-%m-%d")
            
            if (curr_dt - prev_dt).days > 1:  # Gap in dates
                ranges.append((start_date, prev_date))
                start_date = date
            
            prev_date = date
        
        # Add final range
        ranges.append((start_date, prev_date))
        return ranges
    
    def _create_chunks(self, ranges: List[tuple], chunk_days: int = 7, asset_type: str = "GOLD") -> List[tuple]:
        """Split date ranges into smaller chunks with asset-specific sizing."""
        # Use larger chunks for funds (14 days) vs gold (default 7 days)
        if asset_type == "FUND":
            chunk_days = 14
        
        chunks = []
        
        for start_date, end_date in ranges:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            current_start = start_dt
            while current_start <= end_dt:
                current_end = min(current_start + timedelta(days=chunk_days - 1), end_dt)
                chunks.append((current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d")))
                current_start = current_end + timedelta(days=1)
        
        return chunks
    
    def _fetch_fund_chunk(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch fund NAV data for a specific chunk using fund client."""
        try:
            # Get fund ID
            fund_id = self.fund_client._get_fund_id(symbol)
            if not fund_id:
                logger.warning(f"Fund ID not found for symbol: {symbol}")
                return []
            
            # Fetch data using existing method
            history_df = self.fund_client._fetch_fund_nav_history_from_provider(fund_id, start_date, end_date)
            
            if history_df is None or history_df.empty:
                return []
            
            # Convert to standard format
            records = []
            for _, row in history_df.iterrows():
                nav_value = row.get("nav_per_unit", 0.0)
                nav = float(nav_value) if nav_value else 0.0
                date_val = row.get("date")
                date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                
                records.append({
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
            
            return records
            
        except Exception as e:
            logger.error(f"Error fetching fund chunk for {symbol} ({start_date} to {end_date}): {e}")
            return []
    
    def _calculate_adaptive_delay(self) -> float:
        """Calculate adaptive delay based on recent API calls."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check recent API calls (last minute)
                one_minute_ago = (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute('''
                    SELECT COUNT(*) FROM provider_logs 
                    WHERE timestamp > ?
                ''', (one_minute_ago,))
                
                recent_calls = cursor.fetchone()[0]
                
                # Adaptive delay: more calls = longer delay (more conservative for lazy fetch)
                if recent_calls > 40:
                    return 5.0  # High rate limit risk
                elif recent_calls > 25:
                    return 3.0  # Medium risk
                elif recent_calls > 15:
                    return 2.0  # Moderate risk
                else:
                    return 1.0  # Low risk
                    
        except Exception:
            return 1.0  # Default conservative delay
    
    def _store_records(self, symbol: str, asset_type: str, records: List[Dict]) -> int:
        """Store records in database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                stored_count = 0
                for record in records:
                    # Ensure all numeric fields have proper values (not None)
                    nav = record.get('nav') or 0.0
                    open_price = record.get('open') or nav
                    high_price = record.get('high') or nav
                    low_price = record.get('low') or nav
                    close_price = record.get('close') or nav
                    adjclose = record.get('adjclose') or 0.0
                    volume = record.get('volume') or 0.0
                    buy_price = record.get('buy_price') or 0.0
                    sell_price = record.get('sell_price') or 0.0
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_records 
                        (symbol, asset_type, date, open, high, low, close, 
                         adjclose, volume, nav, buy_price, sell_price)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        symbol, asset_type, record.get('date'),
                        float(open_price), float(high_price), float(low_price),
                        float(close_price), float(adjclose), float(volume),
                        float(nav), float(buy_price), float(sell_price)
                    ))
                    stored_count += 1
                
                conn.commit()
                return stored_count
                
        except Exception as e:
            logger.error(f"Error storing records: {e}")
            return 0
    
    def _update_fetch_status(self, fetch_key: str, status: str, total_chunks: int, completed_chunks: int):
        """Update fetch progress status."""
        with self._lock:
            if fetch_key in self._fetch_status:
                self._fetch_status[fetch_key].update({
                    "status": status,
                    "total_chunks": total_chunks,
                    "completed_chunks": completed_chunks,
                    "last_updated": datetime.now().isoformat()
                })
    
    def get_fetch_status(self, symbol: Optional[str] = None) -> Dict:
        """Get current fetch status."""
        with self._lock:
            if symbol:
                # Return status for specific symbol
                symbol_status = {}
                for key, status in self._fetch_status.items():
                    if key.startswith(symbol + "_"):
                        symbol_status[key] = status
                return symbol_status
            else:
                # Return all status
                return self._fetch_status.copy()
    
    def needs_lazy_fetch(self, symbol: str, start_date: str, end_date: str, 
                        cached_records: List[Dict], asset_type: str = "GOLD") -> bool:
        """
        Determine if lazy fetch is needed for this request.
        
        Args:
            symbol: Asset symbol
            start_date: Start date string
            end_date: End date string
            cached_records: Currently cached records
            asset_type: Asset type
            
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