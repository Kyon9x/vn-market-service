"""
Data freshness utilities for checking and updating latest data.
Reusable across all asset type clients.
"""

from datetime import datetime
from typing import List, Dict, Any
from .market_time_utils import is_weekday, is_friday, get_latest_friday, should_update_data
import logging

logger = logging.getLogger(__name__)

def check_and_update_latest_data(
    symbol: str,
    asset_type: str,
    cached_data: List[Dict],
    client_instance: Any,
    update_threshold_minutes: int = 30
) -> bool:
    """
    Check if latest data needs update and fetch if necessary.
    
    Returns True if update was performed, False otherwise.
    """
    if not cached_data:
        return False
    
    now = datetime.now()
    latest_record = cached_data[-1]  # Most recent
    
    if is_weekday(now):
        # Weekday: Update if older than threshold
        if should_update_data(latest_record['date'], update_threshold_minutes, now):
            return _fetch_and_store_latest_price(
                symbol, asset_type, client_instance, now
            )
    else:
        # Weekend: Ensure Friday data
        if not _is_friday_data(latest_record['date']):
            return _fetch_and_store_friday_price(
                symbol, asset_type, client_instance, now
            )
    
    return False

def _is_friday_data(date_str: str) -> bool:
    """Check if given date string is a Friday."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return is_friday(dt)
    except ValueError:
        return False

def _fetch_and_store_latest_price(symbol: str, asset_type: str, client: Any, dt: datetime) -> bool:
    """Fetch and store latest price for given asset type."""
    try:
        # Call appropriate client method based on asset type
        if asset_type == 'STOCK':
            # Get today's data or most recent trading day
            today_str = dt.strftime("%Y-%m-%d")
            fresh_data = client._fetch_stock_history_raw(symbol, today_str, today_str)
        elif asset_type == 'FUND':
            # Use fund client's latest NAV method
            fresh_data = [client.get_latest_nav(symbol)]
        # Add other asset types as needed
        
        if fresh_data and hasattr(client, 'historical_cache') and client.historical_cache:
            client.historical_cache.store_historical_records(symbol, asset_type, fresh_data)
            logger.info(f"Updated latest {asset_type} data for {symbol}")
            return True
    except Exception as e:
        logger.error(f"Error updating latest {asset_type} data for {symbol}: {e}")
    
    return False

def _fetch_and_store_friday_price(symbol: str, asset_type: str, client: Any, dt: datetime) -> bool:
    """Fetch and store Friday price for weekend updates."""
    try:
        friday = get_latest_friday(dt)
        friday_str = friday.strftime("%Y-%m-%d")
        
        # Fetch Friday data
        if asset_type == 'STOCK':
            fresh_data = client._fetch_stock_history_raw(symbol, friday_str, friday_str)
        elif asset_type == 'FUND':
            fresh_data = [client.get_latest_nav(symbol)]
        
        if fresh_data and hasattr(client, 'historical_cache') and client.historical_cache:
            client.historical_cache.store_historical_records(symbol, asset_type, fresh_data)
            logger.info(f"Updated Friday {asset_type} data for {symbol}")
            return True
    except Exception as e:
        logger.error(f"Error updating Friday {asset_type} data for {symbol}: {e}")
    
    return False