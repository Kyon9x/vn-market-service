"""
Historical Cache Manager - Incremental fetching for historical data.

This module implements smart caching for historical market data:
- Stores individual records (one row per symbol per date)
- Fetches only missing date ranges
- Merges cached and new data
- Historical data never expires (immutable)
"""

import sqlite3
import json
import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

class HistoricalCacheManager:
    """
    Manages incremental caching of historical market data.
    
    Key features:
    - Store individual records instead of date ranges
    - Smart detection of missing dates
    - Minimal API calls by fetching only gaps
    - Automatic merging of cached and fresh data
    """
    
    def __init__(self, db_path: str = "db/assets.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Ensure historical_records table exists."""
        try:
            # Import at runtime to avoid circular dependency
            import importlib
            migrations = importlib.import_module('.migrations', package='app.cache')
            migrations.migrate_database(str(self.db_path))
        except Exception as e:
            logger.warning(f"Could not run migrations (table may already exist): {e}")
    
    def store_historical_records(self, symbol: str, asset_type: str, 
                                records: List[Dict]) -> int:
        """
        Store individual historical records in database.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset (STOCK, FUND, INDEX, GOLD)
            records: List of historical data records
            
        Returns:
            Number of records stored
        """
        if not records:
            return 0
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                stored_count = 0
                
                for record in records:
                    # Extract date field (handle different formats)
                    record_date = self._extract_date(record)
                    if not record_date:
                        logger.warning(f"Skipping record without date: {record}")
                        continue
                    
                    # Extract numeric fields
                    open_price = self._safe_float(record.get('open'))
                    high_price = self._safe_float(record.get('high'))
                    low_price = self._safe_float(record.get('low'))
                    close_price = self._safe_float(record.get('close'))
                    adjclose = self._safe_float(record.get('adjclose'))
                    volume = self._safe_float(record.get('volume'))
                    nav = self._safe_float(record.get('nav'))
                    buy_price = self._safe_float(record.get('buy_price'))
                    sell_price = self._safe_float(record.get('sell_price'))
                    
                    # Store complete record as JSON for flexibility
                    data_json = json.dumps(record)
                    
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_records
                        (symbol, asset_type, date, open, high, low, close, adjclose,
                         volume, nav, buy_price, sell_price, data_json, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        symbol, asset_type, record_date,
                        open_price, high_price, low_price, close_price, adjclose,
                        volume, nav, buy_price, sell_price, data_json,
                        datetime.now()
                    ))
                    stored_count += 1
                
                conn.commit()
                logger.info(f"Stored {stored_count} historical records for {symbol} ({asset_type})")
                return stored_count
                
            except Exception as e:
                logger.error(f"Error storing historical records for {symbol}: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()
    
    def mark_date_range_as_fetched(self, symbol: str, asset_type: str, 
                                    start_date: str, end_date: str) -> int:
        """
        Mark a date range as fetched by creating null records for missing dates.
        This prevents repeated API calls for dates with no trading data (weekends/holidays).
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Number of null records created
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return 0
        
        # Get dates that already exist in cache
        cached_dates = self.get_cached_dates(symbol, start_date, end_date, asset_type)
        
        # Generate all dates in range
        all_dates = set()
        current = start
        while current <= end:
            all_dates.add(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        # Find dates that need null markers
        dates_to_mark = all_dates - cached_dates
        
        if not dates_to_mark:
            return 0
        
        # Create null records for these dates
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                marked_count = 0
                
                for date_str in dates_to_mark:
                    # Insert a null record (all prices NULL, volume 0)
                    cursor.execute('''
                        INSERT OR REPLACE INTO historical_records
                        (symbol, asset_type, date, open, high, low, close, adjclose,
                         volume, nav, buy_price, sell_price, data_json, updated_at)
                        VALUES (?, ?, ?, NULL, NULL, NULL, NULL, NULL, 0, NULL, NULL, NULL, '{}', ?)
                    ''', (symbol, asset_type, date_str, datetime.now()))
                    marked_count += 1
                
                conn.commit()
                logger.debug(f"Marked {marked_count} no-data dates for {symbol} ({asset_type})")
                return marked_count
                
            except Exception as e:
                logger.error(f"Error marking date range as fetched for {symbol}: {e}")
                conn.rollback()
                return 0
            finally:
                conn.close()
    
    def get_cached_dates(self, symbol: str, start_date: str, end_date: str,
                        asset_type: str) -> Set[str]:
        """
        Get set of dates that are already cached.
        
        Args:
            symbol: Asset symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            asset_type: Type of asset
            
        Returns:
            Set of cached date strings
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT DISTINCT date FROM historical_records
                    WHERE symbol = ? AND asset_type = ?
                    AND date BETWEEN ? AND ?
                    ORDER BY date
                ''', (symbol, asset_type, start_date, end_date))
                
                cached_dates = {row[0] for row in cursor.fetchall()}
                logger.debug(f"Found {len(cached_dates)} cached dates for {symbol} "
                           f"between {start_date} and {end_date}")
                return cached_dates
                
            except Exception as e:
                logger.error(f"Error getting cached dates for {symbol}: {e}")
                return set()
            finally:
                conn.close()
    
    def get_cached_records(self, symbol: str, start_date: str, end_date: str,
                          asset_type: str) -> List[Dict]:
        """
        Get cached historical records for a date range.
        
        Args:
            symbol: Asset symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            asset_type: Type of asset
            
        Returns:
            List of historical records
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT data_json FROM historical_records
                    WHERE symbol = ? AND asset_type = ?
                    AND date BETWEEN ? AND ?
                    AND data_json != '{}'
                    ORDER BY date ASC
                ''', (symbol, asset_type, start_date, end_date))
                
                records = [json.loads(row[0]) for row in cursor.fetchall()]
                logger.debug(f"Retrieved {len(records)} cached records for {symbol}")
                return records
                
            except Exception as e:
                logger.error(f"Error retrieving cached records for {symbol}: {e}")
                return []
            finally:
                conn.close()
    
    def calculate_missing_date_ranges(self, start_date: str, end_date: str,
                                     cached_dates: Set[str]) -> List[Tuple[str, str]]:
        """
        Calculate missing date ranges that need to be fetched.
        
        Args:
            start_date: Requested start date (YYYY-MM-DD)
            end_date: Requested end date (YYYY-MM-DD)
            cached_dates: Set of already cached dates
            
        Returns:
            List of (start, end) tuples for missing ranges
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return [(start_date, end_date)]
        
        # Generate all requested dates
        all_dates = set()
        current = start
        while current <= end:
            all_dates.add(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        # Calculate missing dates
        missing_dates = all_dates - cached_dates
        
        if not missing_dates:
            return []
        
        # Convert to sorted list
        missing_sorted = sorted([datetime.strptime(d, '%Y-%m-%d').date() 
                                for d in missing_dates])
        
        # Group consecutive dates into ranges
        ranges = []
        range_start = missing_sorted[0]
        range_end = missing_sorted[0]
        
        for current_date in missing_sorted[1:]:
            if (current_date - range_end).days == 1:
                # Consecutive date, extend range
                range_end = current_date
            else:
                # Gap found, save current range and start new one
                ranges.append((
                    range_start.strftime('%Y-%m-%d'),
                    range_end.strftime('%Y-%m-%d')
                ))
                range_start = current_date
                range_end = current_date
        
        # Add the last range
        ranges.append((
            range_start.strftime('%Y-%m-%d'),
            range_end.strftime('%Y-%m-%d')
        ))
        
        logger.info(f"Missing {len(missing_dates)} dates in {len(ranges)} ranges")
        return ranges
    
    def should_fetch_full_range(self, missing_ranges: List[Tuple[str, str]],
                               total_days_requested: int) -> bool:
        """
        Decide whether to fetch the full range or just missing parts.
        
        Strategy:
        - If missing > 80% of requested range: fetch full range (more efficient)
        - If missing < 20%: fetch only missing (minimal API calls)
        - Otherwise: fetch missing ranges
        
        Args:
            missing_ranges: List of missing date ranges
            total_days_requested: Total days in requested range
            
        Returns:
            True if should fetch full range, False if should fetch missing parts
        """
        if not missing_ranges:
            return False
        
        total_missing_days = sum(
            (datetime.strptime(end, '%Y-%m-%d') - 
             datetime.strptime(start, '%Y-%m-%d')).days + 1
            for start, end in missing_ranges
        )
        
        missing_percentage = (total_missing_days / total_days_requested * 100) if total_days_requested > 0 else 0
        
        logger.debug(f"Missing {total_missing_days}/{total_days_requested} days "
                    f"({missing_percentage:.1f}%)")
        
        # If missing more than 80%, fetch everything
        return missing_percentage > 80
    
    def merge_historical_data(self, cached_records: List[Dict],
                             new_records: List[Dict]) -> List[Dict]:
        """
        Merge cached and newly fetched historical records.
        
        Args:
            cached_records: Records from cache
            new_records: Newly fetched records
            
        Returns:
            Merged and sorted list of records
        """
        # Create a dict to deduplicate by date
        merged = {}
        
        for record in cached_records:
            record_date = self._extract_date(record)
            if record_date:
                merged[record_date] = record
        
        # New records override cached ones (fresher data)
        for record in new_records:
            record_date = self._extract_date(record)
            if record_date:
                merged[record_date] = record
        
        # Sort by date
        sorted_records = sorted(merged.values(), 
                              key=lambda x: self._extract_date(x) or '')
        
        logger.debug(f"Merged {len(cached_records)} cached + {len(new_records)} new "
                    f"= {len(sorted_records)} total records")
        
        return sorted_records
    
    def get_cache_stats(self, symbol: Optional[str] = None) -> Dict:
        """
        Get statistics about cached historical data.
        
        Args:
            symbol: Optional symbol to filter stats
            
        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                stats = {}
                
                if symbol:
                    # Stats for specific symbol
                    cursor.execute('''
                        SELECT asset_type, COUNT(*), MIN(date), MAX(date)
                        FROM historical_records
                        WHERE symbol = ?
                        GROUP BY asset_type
                    ''', (symbol,))
                    
                    stats['symbol'] = symbol
                    stats['by_asset_type'] = {}
                    for row in cursor.fetchall():
                        stats['by_asset_type'][row[0]] = {
                            'record_count': row[1],
                            'earliest_date': row[2],
                            'latest_date': row[3]
                        }
                else:
                    # Overall stats
                    cursor.execute('''
                        SELECT COUNT(*), COUNT(DISTINCT symbol), 
                               COUNT(DISTINCT asset_type)
                        FROM historical_records
                    ''')
                    row = cursor.fetchone()
                    stats['total_records'] = row[0]
                    stats['unique_symbols'] = row[1]
                    stats['asset_types'] = row[2]
                    
                    # Top symbols by record count
                    cursor.execute('''
                        SELECT symbol, asset_type, COUNT(*) as cnt
                        FROM historical_records
                        GROUP BY symbol, asset_type
                        ORDER BY cnt DESC
                        LIMIT 10
                    ''')
                    stats['top_symbols'] = [
                        {'symbol': row[0], 'asset_type': row[1], 'records': row[2]}
                        for row in cursor.fetchall()
                    ]
                
                return stats
                
            except Exception as e:
                logger.error(f"Error getting cache stats: {e}")
                return {}
            finally:
                conn.close()
    
    def _extract_date(self, record: Dict) -> Optional[str]:
        """Extract and normalize date from record."""
        # Try different date field names
        for field in ['date', 'time', 'trading_date', 'Date', 'Time']:
            if field in record:
                date_value = record[field]
                if isinstance(date_value, str):
                    # Try to parse and normalize
                    try:
                        dt = datetime.strptime(date_value, '%Y-%m-%d')
                        return dt.strftime('%Y-%m-%d')
                    except ValueError:
                        try:
                            dt = datetime.strptime(date_value[:10], '%Y-%m-%d')
                            return dt.strftime('%Y-%m-%d')
                        except ValueError:
                            pass
                return str(date_value)[:10]
        return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def get_most_recent_record(self, symbol: str, asset_type: str, 
                              lookback_days: int = 30) -> Optional[Dict]:
        """
        Get the most recent non-null historical record for a symbol.
        Used as fallback for weekend/holiday quote requests.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset (STOCK, FUND, INDEX, GOLD)
            lookback_days: Maximum days to look back (default 30)
            
        Returns:
            Most recent record dict or None if not found
        """
        lookback_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT data_json FROM historical_records
                    WHERE symbol = ? AND asset_type = ?
                    AND date BETWEEN ? AND ?
                    AND data_json != '{}'
                    ORDER BY date DESC
                    LIMIT 1
                ''', (symbol, asset_type, lookback_date, today))
                
                row = cursor.fetchone()
                if row:
                    record = json.loads(row[0])
                    # Ensure symbol is in the record for API response validation
                    if 'symbol' not in record:
                        record['symbol'] = symbol
                    logger.debug(f"Found most recent record for {symbol} dated {record.get('date')}")
                    return record
                
                logger.debug(f"No recent records found for {symbol} in last {lookback_days} days")
                return None
                
            except Exception as e:
                logger.error(f"Error getting most recent record for {symbol}: {e}")
                return None
            finally:
                conn.close()

# Global instance
_historical_cache: Optional[HistoricalCacheManager] = None

def get_historical_cache(db_path: str = "db/assets.db") -> HistoricalCacheManager:
    """
    Get or create the global historical cache manager instance.
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        HistoricalCacheManager instance
    """
    global _historical_cache
    if _historical_cache is None:
        _historical_cache = HistoricalCacheManager(db_path)
    return _historical_cache

if __name__ == "__main__":
    # Demo and testing
    logging.basicConfig(level=logging.INFO)
    
    cache = HistoricalCacheManager()
    
    # Test with sample data
    sample_records = [
        {'date': '2025-10-01', 'open': 100, 'close': 105, 'volume': 1000},
        {'date': '2025-10-02', 'open': 105, 'close': 110, 'volume': 1200},
        {'date': '2025-10-03', 'open': 110, 'close': 108, 'volume': 1100},
    ]
    
    print("\n=== Storing Sample Records ===")
    count = cache.store_historical_records('TEST', 'STOCK', sample_records)
    print(f"Stored {count} records")
    
    print("\n=== Checking Cached Dates ===")
    cached = cache.get_cached_dates('TEST', '2025-10-01', '2025-10-05', 'STOCK')
    print(f"Cached dates: {cached}")
    
    print("\n=== Calculating Missing Ranges ===")
    missing = cache.calculate_missing_date_ranges(
        '2025-10-01', '2025-10-05', cached
    )
    print(f"Missing ranges: {missing}")
    
    print("\n=== Cache Stats ===")
    stats = cache.get_cache_stats('TEST')
    print(json.dumps(stats, indent=2))
