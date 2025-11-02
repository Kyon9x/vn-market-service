import sqlite3
import json
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class CacheManager:
    """SQLite-based cache manager for persistent data storage with TTL support."""
    
    def __init__(self, db_path: str = "db/assets.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_database()
    
    def _init_database(self):
        """Initialize cache database with required tables and run migrations."""
        # Run migrations first to create historical_records table
        try:
            from .migrations import migrate_database
            migrate_database(str(self.db_path))
        except Exception as e:
            logger.warning(f"Could not run migrations: {e}")
        
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Assets table for symbol mappings and metadata
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS assets (
                        symbol TEXT PRIMARY KEY,
                        name TEXT,
                        asset_type TEXT,
                        asset_class TEXT,
                        asset_sub_class TEXT,
                        exchange TEXT,
                        currency TEXT,
                        data_source TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Quotes cache with TTL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS quotes (
                        symbol TEXT,
                        asset_type TEXT,
                        quote_data TEXT,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (symbol, asset_type)
                    )
                ''')
                
                # Search results cache with TTL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS search_results (
                        query TEXT,
                        results TEXT,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (query)
                    )
                ''')
                
                # Historical data cache with TTL
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS historical_data (
                        symbol TEXT,
                        start_date TEXT,
                        end_date TEXT,
                        asset_type TEXT,
                        history_data TEXT,
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (symbol, start_date, end_date, asset_type)
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_quotes_expires ON quotes(expires_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_search_expires ON search_results(expires_at)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_historical_expires ON historical_data(expires_at)')
                
                conn.commit()
                logger.info("Cache database initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing cache database: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def set_asset(self, symbol: str, name: str, asset_type: str, 
                  asset_class: str = "", asset_sub_class: str = "",
                  exchange: str = "", currency: str = "VND", 
                  data_source: str = "VN_MARKET", metadata: Optional[Dict] = None):
        """Cache asset information."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO assets 
                    (symbol, name, asset_type, asset_class, asset_sub_class, 
                     exchange, currency, data_source, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol, name, asset_type, asset_class, asset_sub_class,
                    exchange, currency, data_source, 
                    json.dumps(metadata) if metadata else None,
                    datetime.now()
                ))
                conn.commit()
            except Exception as e:
                logger.error(f"Error caching asset {symbol}: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_asset(self, symbol: str) -> Optional[Dict]:
        """Retrieve cached asset information."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT symbol, name, asset_type, asset_class, asset_sub_class,
                           exchange, currency, data_source, metadata
                    FROM assets WHERE symbol = ?
                ''', (symbol,))
                row = cursor.fetchone()
                if row:
                    metadata: Dict = json.loads(row[8]) if row[8] and row[8] != 'null' else {}
                    return {
                        'symbol': row[0],
                        'name': row[1],
                        'asset_type': row[2],
                        'asset_class': row[3],
                        'asset_sub_class': row[4],
                        'exchange': row[5],
                        'currency': row[6],
                        'data_source': row[7],
                        'metadata': metadata
                    }
                return None
            except Exception as e:
                logger.error(f"Error retrieving asset {symbol}: {e}")
                return None
            finally:
                conn.close()
    
    def search_assets_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """Search assets by name or symbol using FTS."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT symbol, name, asset_type, asset_class, asset_sub_class,
                           exchange, currency, data_source
                    FROM assets 
                    WHERE symbol LIKE ? OR name LIKE ?
                    ORDER BY 
                        CASE WHEN symbol LIKE ? THEN 1 ELSE 2 END,
                        symbol
                    LIMIT ?
                ''', (f'%{query}%', f'%{query}%', f'{query}%', limit))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        'symbol': row[0],
                        'name': row[1],
                        'asset_type': row[2],
                        'asset_class': row[3],
                        'asset_sub_class': row[4],
                        'exchange': row[5],
                        'currency': row[6],
                        'data_source': row[7]
                    })
                return results
            except Exception as e:
                logger.error(f"Error searching assets by name '{query}': {e}")
                return []
            finally:
                conn.close()
    
    def set_quote(self, symbol: str, asset_type: str, quote_data: Dict, ttl_seconds: int = 300):
        """Cache quote data with TTL."""
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO quotes (symbol, asset_type, quote_data, expires_at)
                    VALUES (?, ?, ?, ?)
                ''', (symbol, asset_type, json.dumps(quote_data), expires_at))
                conn.commit()
            except Exception as e:
                logger.error(f"Error caching quote for {symbol}: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_quote(self, symbol: str, asset_type: str) -> Optional[Dict]:
        """Retrieve cached quote data if not expired."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT quote_data, expires_at FROM quotes 
                    WHERE symbol = ? AND asset_type = ? AND expires_at > ?
                ''', (symbol, asset_type, datetime.now()))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except Exception as e:
                logger.error(f"Error retrieving quote for {symbol}: {e}")
                return None
            finally:
                conn.close()
    
    def set_search_results(self, query: str, results: List[Dict], ttl_seconds: int = 1800):
        """Cache search results with TTL (30 minutes default)."""
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO search_results (query, results, expires_at)
                    VALUES (?, ?, ?)
                ''', (query.upper(), json.dumps(results), expires_at))
                conn.commit()
            except Exception as e:
                logger.error(f"Error caching search results for '{query}': {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_search_results(self, query: str) -> Optional[List[Dict]]:
        """Retrieve cached search results if not expired."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT results, expires_at FROM search_results 
                    WHERE query = ? AND expires_at > ?
                ''', (query.upper(), datetime.now()))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except Exception as e:
                logger.error(f"Error retrieving search results for '{query}': {e}")
                return None
            finally:
                conn.close()
    
    def set_historical_data(self, symbol: str, start_date: str, end_date: str, 
                           asset_type: str, history_data: List[Dict], ttl_seconds: int = 86400):
        """Cache historical data with TTL (24 hours default)."""
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO historical_data 
                    (symbol, start_date, end_date, asset_type, history_data, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (symbol, start_date, end_date, asset_type, json.dumps(history_data), expires_at))
                conn.commit()
            except Exception as e:
                logger.error(f"Error caching historical data for {symbol}: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_historical_data(self, symbol: str, start_date: str, end_date: str, 
                           asset_type: str) -> Optional[List[Dict]]:
        """Retrieve cached historical data if not expired."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT history_data, expires_at FROM historical_data 
                    WHERE symbol = ? AND start_date = ? AND end_date = ? 
                    AND asset_type = ? AND expires_at > ?
                ''', (symbol, start_date, end_date, asset_type, datetime.now()))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except Exception as e:
                logger.error(f"Error retrieving historical data for {symbol}: {e}")
                return None
            finally:
                conn.close()
    
    def cleanup_expired(self):
        """Remove expired cache entries."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                current_time = datetime.now()
                
                cursor.execute('DELETE FROM quotes WHERE expires_at <= ?', (current_time,))
                cursor.execute('DELETE FROM search_results WHERE expires_at <= ?', (current_time,))
                cursor.execute('DELETE FROM historical_data WHERE expires_at <= ?', (current_time,))
                
                deleted_rows = cursor.rowcount
                conn.commit()
                if deleted_rows > 0:
                    logger.info(f"Cleaned up {deleted_rows} expired cache entries")
            except Exception as e:
                logger.error(f"Error cleaning up expired cache entries: {e}")
                conn.rollback()
            finally:
                conn.close()
    
    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                stats = {}
                
                cursor.execute('SELECT COUNT(*) FROM assets')
                stats['assets'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM quotes WHERE expires_at > ?', (datetime.now(),))
                stats['valid_quotes'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM search_results WHERE expires_at > ?', (datetime.now(),))
                stats['valid_searches'] = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM historical_data WHERE expires_at > ?', (datetime.now(),))
                stats['valid_historical'] = cursor.fetchone()[0]
                
                return stats
            except Exception as e:
                logger.error(f"Error getting cache stats: {e}")
                return {}
            finally:
                conn.close()