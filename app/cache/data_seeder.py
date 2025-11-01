import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Optional
from app.cache.cache_manager import CacheManager
from app.cache.memory_cache import quote_cache

logger = logging.getLogger(__name__)

class DataSeeder:
    """Handles initial seeding and periodic refresh of cache database."""
    
    def __init__(self, cache_manager: CacheManager, stock_client, fund_client, gold_client):
        self.cache_manager = cache_manager
        self.stock_client = stock_client
        self.fund_client = fund_client
        self.gold_client = gold_client
        self._seeding_progress = 0
        self._total_assets = 0
        
        # Exchange mapping for compatibility
        self.exchange_mapping = {
            'HSX': 'HOSE',  # Ho Chi Minh Stock Exchange
            'HNX': 'HNX',   # Hanoi Stock Exchange  
            'UPCOM': 'UPCOM' # Unlisted Public Company Market
        }
    
    async def seed_all_assets(self, force_refresh: bool = False) -> Dict[str, int]:
        """
        Seed the cache database with all available assets.
        
        Args:
            force_refresh: Whether to force refresh existing data
            
        Returns:
            Dictionary with counts of seeded assets by type
        """
        logger.info("Starting initial asset data seeding...")
        start_time = datetime.now()
        
        # Check if we already have data
        if not force_refresh:
            existing_stats = self.cache_manager.get_stats()
            if existing_stats.get('assets', 0) > 100:  # Assume seeded if we have substantial data
                logger.info(f"Cache already contains {existing_stats['assets']} assets, skipping seeding")
                return existing_stats
        
        try:
            # Reset progress tracking
            self._seeding_progress = 0
            self._total_assets = 0
            
            # Seed all asset types in parallel
            results = await asyncio.gather(
                self._seed_stocks(),
                self._seed_funds(),
                self._seed_indices(),
                self._seed_gold_providers(),
                return_exceptions=True
            )
            
            # Process results
            counts: Dict[str, int] = {
                'stocks': 0,
                'funds': 0,
                'indices': 0,
                'gold': 0,
                'total': 0
            }
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error seeding asset type {i}: {result}")
                    continue
                
                if isinstance(result, dict):
                    asset_type = ['stocks', 'funds', 'indices', 'gold'][i]
                    counts[asset_type] = result.get('count', 0)
                    counts['total'] += result.get('count', 0)
            
            # Log completion
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            logger.info(f"Seeding completed in {duration:.2f}s: {counts}")
            
            # Cleanup any expired entries
            self.cache_manager.cleanup_expired()
            
            return counts
            
        except Exception as e:
            logger.error(f"Error during asset seeding: {e}")
            raise
    
    async def _seed_stocks(self) -> Dict[str, int]:
        """Seed all available stocks from vnstock listing."""
        try:
            logger.info("Seeding stocks...")
            
            # Get all companies from vnstock
            companies_df = self.stock_client._get_companies_df()
            if companies_df is None or companies_df.empty:
                logger.warning("No stock data available from vnstock")
                return {'count': 0}
            
            stocks_seeded = 0
            batch_size = 100
            total_stocks = len(companies_df)
            
            # Process in batches to avoid memory issues
            for batch_start in range(0, total_stocks, batch_size):
                batch_end = min(batch_start + batch_size, total_stocks)
                batch = companies_df.iloc[batch_start:batch_end]
                
                for _, row in batch.iterrows():
                    try:
                        symbol = str(row.get("symbol", "")).strip()
                        company_name = str(row.get("organ_name", "")).strip()
                        industry = str(row.get("organ_type", "")).strip()
                        company_type = str(row.get("com_type", "")).strip()
                        exchange = str(row.get("exchange", "")).strip()
                        mapped_exchange = self.exchange_mapping.get(exchange, exchange)
                        
                        if symbol and company_name:
                            self.cache_manager.set_asset(
                                symbol=symbol,
                                name=company_name,
                                asset_type="STOCK",
                                asset_class="Equity",
                                asset_sub_class="Stock",
                                exchange=mapped_exchange,  # Use mapped exchange from data
                                currency="VND",
                                metadata={
                                    "industry": industry,
                                    "company_type": company_type,
                                    "listing_source": "vnstock"
                                }
                            )
                            stocks_seeded += 1
                    except Exception as e:
                        logger.debug(f"Error seeding stock {row.get('symbol', 'unknown')}: {e}")
                
                # Update progress
                self._seeding_progress = batch_end
                logger.debug(f"Seeded {batch_end}/{total_stocks} stocks")
            
            logger.info(f"Successfully seeded {stocks_seeded} stocks")
            return {'count': int(stocks_seeded)}
            
        except Exception as e:
            logger.error(f"Error seeding stocks: {e}")
            return {'count': 0}
    
    async def _seed_funds(self) -> Dict[str, int]:
        """Seed all available funds from fund API."""
        try:
            logger.info("Seeding funds...")
            
            # Get all funds
            funds = self.fund_client.get_funds_list()
            if not funds:
                logger.warning("No fund data available")
                return {'count': 0}
            
            funds_seeded = 0
            for fund in funds:
                try:
                    symbol = fund.get("symbol", "").strip()
                    fund_name = fund.get("fund_name", "").strip()
                    
                    if symbol and fund_name:
                        self.cache_manager.set_asset(
                            symbol=symbol,
                            name=fund_name,
                            asset_type="FUND",
                            asset_class="Investment Fund",
                            asset_sub_class="Mutual Fund",
                            exchange="VN",
                            currency="VND",
                            metadata={
                                "listing_source": "vnstock_funds"
                            }
                        )
                        funds_seeded += 1
                except Exception as e:
                    logger.debug(f"Error seeding fund {fund.get('symbol', 'unknown')}: {e}")
            
            logger.info(f"Successfully seeded {funds_seeded} funds")
            return {'count': int(funds_seeded)}
            
        except Exception as e:
            logger.error(f"Error seeding funds: {e}")
            return {'count': 0}
    
    async def _seed_indices(self) -> Dict[str, int]:
        """Seed all available indices."""
        try:
            logger.info("Seeding indices...")
            
            # Define major Vietnamese indices
            indices = [
                {
                    "symbol": "VNINDEX",
                    "name": "VNINDEX - Vietnam All Share Index",
                    "exchange": "HOSE"
                },
                {
                    "symbol": "VN30", 
                    "name": "VN30 - Vietnam 30 Index",
                    "exchange": "HOSE"
                },
                {
                    "symbol": "HNX",
                    "name": "HNX - Hanoi Stock Exchange Index", 
                    "exchange": "HNX"
                },
                {
                    "symbol": "HNX30",
                    "name": "HNX30 - Hanoi 30 Index",
                    "exchange": "HNX"
                },
                {
                    "symbol": "UPCOM",
                    "name": "UPCOM - Unlisted Public Company Market Index",
                    "exchange": "HNX"
                }
            ]
            
            indices_seeded = 0
            for index in indices:
                try:
                    self.cache_manager.set_asset(
                        symbol=index["symbol"],
                        name=index["name"],
                        asset_type="INDEX",
                        asset_class="Index",
                        asset_sub_class="Market Index",
                        exchange=index["exchange"],
                        currency="VND",
                        metadata={
                            "listing_source": "predefined"
                        }
                    )
                    indices_seeded += 1
                except Exception as e:
                    logger.debug(f"Error seeding index {index['symbol']}: {e}")
            
            logger.info(f"Successfully seeded {indices_seeded} indices")
            return {'count': int(indices_seeded)}
            
        except Exception as e:
            logger.error(f"Error seeding indices: {e}")
            return {'count': 0}
    
    async def _seed_gold_providers(self) -> Dict[str, int]:
        """Seed all gold providers."""
        try:
            logger.info("Seeding gold providers...")
            
            # Get all gold providers
            gold_providers = self.gold_client.get_all_gold_providers()
            if not gold_providers:
                logger.warning("No gold provider data available")
                return {'count': 0}
            
            gold_seeded = 0
            for provider in gold_providers:
                try:
                    self.cache_manager.set_asset(
                        symbol=provider["symbol"],
                        name=provider["name"],
                        asset_type="GOLD",
                        asset_class="Commodity",
                        asset_sub_class="Precious Metal",
                        exchange=provider["exchange"],
                        currency=provider["currency"],
                        metadata={
                            "provider": provider.get("provider", ""),
                            "provider_name": provider.get("provider_name", ""),
                            "listing_source": "vnstock_gold"
                        }
                    )
                    gold_seeded += 1
                except Exception as e:
                    logger.debug(f"Error seeding gold provider {provider.get('symbol', 'unknown')}: {e}")
            
            logger.info(f"Successfully seeded {gold_seeded} gold providers")
            return {'count': int(gold_seeded)}
            
        except Exception as e:
            logger.error(f"Error seeding gold providers: {e}")
            return {'count': 0}
    
    def get_seeding_progress(self) -> Dict[str, int]:
        """Get current seeding progress."""
        return {
            "progress": self._seeding_progress,
            "total": self._total_assets,
            "percentage": (self._seeding_progress / self._total_assets * 100) if self._total_assets > 0 else 0
        }
    
    async def refresh_popular_assets(self):
        """Refresh quotes for popular assets to warm up cache."""
        try:
            logger.info("Refreshing popular asset quotes...")
            
            # Define popular assets
            popular_stocks = ["VNM", "FPT", "MWG", "VCB", "HDB", "ACB", "CTG", "BID", "TCB", "VPB"]
            popular_funds = ["VESAF", "VOF", "EVF", "SSBF", "VCBF"]
            popular_indices = ["VNINDEX", "VN30"]
            popular_gold = ["VN.GOLD", "SJC.GOLD", "BTMC.GOLD"]
            
            # Refresh quotes in parallel
            refresh_tasks = []
            
            # Stock quotes
            for symbol in popular_stocks:
                refresh_tasks.append(self._refresh_stock_quote(symbol))
            
            # Fund NAVs
            for symbol in popular_funds:
                refresh_tasks.append(self._refresh_fund_nav(symbol))
            
            # Index quotes
            for symbol in popular_indices:
                refresh_tasks.append(self._refresh_index_quote(symbol))
            
            # Gold quotes
            for symbol in popular_gold:
                refresh_tasks.append(self._refresh_gold_quote(symbol))
            
            # Execute all refresh tasks
            results = await asyncio.gather(*refresh_tasks, return_exceptions=True)
            
            # Count successful refreshes
            successful = sum(1 for r in results if not isinstance(r, Exception))
            logger.info(f"Refreshed {successful}/{len(refresh_tasks)} popular asset quotes")
            
        except Exception as e:
            logger.error(f"Error refreshing popular assets: {e}")
    
    async def _refresh_stock_quote(self, symbol: str):
        """Refresh quote for a specific stock."""
        try:
            await asyncio.sleep(0.1)  # Small delay to avoid overwhelming API
            quote = self.stock_client.get_latest_quote(symbol)
            return quote is not None
        except Exception as e:
            logger.debug(f"Error refreshing stock quote {symbol}: {e}")
            return False
    
    async def _refresh_fund_nav(self, symbol: str):
        """Refresh NAV for a specific fund."""
        try:
            await asyncio.sleep(0.1)  # Small delay to avoid overwhelming API
            nav = self.fund_client.get_latest_nav(symbol)
            return nav is not None
        except Exception as e:
            logger.debug(f"Error refreshing fund NAV {symbol}: {e}")
            return False
    
    async def _refresh_index_quote(self, symbol: str):
        """Refresh quote for a specific index."""
        try:
            await asyncio.sleep(0.1)  # Small delay to avoid overwhelming API
            quote = self.stock_client.get_latest_quote(symbol)  # Index uses same client
            return quote is not None
        except Exception as e:
            logger.debug(f"Error refreshing index quote {symbol}: {e}")
            return False
    
    async def _refresh_gold_quote(self, symbol: str):
        """Refresh quote for a specific gold provider."""
        try:
            await asyncio.sleep(0.1)  # Small delay to avoid overwhelming API
            quote = self.gold_client.get_latest_quote(symbol)
            return quote is not None
        except Exception as e:
            logger.debug(f"Error refreshing gold quote {symbol}: {e}")
            return False

# Global seeder instance
_seeder: Optional[DataSeeder] = None

def get_data_seeder(cache_manager: CacheManager, stock_client, fund_client, gold_client) -> DataSeeder:
    """Get or create global data seeder."""
    global _seeder
    if _seeder is None:
        _seeder = DataSeeder(cache_manager, stock_client, fund_client, gold_client)
    return _seeder