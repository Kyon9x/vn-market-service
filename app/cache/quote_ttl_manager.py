"""
Quote TTL Manager - Asset-specific TTL configuration for quote caching.

This module provides intelligent TTL management based on asset types:
- FUND: 24 hours (NAV updates daily)
- STOCK: 1 hour (frequent updates during market hours)
- INDEX: 1 hour (market indices update frequently)
- GOLD: 1 hour (commodity prices change throughout day)
- CRYPTO: 15 minutes (high volatility, future support)
"""

import logging
from typing import Dict, Optional, Any, Union
from datetime import datetime, time

logger = logging.getLogger(__name__)

class QuoteTTLManager:
    """
    Manages Time-To-Live (TTL) settings for different asset types.
    
    Provides asset-specific caching strategies to minimize API calls
    while maintaining appropriate data freshness.
    """
    
    # Default TTL configuration (in seconds)
    DEFAULT_TTL_CONFIG: Dict[str, int] = {
        'FUND': 86400,      # 24 hours - NAV updates once daily after market close
        'STOCK': 3600,      # 1 hour - Real-time during market, hourly sufficient
        'INDEX': 3600,      # 1 hour - Market index updates frequently
        'GOLD': 3600,       # 1 hour - Commodity price updates
        'CRYPTO': 900,      # 15 minutes - High volatility (future)
        'DEFAULT': 3600     # 1 hour - Default fallback
    }
    
    # Market hours for dynamic TTL (optional advanced feature)
    MARKET_HOURS = {
        'HOSE': {'open': time(9, 0), 'close': time(15, 0)},
        'HNX': {'open': time(9, 0), 'close': time(15, 0)},
        'UPCOM': {'open': time(9, 0), 'close': time(15, 0)}
    }
    
    def __init__(self, custom_config: Optional[Dict[str, int]] = None):
        """
        Initialize TTL manager with optional custom configuration.
        
        Args:
            custom_config: Optional dictionary to override default TTL values
        """
        self.ttl_config = self.DEFAULT_TTL_CONFIG.copy()
        if custom_config:
            self.ttl_config.update(custom_config)
            logger.info(f"TTL config updated with custom values: {custom_config}")
    
    def get_ttl_for_asset(self, asset_type: str) -> int:
        """
        Get the appropriate TTL (in seconds) for a specific asset type.
        
        Args:
            asset_type: Type of asset (FUND, STOCK, INDEX, GOLD, CRYPTO)
            
        Returns:
            TTL in seconds
        """
        asset_type_upper = asset_type.upper() if asset_type else 'DEFAULT'
        ttl = self.ttl_config.get(asset_type_upper, self.ttl_config['DEFAULT'])
        
        logger.debug(f"TTL for {asset_type_upper}: {ttl} seconds")
        return ttl
    
    def get_ttl_for_quote(self, symbol: str, asset_type: str, 
                         exchange: Optional[str] = None) -> int:
        """
        Get TTL for a specific quote, with optional market-hours awareness.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset
            exchange: Exchange name (HOSE, HNX, UPCOM) - optional
            
        Returns:
            TTL in seconds
        """
        base_ttl = self.get_ttl_for_asset(asset_type)
        
        # Future enhancement: Adjust TTL based on market hours
        # During market hours, stocks might need shorter TTL
        # After market close, longer TTL is acceptable
        
        # For now, return base TTL
        return base_ttl
    
    def should_refresh_quote(self, symbol: str, asset_type: str, 
                            last_update: Optional[datetime] = None) -> bool:
        """
        Determine if a quote should be refreshed based on TTL.
        
        Args:
            symbol: Asset symbol
            asset_type: Type of asset
            last_update: Timestamp of last update (None means not cached)
            
        Returns:
            True if quote should be refreshed, False otherwise
        """
        if last_update is None:
            return True  # Not cached, should fetch
        
        ttl = self.get_ttl_for_asset(asset_type)
        age_seconds = (datetime.now() - last_update).total_seconds()
        
        should_refresh = age_seconds >= ttl
        
        if should_refresh:
            logger.debug(f"Quote for {symbol} ({asset_type}) is stale "
                        f"(age: {age_seconds:.0f}s, TTL: {ttl}s)")
        
        return should_refresh
    
    def get_cache_efficiency_score(self, asset_type: str, 
                                   old_ttl: int = 300) -> Dict[str, Any]:
        """
        Calculate the expected cache efficiency improvement.
        
        Args:
            asset_type: Type of asset
            old_ttl: Previous TTL value (default 300 seconds = 5 minutes)
            
        Returns:
            Dictionary with efficiency metrics
        """
        new_ttl = self.get_ttl_for_asset(asset_type)
        
        # Calculate reduction in API calls
        reduction_ratio = new_ttl / old_ttl if old_ttl > 0 else 1
        reduction_percentage = ((new_ttl - old_ttl) / old_ttl * 100) if old_ttl > 0 else 0
        
        # Calls per day with old TTL vs new TTL
        calls_per_day_old = (24 * 3600) / old_ttl if old_ttl > 0 else 0
        calls_per_day_new = (24 * 3600) / new_ttl if new_ttl > 0 else 0
        
        return {
            'asset_type': asset_type,
            'old_ttl_seconds': old_ttl,
            'new_ttl_seconds': new_ttl,
            'reduction_ratio': round(reduction_ratio, 2),
            'reduction_percentage': round(reduction_percentage, 2),
            'calls_per_day_old': round(calls_per_day_old, 0),
            'calls_per_day_new': round(calls_per_day_new, 0),
            'calls_saved_per_day': round(calls_per_day_old - calls_per_day_new, 0)
        }
    
    def get_all_efficiency_scores(self, old_ttl: int = 300) -> Dict[str, Dict]:
        """
        Get efficiency scores for all asset types.
        
        Args:
            old_ttl: Previous TTL value (default 300 seconds)
            
        Returns:
            Dictionary mapping asset types to efficiency metrics
        """
        scores = {}
        for asset_type in ['FUND', 'STOCK', 'INDEX', 'GOLD', 'CRYPTO']:
            scores[asset_type] = self.get_cache_efficiency_score(asset_type, old_ttl)
        
        return scores
    
    def update_ttl_config(self, asset_type: str, ttl_seconds: int):
        """
        Update TTL configuration for a specific asset type.
        
        Args:
            asset_type: Type of asset
            ttl_seconds: New TTL value in seconds
        """
        asset_type_upper = asset_type.upper()
        old_ttl = self.ttl_config.get(asset_type_upper, 0)
        self.ttl_config[asset_type_upper] = ttl_seconds
        
        logger.info(f"Updated TTL for {asset_type_upper}: {old_ttl}s -> {ttl_seconds}s")
    
    def get_config_summary(self) -> Dict[str, str]:
        """
        Get a human-readable summary of current TTL configuration.
        
        Returns:
            Dictionary with formatted TTL values
        """
        def format_ttl(seconds: int) -> str:
            """Format TTL in human-readable format."""
            if seconds < 60:
                return f"{seconds}s"
            elif seconds < 3600:
                minutes = seconds // 60
                return f"{minutes}m"
            elif seconds < 86400:
                hours = seconds // 3600
                return f"{hours}h"
            else:
                days = seconds // 86400
                return f"{days}d"
        
        return {
            asset_type: format_ttl(ttl)
            for asset_type, ttl in self.ttl_config.items()
        }

# Global instance
_ttl_manager: Optional[QuoteTTLManager] = None

def get_ttl_manager(custom_config: Optional[Dict[str, int]] = None) -> QuoteTTLManager:
    """
    Get or create the global TTL manager instance.
    
    Args:
        custom_config: Optional custom configuration (only used on first call)
        
    Returns:
        QuoteTTLManager instance
    """
    global _ttl_manager
    if _ttl_manager is None:
        _ttl_manager = QuoteTTLManager(custom_config)
    return _ttl_manager

def get_ttl_for_asset(asset_type: str) -> int:
    """
    Convenience function to get TTL for an asset type.
    
    Args:
        asset_type: Type of asset
        
    Returns:
        TTL in seconds
    """
    return get_ttl_manager().get_ttl_for_asset(asset_type)

if __name__ == "__main__":
    # Demo and testing
    logging.basicConfig(level=logging.INFO)
    
    manager = QuoteTTLManager()
    
    print("\n=== TTL Configuration ===")
    print(manager.get_config_summary())
    
    print("\n=== Efficiency Analysis (vs 5-minute TTL) ===")
    scores = manager.get_all_efficiency_scores(old_ttl=300)
    for asset_type, score in scores.items():
        print(f"\n{asset_type}:")
        print(f"  Old: {score['old_ttl_seconds']}s ({score['calls_per_day_old']} calls/day)")
        print(f"  New: {score['new_ttl_seconds']}s ({score['calls_per_day_new']} calls/day)")
        print(f"  Improvement: {score['reduction_percentage']:.1f}% "
              f"({score['calls_saved_per_day']} calls saved/day)")
