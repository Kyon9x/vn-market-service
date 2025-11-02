"""
Gold Static Data Seeder

This module handles seeding historical SJC gold data from 2016 to current date.
It fetches data from vnstock SJC API and stores it in the historical_records table
for fast, reliable access without hitting rate limits.

Features:
- Fetches SJC gold data from 2016-01-01 to current date
- Intelligent rate limiting with Vietnamese error detection
- Progress tracking with resume capability
- Batch processing by year for reliability
- Stores data in historical_records table for database-first serving
"""

import sqlite3
import time
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from vnstock.explorer.misc import sjc_gold_price
import pandas as pd

logger = logging.getLogger(__name__)

class GoldStaticSeeder:
    """
    Seeds historical SJC gold data from 2016 to current date.
    
    This seeder fetches daily gold prices and stores them in the database
    to eliminate API rate limiting for historical queries.
    """
    
    def __init__(self, db_path: str = "db/assets.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Progress tracking
        self._total_days = 0
        self._processed_days = 0
        self._failed_days = 0
        self._start_time = 0.0
        
        # Rate limiting
        self._last_call_time = 0.0
        self._consecutive_errors = 0
        self._adaptive_delay = 1.0  # Start with 1 second delay
        
        # Date range - start from 2020 to avoid connection issues with very old data
        self.start_date = datetime(2020, 1, 1)
        self.end_date = datetime.now()
        
        logger.info(f"Gold seeder initialized: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}")
    
    def seed_all_data(self, resume: bool = True) -> Dict[str, int]:
        """
        Seed all historical gold data from 2016 to current date.
        
        Args:
            resume: Whether to resume from last processed date
            
        Returns:
            Dictionary with seeding statistics
        """
        self._start_time = time.time()
        logger.info("Starting gold historical data seeding...")
        
        # Initialize database
        self._init_database()
        
        # Calculate total trading days
        self._total_days = self._count_trading_days(self.start_date, self.end_date)
        logger.info(f"Total trading days to process: {self._total_days}")
        
        # Find last processed date if resuming
        start_processing = self.start_date
        if resume:
            last_processed = self._get_last_processed_date()
            if last_processed:
                start_processing = last_processed + timedelta(days=1)
                logger.info(f"Resuming from: {start_processing.strftime('%Y-%m-%d')}")
        
        # Process data year by year for better progress tracking
        current_year = start_processing.year
        end_year = self.end_date.year
        
        for year in range(current_year, end_year + 1):
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31)
            
            # Adjust boundaries for first/last year
            if year == current_year:
                year_start = start_processing
            if year == end_year:
                year_end = self.end_date
            
            logger.info(f"Processing year {year}: {year_start.strftime('%Y-%m-%d')} to {year_end.strftime('%Y-%m-%d')}")
            
            try:
                self._process_year_batch(year, year_start, year_end)
                logger.info(f"Completed year {year}")
            except Exception as e:
                logger.error(f"Error processing year {year}: {e}")
                # Continue with next year instead of failing completely
                continue
        
        # Final statistics
        duration = time.time() - self._start_time
        stats = {
            'total_days': self._total_days,
            'processed_days': self._processed_days,
            'failed_days': self._failed_days,
            'duration_seconds': int(duration),
            'duration_formatted': f"{duration/60:.1f} minutes",
            'success_rate': int((self._processed_days / self._total_days * 100) if self._total_days > 0 else 0)
        }
        
        logger.info(f"Gold seeding completed: {stats}")
        return stats
    
    def _process_year_batch(self, year: int, year_start: datetime, year_end: datetime):
        """Process one year of gold data."""
        current_date = year_start
        
        while current_date <= year_end:
            # Skip weekends (gold markets closed)
            if current_date.weekday() >= 5:  # Saturday, Sunday
                current_date += timedelta(days=1)
                continue
            
            date_str = current_date.strftime("%Y-%m-%d")
            
            try:
                # Check if data already exists
                if self._record_exists(date_str):
                    logger.debug(f"Data already exists for {date_str}, skipping")
                    current_date += timedelta(days=1)
                    continue
                
                # Fetch data with intelligent retry
                gold_data = self._fetch_sjc_with_retry(date_str)
                
                if gold_data:
                    self._store_historical_record(gold_data)
                    self._processed_days += 1
                    self._consecutive_errors = 0
                    logger.debug(f"✓ {date_str}: {gold_data['close']:,.0f} VND")
                else:
                    self._failed_days += 1
                    self._consecutive_errors += 1
                    logger.warning(f"✗ Failed to fetch data for {date_str}")
                
                # Progress logging
                if self._processed_days % 50 == 0:
                    progress = (self._processed_days / self._total_days) * 100
                    elapsed = time.time() - self._start_time
                    eta = (elapsed / self._processed_days * (self._total_days - self._processed_days)) if self._processed_days > 0 else 0
                    logger.info(f"Progress: {progress:.1f}% ({self._processed_days}/{self._total_days}), ETA: {eta/60:.1f} min")
                
            except Exception as e:
                self._failed_days += 1
                self._consecutive_errors += 1
                logger.error(f"Error processing {date_str}: {e}")
            
            # Adaptive delay based on consecutive errors
            if self._consecutive_errors > 3:
                self._adaptive_delay = min(self._adaptive_delay * 1.5, 10.0)  # Max 10 seconds
                logger.warning(f"Increasing delay to {self._adaptive_delay:.1f}s due to consecutive errors")
            elif self._consecutive_errors == 0:
                self._adaptive_delay = max(self._adaptive_delay * 0.9, 1.0)  # Min 1 second
            
            current_date += timedelta(days=1)
    
    def _fetch_sjc_with_retry(self, date_str: str, max_retries: int = 3) -> Optional[Dict]:
        """
        Fetch SJC gold data with intelligent retry logic.
        
        Args:
            date_str: Date string in YYYY-MM-DD format
            max_retries: Maximum number of retries
            
        Returns:
            Gold data dictionary or None if failed
        """
        for attempt in range(max_retries):
            try:
                # Rate limiting - adaptive delay
                current_time = time.time()
                time_since_last = current_time - self._last_call_time
                if time_since_last < self._adaptive_delay:
                    time.sleep(self._adaptive_delay - time_since_last)
                
                # Fetch data
                df = sjc_gold_price(date=date_str)
                self._last_call_time = time.time()
                
                if df is None or df.empty:
                    logger.debug(f"No data returned for {date_str}")
                    return None
                
                # Handle both DataFrame and Series
                if hasattr(df, 'iloc'):
                    info = df.iloc[0]
                else:
                    info = df
                
                # Extract prices
                buy_val = info.get("buy_price")
                sell_val = info.get("sell_price")
                buy_price = float(buy_val) if buy_val is not None and not pd.isna(buy_val) else 0.0
                sell_price = float(sell_val) if sell_val is not None and not pd.isna(sell_val) else 0.0
                close_price = sell_price if sell_price > 0 else buy_price
                
                if close_price <= 0:
                    logger.debug(f"Invalid price for {date_str}: buy={buy_price}, sell={sell_price}")
                    return None
                
                return {
                    "symbol": "VN.GOLD",  # Use primary symbol
                    "date": date_str,
                    "nav": close_price,
                    "open": close_price,
                    "high": close_price,
                    "low": close_price,
                    "close": close_price,
                    "adjclose": close_price,
                    "volume": 0.0,
                    "buy_price": buy_price,
                    "sell_price": sell_price
                }
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Check for Vietnamese rate limit messages or connection issues
                if self._detect_rate_limit_error(error_msg):
                    wait_time = self._parse_wait_time(str(e))
                    logger.warning(f"Rate limit/connection issue for {date_str}: waiting {wait_time}s")
                    time.sleep(wait_time+1)
                    continue
                
                # For connection issues, increase wait time more aggressively
                if any(pattern in error_msg for pattern in ["connection", "remote", "timeout"]):
                    if attempt < max_retries - 1:
                        wait_time = 5 + (2 ** attempt)  # 5, 7, 9 seconds
                        logger.debug(f"Connection issue for {date_str}, retry {attempt + 1}/{max_retries} after {wait_time}s")
                        time.sleep(wait_time+1)
                        continue
                
                # Log error and retry
                if attempt < max_retries - 1:
                    logger.debug(f"Retry {attempt + 1}/{max_retries} for {date_str}: {e}")
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Failed to fetch {date_str} after {max_retries} attempts: {e}")
        
        return None
    
    def _detect_rate_limit_error(self, error_msg: str) -> bool:
        """Detect if error message indicates rate limiting."""
        rate_limit_patterns = [
            "quá nhiều request",
            "request tới misc",
            "thử lại sau",
            "giây",
            "too many requests",
            "rate limit",
            "retry after"
        ]
        
        # Also detect connection issues that should be retried
        connection_patterns = [
            "connection aborted",
            "remote end closed",
            "connection reset",
            "timeout",
            "network unreachable"
        ]
        
        return any(pattern in error_msg for pattern in rate_limit_patterns + connection_patterns)
    
    def _parse_wait_time(self, error_msg: str) -> int:
        """Parse wait time from Vietnamese error message."""
        # Look for patterns like "15 giây" or "15 seconds"
        patterns = [
            r'(\d+)\s*giây',  # Vietnamese: 15 giây
            r'(\d+)\s*seconds?',  # English: 15 seconds
            r'(\d+)\s*sec',     # Short: 15 sec
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_msg, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        # Default wait time if parsing fails
        return 15
    
    def _store_historical_record(self, gold_data: Dict):
        """Store gold data in historical_records table."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO historical_records 
                    (symbol, asset_type, date, open, high, low, close, adjclose, volume, nav, buy_price, sell_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    gold_data["symbol"],
                    "GOLD",
                    gold_data["date"],
                    gold_data["open"],
                    gold_data["high"],
                    gold_data["low"],
                    gold_data["close"],
                    gold_data["adjclose"],
                    gold_data["volume"],
                    gold_data["nav"],
                    gold_data["buy_price"],
                    gold_data["sell_price"]
                ))
                conn.commit()
            except Exception as e:
                logger.error(f"Error storing record for {gold_data['date']}: {e}")
                conn.rollback()
                raise
    
    def _record_exists(self, date_str: str) -> bool:
        """Check if record already exists for given date."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 1 FROM historical_records 
                WHERE asset_type = 'GOLD' AND date = ?
                LIMIT 1
            ''', (date_str,))
            return cursor.fetchone() is not None
    
    def _get_last_processed_date(self) -> Optional[datetime]:
        """Get the last processed date from database."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT MAX(date) FROM historical_records 
                WHERE asset_type = 'GOLD'
            ''')
            result = cursor.fetchone()
            if result and result[0]:
                return datetime.strptime(result[0], "%Y-%m-%d")
            return None
    
    def _count_trading_days(self, start_date: datetime, end_date: datetime) -> int:
        """Count trading days (weekdays only) between two dates."""
        days = 0
        current = start_date
        while current <= end_date:
            if current.weekday() < 5:  # Monday to Friday
                days += 1
            current += timedelta(days=1)
        return days
    
    def _init_database(self):
        """Initialize database and create tables if needed."""
        # Run migrations first
        try:
            from .migrations import migrate_database
            migrate_database(str(self.db_path))
        except Exception as e:
            logger.warning(f"Could not run migrations: {e}")
        
        # Ensure historical_records table exists
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS historical_records (
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adjclose REAL,
                    volume REAL,
                    nav REAL,
                    buy_price REAL,
                    sell_price REAL,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, asset_type, date)
                )
            ''')
            
            # Create indexes for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_historical_gold_date 
                ON historical_records(asset_type, date)
            ''')
            
            conn.commit()

# Global instance
_gold_seeder = None

def get_gold_seeder(db_path: str = "db/assets.db") -> GoldStaticSeeder:
    """Get or create global gold seeder instance."""
    global _gold_seeder
    if _gold_seeder is None:
        _gold_seeder = GoldStaticSeeder(db_path)
    return _gold_seeder

if __name__ == "__main__":
    # Run seeding when executed directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Starting gold historical data seeding...")
    seeder = GoldStaticSeeder()
    stats = seeder.seed_all_data()
    
    print(f"\nSeeding completed!")
    print(f"Total days: {stats['total_days']}")
    print(f"Processed: {stats['processed_days']}")
    print(f"Failed: {stats['failed_days']}")
    print(f"Success rate: {stats['success_rate']:.1f}%")
    print(f"Duration: {stats['duration_formatted']}")