import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
import threading
from app.cache.cache_manager import CacheManager
from app.cache.memory_cache import cleanup_expired_caches

logger = logging.getLogger(__name__)

class BackgroundCacheManager:
    """Manages background cache refresh and cleanup tasks."""
    
    def __init__(self, cache_manager: CacheManager, stock_client, fund_client, gold_client):
        self.cache_manager = cache_manager
        self.stock_client = stock_client
        self.fund_client = fund_client
        self.gold_client = gold_client
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cleanup_thread: Optional[threading.Thread] = None
    
    async def start_background_tasks(self):
        """Start background cache management tasks."""
        if self._running:
            logger.warning("Background cache tasks already running")
            return
        
        self._running = True
        logger.info("Starting background cache management tasks")
        
        # Start cache refresh task
        self._task = asyncio.create_task(self._periodic_cache_refresh())
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()
    
    async def stop_background_tasks(self):
        """Stop background cache management tasks."""
        if not self._running:
            return
        
        self._running = False
        logger.info("Stopping background cache management tasks")
        
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        # Cleanup thread will stop automatically when _running is False
    
    async def _periodic_cache_refresh(self):
        """Periodically refresh cache data."""
        while self._running:
            try:
                await self._refresh_asset_data()
                await asyncio.sleep(3600)  # Refresh every hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic cache refresh: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _refresh_asset_data(self):
        """Refresh asset data in cache."""
        try:
            logger.info("Starting asset data refresh")
            
            # Refresh stock data
            await self._refresh_stock_data()
            
            # Refresh fund data
            await self._refresh_fund_data()
            
            # Refresh gold provider data
            await self._refresh_gold_data()
            
            logger.info("Asset data refresh completed")
        except Exception as e:
            logger.error(f"Error refreshing asset data: {e}")
    
    async def _refresh_stock_data(self):
        """Refresh stock symbols and basic data."""
        try:
            # This will trigger a refresh of the companies cache
            companies_df = self.stock_client._get_companies_df()
            if companies_df is not None and not companies_df.empty:
                logger.info(f"Refreshed {len(companies_df)} stock symbols")
                
                # Cache some popular stocks
                popular_symbols = ["VNM", "FPT", "MWG", "VCB", "HDB", "ACB", "CTG", "BID", "TCB", "VPB"]
                for symbol in popular_symbols:
                    try:
                        stock_info = self.stock_client.search_stock(symbol)
                        if stock_info:
                            self.cache_manager.set_asset(
                                symbol=stock_info["symbol"],
                                name=stock_info["company_name"],
                                asset_type="STOCK",
                                asset_class="Equity",
                                asset_sub_class="Stock",
                                exchange=stock_info.get("exchange", "HOSE"),
                                currency="VND",
                                metadata={
                                    "industry": stock_info.get("industry", ""),
                                    "company_type": stock_info.get("company_type", "")
                                }
                            )
                    except Exception as e:
                        logger.debug(f"Error caching stock {symbol}: {e}")
        except Exception as e:
            logger.error(f"Error refreshing stock data: {e}")
    
    async def _refresh_fund_data(self):
        """Refresh fund data."""
        try:
            funds = self.fund_client.get_funds_list()
            if funds:
                logger.info(f"Refreshed {len(funds)} funds")
                
                # Cache all funds
                for fund in funds:
                    try:
                        self.cache_manager.set_asset(
                            symbol=fund["symbol"],
                            name=fund["fund_name"],
                            asset_type="FUND",
                            asset_class="Investment Fund",
                            asset_sub_class="Mutual Fund",
                            exchange="VN",
                            currency="VND"
                        )
                    except Exception as e:
                        logger.debug(f"Error caching fund {fund['symbol']}: {e}")
        except Exception as e:
            logger.error(f"Error refreshing fund data: {e}")
    
    async def _refresh_gold_data(self):
        """Refresh gold provider data."""
        try:
            gold_providers = self.gold_client.get_all_gold_providers()
            if gold_providers:
                logger.info(f"Refreshed {len(gold_providers)} gold providers")
                
                for provider in gold_providers:
                    try:
                        self.cache_manager.set_asset(
                            symbol=provider["symbol"],
                            name=provider["name"],
                            asset_type="GOLD",
                            asset_class="Commodity",
                            asset_sub_class="Precious Metal",
                            exchange=provider["exchange"],
                            currency=provider["currency"]
                        )
                    except Exception as e:
                        logger.debug(f"Error caching gold provider {provider['symbol']}: {e}")
        except Exception as e:
            logger.error(f"Error refreshing gold data: {e}")
    
    def _periodic_cleanup(self):
        """Run periodic cleanup of expired cache entries."""
        while self._running:
            try:
                cleanup_expired_caches()
                self.cache_manager.cleanup_expired()
                
                # Sleep for 30 minutes
                for _ in range(1800):  # 30 minutes in seconds
                    if not self._running:
                        break
                    threading.Event().wait(1)
                    
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                # Wait 5 minutes on error
                for _ in range(300):
                    if not self._running:
                        break
                    threading.Event().wait(1)

# Global background cache manager instance
_background_manager: Optional[BackgroundCacheManager] = None

def get_background_manager(cache_manager: CacheManager, stock_client, fund_client, gold_client) -> BackgroundCacheManager:
    """Get or create global background cache manager."""
    global _background_manager
    if _background_manager is None:
        _background_manager = BackgroundCacheManager(cache_manager, stock_client, fund_client, gold_client)
    return _background_manager

async def start_cache_background_tasks(cache_manager: CacheManager, stock_client, fund_client, gold_client):
    """Start background cache tasks."""
    manager = get_background_manager(cache_manager, stock_client, fund_client, gold_client)
    await manager.start_background_tasks()

async def stop_cache_background_tasks():
    """Stop background cache tasks."""
    global _background_manager
    if _background_manager:
        await _background_manager.stop_background_tasks()