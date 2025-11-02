"""
Database migration module for cache schema updates.

This module handles database migrations to add new tables and indexes
for the smart caching system.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CacheMigration:
    """Handles database migrations for the cache system."""
    
    def __init__(self, db_path: str = "db/assets.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def run_migrations(self):
        """Run all pending migrations."""
        logger.info("Starting cache database migrations...")
        
        try:
            self._migrate_v1_historical_records()
            logger.info("All migrations completed successfully")
            return True
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return False
    
    def _migrate_v1_historical_records(self):
        """
        Migration V1: Create historical_records table for incremental caching.
        
        This table stores individual historical records (one row per symbol per date)
        instead of caching entire date ranges. This enables incremental fetching.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='historical_records'
            """)
            
            if cursor.fetchone():
                logger.info("historical_records table already exists, skipping migration")
                return
            
            logger.info("Creating historical_records table...")
            
            # Create historical_records table
            # Historical data never expires (immutable market data)
            cursor.execute('''
                CREATE TABLE historical_records (
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
            
            # Create indexes for efficient querying
            cursor.execute('''
                CREATE INDEX idx_historical_symbol_type_date 
                ON historical_records(symbol, asset_type, date)
            ''')
            
            cursor.execute('''
                CREATE INDEX idx_historical_date 
                ON historical_records(date)
            ''')
            
            cursor.execute('''
                CREATE INDEX idx_historical_created 
                ON historical_records(created_at)
            ''')
            
            cursor.execute('''
                CREATE INDEX idx_historical_symbol 
                ON historical_records(symbol)
            ''')
            
            conn.commit()
            logger.info("historical_records table created successfully")
            
        except Exception as e:
            logger.error(f"Error in migration V1: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def check_migration_status(self) -> dict:
        """Check the status of all migrations."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            
            # Check if historical_records table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='historical_records'
            """)
            has_historical_records = cursor.fetchone() is not None
            
            # Get row counts
            stats = {}
            if has_historical_records:
                cursor.execute("SELECT COUNT(*) FROM historical_records")
                stats['historical_records_count'] = cursor.fetchone()[0]
            
            return {
                'has_historical_records_table': has_historical_records,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"Error checking migration status: {e}")
            return {}
        finally:
            conn.close()

def migrate_database(db_path: str = "db/assets.db"):
    """
    Run all database migrations.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        True if migrations succeeded, False otherwise
    """
    migration = CacheMigration(db_path)
    return migration.run_migrations()

def check_migration_status(db_path: str = "db/assets.db") -> dict:
    """
    Check the status of database migrations.
    
    Args:
        db_path: Path to the SQLite database file
        
    Returns:
        Dictionary with migration status information
    """
    migration = CacheMigration(db_path)
    return migration.check_migration_status()

if __name__ == "__main__":
    # Run migrations when executed directly
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Running cache database migrations...")
    success = migrate_database()
    
    if success:
        print("Migrations completed successfully!")
        status = check_migration_status()
        print(f"Migration status: {status}")
    else:
        print("Migrations failed!")
