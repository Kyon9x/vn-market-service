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
            "symbols": ["VN.GOLD", "VN.GOLD.SJC", "SJC.GOLD"],
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
    
    def __init__(self):
        # Fallback prices for each provider in VND per tael (1 tael ≈ 37.5 grams)
        self.fallback_prices = {
            "sjc": {
                "buy_price": 84_000_000.0,
                "sell_price": 86_500_000.0
            },
            "btmc": {
                "buy_price": 82_000_000.0,
                "sell_price": 85_000_000.0
            },
            "msn": {
                "close": 2_100_000.0  # USD price in VND equivalent, approximate
            }
        }
    
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
        try:
            _, provider = self.parse_symbol(symbol)
            
            if provider == "sjc":
                return self._get_sjc_history(start_date, end_date)
            elif provider == "btmc":
                return self._get_btmc_history(start_date, end_date)
            elif provider == "msn":
                return self._get_msn_history(start_date, end_date)
        except ValueError as e:
            logger.error(f"Invalid symbol: {e}")
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
                                "adjclose": price,
                                "volume": 0.0,
                                "buy_price": buy_price,
                                "sell_price": sell_price
                            })
                            current_dt += timedelta(days=1)
                            continue
                except Exception as date_error:
                    logger.warning(f"API error for {date_str}: {date_error}, using fallback")
                
                # Fallback
                fallback = self.fallback_prices["sjc"]
                price = fallback["sell_price"]
                history.append({
                    "date": date_str,
                    "nav": price,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "adjclose": price,
                    "volume": 0.0,
                    "buy_price": fallback["buy_price"],
                    "sell_price": fallback["sell_price"]
                })
                
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
                                "adjclose": price,
                                "volume": 0.0,
                                "buy_price": buy_price,
                                "sell_price": sell_price
                            })
                            current_dt += timedelta(days=1)
                            continue
                except Exception as date_error:
                    logger.warning(f"BTMC API error for {date_str}: {date_error}")
                
                # Fallback
                fallback = self.fallback_prices["btmc"]
                price = fallback["sell_price"]
                history.append({
                    "date": date_str,
                    "nav": price,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "adjclose": price,
                    "volume": 0.0,
                    "buy_price": fallback["buy_price"],
                    "sell_price": fallback["sell_price"]
                })
                
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
                return self._get_msn_fallback_history(start_date, end_date)
            
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
            logger.warning(f"Error fetching MSN history: {e}, using fallback")
            return self._get_msn_fallback_history(start_date, end_date)
    
    def _get_msn_fallback_history(self, start_date: str, end_date: str) -> List[Dict]:
        """Generate fallback MSN historical data."""
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            history = []
            current_dt = start_dt
            fallback_price = self.fallback_prices["msn"]["close"]
            
            while current_dt <= end_dt:
                date_str = current_dt.strftime("%Y-%m-%d")
                history.append({
                    "date": date_str,
                    "nav": fallback_price,
                    "open": fallback_price,
                    "high": fallback_price,
                    "low": fallback_price,
                    "close": fallback_price,
                    "adjclose": fallback_price,
                    "volume": 0.0
                })
                current_dt += timedelta(days=1)
            
            return history
        except Exception as e:
            logger.error(f"Error in _get_msn_fallback_history: {e}")
            return []
    
    def get_latest_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch the latest gold price for a given provider."""
        try:
            _, provider = self.parse_symbol(symbol)
            
            if provider == "sjc":
                return self._get_sjc_quote(symbol)
            elif provider == "btmc":
                return self._get_btmc_quote(symbol)
            elif provider == "msn":
                return self._get_msn_quote(symbol)
        except ValueError as e:
            logger.error(f"Invalid symbol: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching gold quote for {symbol}: {e}")
            return None
    
    def _get_sjc_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest SJC gold price."""
        try:
            df = sjc_gold_price()
            
            if df is None or df.empty:
                logger.warning("SJC API returned empty data, using fallback")
                return self._get_sjc_fallback_quote(symbol)
            
            info = df.iloc[0]
            date_val = info.get("date")
            date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d") if date_val else datetime.now().strftime("%Y-%m-%d")
            
            buy_price = float(info.get("buy_price", 0.0)) if not pd.isna(info.get("buy_price")) else 0.0
            sell_price = float(info.get("sell_price", 0.0)) if not pd.isna(info.get("sell_price")) else 0.0
            close_price = sell_price if sell_price > 0 else buy_price
            
            return {
                "symbol": symbol,
                "close": close_price,
                "date": date_str,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "currency": "VND"
            }
        except Exception as e:
            logger.warning(f"Error fetching SJC quote: {e}, using fallback")
            return self._get_sjc_fallback_quote(symbol)
    
    def _get_sjc_fallback_quote(self, symbol: str) -> Dict:
        """Return fallback SJC gold prices."""
        today = datetime.now().strftime("%Y-%m-%d")
        fallback = self.fallback_prices["sjc"]
        
        return {
            "symbol": symbol,
            "close": fallback["sell_price"],
            "date": today,
            "buy_price": fallback["buy_price"],
            "sell_price": fallback["sell_price"],
            "currency": "VND"
        }
    
    def _get_btmc_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest BTMC gold price."""
        try:
            df = btmc_goldprice()
            
            if df is None or df.empty:
                logger.warning("BTMC API returned empty data, using fallback")
                return self._get_btmc_fallback_quote(symbol)
            
            info = df.iloc[0]
            time_val = info.get("time")
            date_str = pd.to_datetime(time_val).strftime("%Y-%m-%d") if time_val else datetime.now().strftime("%Y-%m-%d")
            
            buy_price = float(info.get("buy_price", 0.0)) if not pd.isna(info.get("buy_price")) else 0.0
            sell_price = float(info.get("sell_price", 0.0)) if not pd.isna(info.get("sell_price")) else 0.0
            close_price = sell_price if sell_price > 0 else buy_price
            
            return {
                "symbol": symbol,
                "close": close_price,
                "date": date_str,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "currency": "VND"
            }
        except Exception as e:
            logger.warning(f"Error fetching BTMC quote: {e}, using fallback")
            return self._get_btmc_fallback_quote(symbol)
    
    def _get_btmc_fallback_quote(self, symbol: str) -> Dict:
        """Return fallback BTMC gold prices."""
        today = datetime.now().strftime("%Y-%m-%d")
        fallback = self.fallback_prices["btmc"]
        
        return {
            "symbol": symbol,
            "close": fallback["sell_price"],
            "date": today,
            "buy_price": fallback["buy_price"],
            "sell_price": fallback["sell_price"],
            "currency": "VND"
        }
    
    def _get_msn_quote(self, symbol: str) -> Optional[Dict]:
        """Fetch latest MSN/world gold commodity price."""
        try:
            vnstock = Vnstock()
            gold_idx = vnstock.world_index(symbol='GOLD', source='MSN')
            
            df = gold_idx.quote.history(start=(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d'), 
                                       end=datetime.now().strftime('%Y-%m-%d'), 
                                       interval='1D')
            
            if df is None or df.empty:
                logger.warning("MSN API returned empty data, using fallback")
                return self._get_msn_fallback_quote(symbol)
            
            latest = df.iloc[-1]
            date_str = pd.to_datetime(latest['time']).strftime("%Y-%m-%d") if 'time' in latest else datetime.now().strftime("%Y-%m-%d")
            
            return {
                "symbol": symbol,
                "close": float(latest.get('close', 0.0)),
                "date": date_str,
                "currency": "USD"
            }
        except Exception as e:
            logger.warning(f"Error fetching MSN quote: {e}, using fallback")
            return self._get_msn_fallback_quote(symbol)
    
    def _get_msn_fallback_quote(self, symbol: str) -> Dict:
        """Return fallback MSN gold prices."""
        today = datetime.now().strftime("%Y-%m-%d")
        fallback = self.fallback_prices["msn"]
        
        return {
            "symbol": symbol,
            "close": fallback["close"],
            "date": today,
            "currency": "USD"
        }
    
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
            logger.error(f"Invalid symbol: {e}")
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
