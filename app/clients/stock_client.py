from vnstock import Quote, Listing
from datetime import datetime
from typing import List, Dict, Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class StockClient:
    def __init__(self, cache_manager=None, memory_cache=None):
        self._quote = None
        self._listing = Listing()
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
        self._companies_cache = None
        self._cache_timestamp = None
        
        # Exchange mapping for compatibility
        self.exchange_mapping = {
            'HSX': 'HOSE',  # Ho Chi Minh Stock Exchange
            'HNX': 'HNX',   # Hanoi Stock Exchange  
            'UPCOM': 'UPCOM' # Unlisted Public Company Market
        }
    
    def get_stock_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        try:
            quote = Quote(symbol=symbol, source='VCI')
            history_df = quote.history(start=start_date, end=end_date)
            
            if history_df is None or history_df.empty:
                return []
            
            history = []
            for _, row in history_df.iterrows():
                date_val = row.get("time") or row.get("tradingDate")
                if pd.isna(date_val):
                    continue
                    
                date_str = date_val.strftime("%Y-%m-%d") if isinstance(date_val, pd.Timestamp) else str(date_val)
                
                # Convert from shortened VND format (e.g., 12) to actual VND (e.g., 12000)
                open_val = float(row.get("open", 0.0)) * 1000 if not pd.isna(row.get("open")) else 0.0
                high_val = float(row.get("high", 0.0)) * 1000 if not pd.isna(row.get("high")) else 0.0
                low_val = float(row.get("low", 0.0)) * 1000 if not pd.isna(row.get("low")) else 0.0
                close_val = float(row.get("close", 0.0)) * 1000 if not pd.isna(row.get("close")) else 0.0
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
            logger.error(f"Error fetching stock history for {symbol}: {e}")
            return []
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        # Check memory cache first
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "STOCK")
            if cached_quote:
                logger.debug(f"Using cached quote for {symbol}")
                return cached_quote
        
        # Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "STOCK")
            if cached_quote:
                logger.debug(f"Using persistent cached quote for {symbol}")
                # Also store in memory cache for faster access
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "STOCK", cached_quote)
                return cached_quote
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            quote = Quote(symbol=symbol, source='VCI')
            quote_df = quote.history(start=today, end=today)
            
            if quote_df is None or quote_df.empty:
                return None
            
            info = quote_df.iloc[-1]
            date_val = info.get("time") or info.get("tradingDate")
            if isinstance(date_val, pd.Timestamp):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val) if date_val else datetime.now().strftime("%Y-%m-%d")
            
            # Convert from shortened VND format (e.g., 12) to actual VND (e.g., 12000)
            open_val = float(info.get("open", 0.0)) * 1000 if not pd.isna(info.get("open")) else 0.0
            high_val = float(info.get("high", 0.0)) * 1000 if not pd.isna(info.get("high")) else 0.0
            low_val = float(info.get("low", 0.0)) * 1000 if not pd.isna(info.get("low")) else 0.0
            close_val = float(info.get("close", 0.0)) * 1000 if not pd.isna(info.get("close")) else 0.0
            volume_val = float(info.get("volume", 0.0)) if not pd.isna(info.get("volume")) else 0.0
            
            quote_data = {
                "symbol": symbol,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "adjclose": close_val,  # For stocks, adjclose is typically the same as close
                "volume": volume_val,
                "date": date_str
            }
            
            # Cache the quote
            if self.memory_cache:
                self.memory_cache.set_quote(symbol, "STOCK", quote_data)
            if self.cache_manager:
                self.cache_manager.set_quote(symbol, "STOCK", quote_data)
            
            return quote_data
        except Exception as e:
            logger.error(f"Error fetching latest quote for {symbol}: {e}")
            return None
    
    def _get_companies_df(self):
        """Get companies DataFrame with caching and filtering."""
        # Simple in-memory cache for companies data (refresh every hour)
        import time
        current_time = time.time()
        
        if (self._companies_cache is not None and 
            self._cache_timestamp is not None and 
            current_time - self._cache_timestamp < 3600):  # 1 hour cache
            return self._companies_cache
        
        try:
            companies_df = self._listing.symbols_by_exchange()
            
            # Filter for active stocks only: type='STOCK' and exchange != 'DELISTED'
            if companies_df is not None and not companies_df.empty:
                # Apply filters
                filtered_df = companies_df[
                    (companies_df['type'] == 'STOCK') & 
                    (companies_df['exchange'] != 'DELISTED')
                ].copy()
                
                self._companies_cache = filtered_df
                self._cache_timestamp = current_time
                logger.info(f"Refreshed companies cache: {len(filtered_df)} active stocks (filtered from {len(companies_df)} total)")
                return filtered_df
            else:
                self._companies_cache = companies_df
                self._cache_timestamp = current_time
                return companies_df
                
        except Exception as e:
            logger.error(f"Error fetching companies data: {e}")
            return self._companies_cache  # Return stale cache if available
    
    def search_stock(self, symbol: str) -> Optional[Dict]:
        # Check cache first
        if self.cache_manager:
            cached_asset = self.cache_manager.get_asset(symbol)
            if cached_asset and cached_asset.get('asset_type') == 'STOCK':
                logger.debug(f"Using cached asset info for {symbol}")
                return {
                    "symbol": cached_asset['symbol'],
                    "company_name": cached_asset['name'],
                    "exchange": cached_asset.get('exchange', ''),
                    "industry": cached_asset['metadata'].get('industry', '') if cached_asset.get('metadata') else '',
                    "company_type": cached_asset['metadata'].get('company_type', '') if cached_asset.get('metadata') else ''
                }
        
        try:
            # Try to get company info from listing (with caching)
            companies_df = self._get_companies_df()
            if companies_df is not None and not companies_df.empty:
                company_row = companies_df[companies_df['symbol'] == symbol]
                if not company_row.empty:
                    info = company_row.iloc[0]
                    company_name = str(info.get("organ_name", symbol))
                    industry = str(info.get("organ_type", ""))
                    company_type = str(info.get("exchange", ""))  # Use exchange as company_type fallback
                    
                    raw_exchange = str(info.get("exchange", ""))
                    mapped_exchange = self.exchange_mapping.get(raw_exchange, raw_exchange)
                    
                    result = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": mapped_exchange,
                        "industry": industry,
                        "company_type": company_type
                    }
                    
                    # Cache the result
                    if self.cache_manager:
                        self.cache_manager.set_asset(
                            symbol=symbol,
                            name=company_name,
                            asset_type="STOCK",
                            asset_class="Equity",
                            asset_sub_class="Stock",
                            exchange=mapped_exchange,
                            currency="VND",
                            metadata={"industry": industry, "company_type": company_type}
                        )
                    
                    return result
            
            # Stock not found in listing
            return None
        except Exception as e:
            logger.error(f"Error searching stock {symbol}: {e}")
            return None
    
    def search_stocks_by_name(self, query: str, limit: int = 10) -> List[Dict]:
        """Search stocks by partial name match (case-insensitive)."""
        # Check cache first
        if self.cache_manager:
            cached_results = self.cache_manager.search_assets_by_name(query, limit)
            stock_results = [r for r in cached_results if r.get('asset_type') == 'STOCK']
            if stock_results:
                logger.debug(f"Using cached search results for stocks '{query}'")
                return [
                    {
                        "symbol": r['symbol'],
                        "company_name": r['name'],
                        "exchange": r.get('exchange', ''),
                        "industry": r.get('metadata', {}).get('industry', '') if r.get('metadata') else '',
                        "company_type": r.get('metadata', {}).get('company_type', '') if r.get('metadata') else ''
                    }
                    for r in stock_results[:limit]
                ]
        
        try:
            companies_df = self._get_companies_df()
            if companies_df is None or companies_df.empty:
                return []
            
            query_lower = query.lower()
            results = []
            
            for _, row in companies_df.iterrows():
                symbol = str(row.get("symbol", ""))
                company_name = str(row.get("organ_name", ""))
                
                # Match on symbol or company name
                if query_lower in symbol.lower() or query_lower in company_name.lower():
                    industry = str(row.get("organ_short_name", ""))
                    company_type = str(row.get("exchange", ""))  # Use exchange as company_type fallback
                    
                    raw_exchange = str(row.get("exchange", ""))
                    mapped_exchange = self.exchange_mapping.get(raw_exchange, raw_exchange)
                    
                    result = {
                        "symbol": symbol,
                        "company_name": company_name,
                        "exchange": mapped_exchange,
                        "industry": industry,
                        "company_type": company_type
                    }
                    results.append(result)
                    
                    # Cache individual asset
                    if self.cache_manager:
                        self.cache_manager.set_asset(
                            symbol=symbol,
                            name=company_name,
                            asset_type="STOCK",
                            asset_class="Equity",
                            asset_sub_class="Stock",
                            exchange=mapped_exchange,
                            currency="VND",
                            metadata={"industry": industry, "company_type": company_type}
                        )
                    
                    if len(results) >= limit:
                        break
            
            return results
        except Exception as e:
            logger.error(f"Error searching stocks by name '{query}': {e}")
            return []
