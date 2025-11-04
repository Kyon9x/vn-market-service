"""
Date utility functions to eliminate repeated date validation and default date logic.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
from fastapi import HTTPException


def validate_and_set_dates(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_days_back: int = 365,
    allow_future_dates: bool = False
) -> Tuple[str, str]:
    """
    Validate date format and set default dates if not provided.

    Args:
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        default_days_back: Number of days back from today for default start_date
        allow_future_dates: Whether to allow dates in the future

    Returns:
        Tuple of (start_date, end_date) as validated strings

    Raises:
        HTTPException: If date format is invalid or date is in future when not allowed
    """
    # Set default end_date to today
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    # Set default start_date to default_days_back ago
    if not start_date:
        start_date = (datetime.now() - timedelta(days=default_days_back)).strftime("%Y-%m-%d")

    # Validate date formats
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid date format. Use YYYY-MM-DD"
        )

    # Check for future dates if not allowed
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if not allow_future_dates:
        # Allow today and past dates, but not future dates
        tomorrow = today + timedelta(days=1)
        if start_dt >= tomorrow:
            raise HTTPException(
                status_code=400,
                detail=f"Start date {start_date} is in the future. Historical data is not available for future dates."
            )
        if end_dt >= tomorrow:
            raise HTTPException(
                status_code=400,
                detail=f"End date {end_date} is in the future. Historical data is not available for future dates."
            )

    return start_date, end_date


def get_default_history_dates() -> Tuple[str, str]:
    """
    Get default date range for historical data (1 year back to today).

    Returns:
        Tuple of (start_date, end_date)
    """
    return validate_and_set_dates(default_days_back=365)


def get_default_quote_dates() -> Tuple[str, str]:
    """
    Get default date range for quote data (today only).

    Returns:
        Tuple of (start_date, end_date)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return today, today
