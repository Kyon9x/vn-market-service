from vnstock import Quote
from datetime import datetime
from typing import List, Dict, Optional
import logging
import pandas as pd
from app.utils.provider_logger import log_provider_call

logger = logging.getLogger(__name__)

class IndexClient:
    def __init__(self, cache_manager=None, memory_cache=None):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"symbol": lambda r: r[0].get("symbol") if r else None})
    def _fetch_index_history_from_provider(self, symbol: str, start_date: str, end_date: str) -> Optional[pd.DataFrame]:
        quote = Quote(symbol=symbol, source='VCI')
        return quote.history(start=start_date, end=end_date)
    
    @log_provider_call(provider_name="vnstock", metadata_fields={"symbol": lambda r: r.get("symbol") if isinstance(r, dict) else None})
    def _fetch_latest_index_quote_from_provider(self, symbol: str) -> Optional[pd.DataFrame]:
        quote = Quote(symbol=symbol, source='VCI')
        today = datetime.now().strftime("%Y-%m-%d")
        return quote.history(start=today, end=today)
    
    def get_index_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        try:
            history_df = self._fetch_index_history_from_provider(symbol, start_date, end_date)
            
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
        # Check memory cache first
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
                # Also store in memory cache for faster access
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "INDEX", cached_quote)
                return cached_quote
        
        try:
            quote_df = self._fetch_latest_index_quote_from_provider(symbol)
            
            if quote_df is None or quote_df.empty:
                return None
            
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
            
            # Cache the quote
            if self.memory_cache:
                self.memory_cache.set_quote(symbol, "INDEX", quote_data)
            if self.cache_manager:
                self.cache_manager.set_quote(symbol, "INDEX", quote_data)
            
            return quote_data
        except Exception as e:
            logger.error(f"Error fetching latest quote for index {symbol}: {e}")
            return None
