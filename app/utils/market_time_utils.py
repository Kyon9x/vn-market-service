"""
Market time utilities for trading day and timestamp operations.
Reusable across stock, fund, index, and gold clients.
"""

from datetime import datetime, timedelta
from typing import Optional

def is_weekday(dt: Optional[datetime] = None) -> bool:
    """Check if given datetime is a weekday (Mon-Fri)."""
    if dt is None:
        dt = datetime.now()
    return dt.weekday() < 5  # Monday=0, Friday=4

def is_friday(dt: Optional[datetime] = None) -> bool:
    """Check if given datetime is a Friday."""
    if dt is None:
        dt = datetime.now()
    return dt.weekday() == 4  # Friday=4

def get_latest_friday(dt: Optional[datetime] = None) -> datetime:
    """Get most recent Friday on or before given datetime."""
    if dt is None:
        dt = datetime.now()
    days_since_friday = (dt.weekday() - 4) % 7  # Friday=4
    return dt - timedelta(days=days_since_friday)

def is_after_market_close(dt: Optional[datetime] = None) -> bool:
    """Check if current time is after market close (16:00) on a weekday."""
    if dt is None:
        dt = datetime.now()
    
    # Only check time on weekdays
    if not is_weekday(dt):
        return False
    
    return dt.hour >= 16  # After 4 PM

def should_update_data(
    timestamp: str, 
    threshold_minutes: int = 30,
    current_dt: Optional[datetime] = None
) -> bool:
    """Check if data older than threshold minutes needs update."""
    if current_dt is None:
        current_dt = datetime.now()
    
    try:
        last_update = datetime.strptime(timestamp, "%Y-%m-%d")
        # For date-only timestamps, assume end of day
        if len(timestamp) == 10:  # YYYY-MM-DD format
            last_update = last_update.replace(hour=23, minute=59, second=59)
        
        return (current_dt - last_update).total_seconds() > (threshold_minutes * 60)
    except ValueError:
        return True  # If timestamp parsing fails, assume update needed