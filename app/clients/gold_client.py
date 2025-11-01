from vnstock.explorer.misc import sjc_gold_price, btmc_goldprice
from vnstock import Vnstock
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class GoldClient:
    # Provider configurations
    PROVIDERS = {
        "sjc": {
            "name": "Saigon Jewelry Company",
            "symbols": ["VN.GOLD.SJC", "SJC.GOLD"],
            "api_func": "sjc_gold_price"
        },
        "btmc": {
            "name": "Bao Tin Minh Chau",
            "symbols": ["VN.GOLD.BTMC", "BTMC.GOLD"],
            "api_func": "btmc_goldprice"
        },
        "msn": {
            "name": "Microsoft/MSN",
            "symbols": ["GOLD.MSN", "MSN.GOLD"],
            "api_func": "world_index"
        }
    }
    
    def __init__(self, cache_manager=None, memory_cache=None):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
    
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
    
    def get_gold_history(self, symbol: str, start_date: str, end_date: str) -> List[Dict]:
        """Fetch historical gold prices for a given provider."""
        # Check cache first
        if self.cache_manager:
            cached_history = self.cache_manager.get_historical_data(symbol, start_date, end_date, "GOLD")
            if cached_history:
                logger.debug(f"Using cached historical data for {symbol}")
                return cached_history
        
        try:
            _, provider = self.parse_symbol(symbol)
            
            history = []
            if provider == "sjc":
                history = self._get_sjc_history(start_date, end_date)
            elif provider == "btmc":
                history = self._get_btmc_history(start_date, end_date)
            elif provider == "msn":
                history = self._get_msn_history(start_date, end_date)
            
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
        """Fetch SJC gold historical prices."""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            history = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                
                try:
                    df = sjc_gold_price(date=date_str)
                    
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
    
    def _get_btmc_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch BTMC gold historical prices (limited - mostly current prices)."""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            history = []
            current_dt = start_dt
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                
                try:
                    df = btmc_goldprice()
                    
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
                    logger.warning(f"BTMC API error for {date_str}: {date_error}, skipping date")
                
                # Skip this date and continue to next
                current_dt += timedelta(days=1)
            
            return history
        except Exception as e:
            logger.error(f"Error in _get_btmc_history: {e}")
            return []
    
    def _get_msn_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Fetch MSN/world gold commodity historical prices."""
        try:
            vnstock = Vnstock()
            gold_idx = vnstock.world_index(symbol='GOLD', source='MSN')
            
            df = gold_idx.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or df.empty:
                logger.warning("MSN API returned empty data")
                return []
            
            history = []
            for idx, row in df.iterrows():
                date_str = pd.to_datetime(row['time']).strftime('%Y-%m-%d') if 'time' in row else pd.to_datetime(row.name).strftime('%Y-%m-%d')
                
                history.append({
                    "date": date_str,
                    "nav": float(row.get('close', 0.0)),
                    "open": float(row.get('open', 0.0)),
                    "high": float(row.get('high', 0.0)),
                    "low": float(row.get('low', 0.0)),
                    "close": float(row.get('close', 0.0)),
                    "adjclose": float(row.get('close', 0.0)),
                    "volume": float(row.get('volume', 0.0))
                })
            
            return history
        except Exception as e:
            logger.error(f"Error fetching MSN history: {e}")
            return []

    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch the latest gold price for a given provider."""
        # Check memory cache first
        if self.memory_cache:
            cached_quote = self.memory_cache.get_quote(symbol, "GOLD")
            if cached_quote:
                logger.debug(f"Using cached gold quote for {symbol}")
                return cached_quote
        
        # Check persistent cache
        if self.cache_manager:
            cached_quote = self.cache_manager.get_quote(symbol, "GOLD")
            if cached_quote:
                logger.debug(f"Using persistent cached gold quote for {symbol}")
                # Also store in memory cache for faster access
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "GOLD", cached_quote)
                return cached_quote
        
        try:
            _, provider = self.parse_symbol(symbol)
            
            quote_data = None
            if provider == "sjc":
                quote_data = self._get_sjc_quote(symbol)
            elif provider == "btmc":
                quote_data = self._get_btmc_quote(symbol)
            elif provider == "msn":
                quote_data = self._get_msn_quote(symbol)
            
            # Cache the quote
            if quote_data:
                if self.memory_cache:
                    self.memory_cache.set_quote(symbol, "GOLD", quote_data)
                if self.cache_manager:
                    self.cache_manager.set_quote(symbol, "GOLD", quote_data)
            
            return quote_data
        except ValueError as e:
            logger.debug(f"Invalid symbol: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching gold quote for {symbol}: {e}")
            return None
    
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

    
    def _get_btmc_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest BTMC gold price."""
        try:
            df = btmc_goldprice()
            
            if df is None or df.empty:
                logger.warning("BTMC API returned empty data")
                return None
            
            info = df.iloc[0]
            time_val = info.get("time")
            date_str = pd.to_datetime(time_val).strftime("%Y-%m-%d") if time_val else datetime.now().strftime("%Y-%m-%d")
            
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
            logger.error(f"Error fetching BTMC quote: {e}")
            return None

    
    def _get_msn_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest MSN/world gold commodity price."""
        try:
            vnstock = Vnstock()
            gold_idx = vnstock.world_index(symbol='GOLD', source='MSN')
            
            df = gold_idx.quote.history(start=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), 
                                       end=datetime.now().strftime('%Y-%m-%d'), 
                                       interval='1D')
            
            if df is None or df.empty:
                logger.warning("MSN API returned empty data")
                return None
            
            latest = df.iloc[-1]
            date_str = pd.to_datetime(latest['time']).strftime("%Y-%m-%d") if 'time' in latest else datetime.now().strftime("%Y-%m-%d")
            
            open_val = float(latest.get('open', 0.0))
            high_val = float(latest.get('high', 0.0))
            low_val = float(latest.get('low', 0.0))
            close_val = float(latest.get('close', 0.0))
            volume_val = float(latest.get('volume', 0.0))
            
            return {
                "symbol": symbol,
                "open": open_val,
                "high": high_val,
                "low": low_val,
                "close": close_val,
                "adjclose": close_val,  # For commodities, adjclose is typically the same as close
                "volume": volume_val,
                "date": date_str,
                "currency": "USD"
            }
        except Exception as e:
            logger.error(f"Error fetching MSN quote: {e}")
            return None

    
    def search_gold(self, symbol: str) -> Optional[Dict]:
        """Return gold asset information for search results."""
        try:
            _, provider = self.parse_symbol(symbol)
            config = self.PROVIDERS[provider]
            # MSN gold is priced in USD, others in VND
            currency = "USD" if provider == "msn" else "VND"
            
            return {
                "symbol": symbol,
                "name": f"Gold - {config['name']}",
                "provider": provider,
                "provider_name": config["name"],
                "asset_type": "Commodity",
                "exchange": provider.upper(),
                "currency": currency
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
            # MSN gold is priced in USD, others in VND
            currency = "USD" if provider_key == "msn" else "VND"
            providers.append({
                "symbol": primary_symbol,
                "name": f"Gold - {config['name']}",
                "provider": provider_key,
                "provider_name": config["name"],
                "asset_type": "Commodity",
                "exchange": provider_key.upper(),
                "currency": currency
            })
        return providers
