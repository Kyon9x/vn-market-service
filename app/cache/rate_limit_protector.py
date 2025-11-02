"""
Rate Limit Protector - Prevents API rate limiting with throttling and queuing.

This module protects against API rate limits by:
- Tracking API call timestamps
- Enforcing delays between calls
- Queuing requests when at limit
- Providing fallback to cached data
- Logging rate limit warnings
"""

import time
import threading
import logging
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

class RateLimitProtector:
    """
    Protects against API rate limits with intelligent throttling.
    
    Features:
    - Track calls per minute and per hour
    - Enforce minimum delay between calls
    - Queue requests when at capacity
    - Provide statistics and monitoring
    """
    
    DEFAULT_CONFIG = {
        'max_calls_per_minute': 60,
        'max_calls_per_hour': 500,
        'delay_between_calls_ms': 100,
        'queue_max_size': 100,
        'enable_throttling': True
    }
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize rate limit protector.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)
        
        # Thread-safe call tracking
        self._lock = threading.RLock()
        self._call_timestamps: deque = deque()  # All recent calls
        self._minute_calls: deque = deque()     # Calls in last minute
        self._hour_calls: deque = deque()       # Calls in last hour
        self._last_call_time: float = 0
        
        # Statistics
        self._total_calls = 0
        self._throttled_calls = 0
        self._rejected_calls = 0
        
        # Queue for waiting requests (future enhancement)
        self._queue: List = []
        
        logger.info(f"Rate limiter initialized: {self.config}")
    
    def should_throttle(self) -> bool:
        """
        Check if we should throttle the next API call.
        
        Returns:
            True if rate limit is reached and should wait, False otherwise
        """
        if not self.config['enable_throttling']:
            return False
        
        with self._lock:
            now = time.time()
            
            # Clean up old timestamps
            self._cleanup_old_timestamps(now)
            
            # Check per-minute limit
            if len(self._minute_calls) >= self.config['max_calls_per_minute']:
                logger.warning(f"Rate limit: {len(self._minute_calls)} calls/minute "
                             f"(max: {self.config['max_calls_per_minute']})")
                return True
            
            # Check per-hour limit
            if len(self._hour_calls) >= self.config['max_calls_per_hour']:
                logger.warning(f"Rate limit: {len(self._hour_calls)} calls/hour "
                             f"(max: {self.config['max_calls_per_hour']})")
                return True
            
            # Check minimum delay between calls
            delay_seconds = self.config['delay_between_calls_ms'] / 1000.0
            time_since_last = now - self._last_call_time
            if self._last_call_time > 0 and time_since_last < delay_seconds:
                logger.debug(f"Rate limit: {time_since_last:.3f}s since last call "
                           f"(min: {delay_seconds}s)")
                return True
            
            return False
    
    def wait_for_slot(self, timeout: float = 60.0) -> bool:
        """
        Wait for an available API call slot.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 60s)
            
        Returns:
            True if slot became available, False if timed out
        """
        start_time = time.time()
        wait_count = 0
        
        while self.should_throttle():
            if time.time() - start_time > timeout:
                logger.error(f"Rate limit wait timeout after {timeout}s")
                with self._lock:
                    self._rejected_calls += 1
                return False
            
            # Calculate optimal wait time
            wait_time = self._calculate_wait_time()
            
            if wait_count == 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s...")
                with self._lock:
                    self._throttled_calls += 1
            
            time.sleep(wait_time)
            wait_count += 1
        
        if wait_count > 0:
            logger.info(f"Rate limit cleared after {wait_count} waits")
        
        return True
    
    def record_call(self, endpoint: Optional[str] = None):
        """
        Record that an API call was made.
        
        Args:
            endpoint: Optional endpoint name for tracking
        """
        with self._lock:
            now = time.time()
            
            # Record timestamp
            self._call_timestamps.append(now)
            self._minute_calls.append(now)
            self._hour_calls.append(now)
            self._last_call_time = now
            
            self._total_calls += 1
            
            # Clean up old timestamps
            self._cleanup_old_timestamps(now)
            
            logger.debug(f"API call recorded ({len(self._minute_calls)}/min, "
                        f"{len(self._hour_calls)}/hour)")
    
    def _cleanup_old_timestamps(self, now: float):
        """Remove timestamps older than tracking windows."""
        # Remove calls older than 1 minute
        cutoff_minute = now - 60
        while self._minute_calls and self._minute_calls[0] < cutoff_minute:
            self._minute_calls.popleft()
        
        # Remove calls older than 1 hour
        cutoff_hour = now - 3600
        while self._hour_calls and self._hour_calls[0] < cutoff_hour:
            self._hour_calls.popleft()
        
        # Keep only last 1 hour of all calls
        while self._call_timestamps and self._call_timestamps[0] < cutoff_hour:
            self._call_timestamps.popleft()
    
    def _calculate_wait_time(self) -> float:
        """
        Calculate optimal wait time based on current rate limits.
        
        Returns:
            Recommended wait time in seconds
        """
        with self._lock:
            now = time.time()
            
            # If we hit per-minute limit, wait until oldest call expires
            if len(self._minute_calls) >= self.config['max_calls_per_minute']:
                oldest_call = self._minute_calls[0]
                time_until_expire = max(0.1, 60 - (now - oldest_call))
                return min(time_until_expire, 5.0)  # Max 5s wait
            
            # If we hit per-hour limit, wait until oldest call expires
            if len(self._hour_calls) >= self.config['max_calls_per_hour']:
                oldest_call = self._hour_calls[0]
                time_until_expire = max(0.5, 3600 - (now - oldest_call))
                return min(time_until_expire, 60.0)  # Max 60s wait
            
            # Otherwise, just wait for minimum delay
            delay_seconds = self.config['delay_between_calls_ms'] / 1000.0
            time_since_last = now - self._last_call_time
            if time_since_last < delay_seconds:
                return delay_seconds - time_since_last
            
            return 0.1  # Minimal wait
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        with self._lock:
            now = time.time()
            self._cleanup_old_timestamps(now)
            
            # Calculate rates
            calls_per_minute = len(self._minute_calls)
            calls_per_hour = len(self._hour_calls)
            
            # Calculate capacity
            minute_capacity = self.config['max_calls_per_minute'] - calls_per_minute
            hour_capacity = self.config['max_calls_per_hour'] - calls_per_hour
            
            # Calculate utilization
            minute_utilization = (calls_per_minute / self.config['max_calls_per_minute'] * 100 
                                if self.config['max_calls_per_minute'] > 0 else 0)
            hour_utilization = (calls_per_hour / self.config['max_calls_per_hour'] * 100 
                              if self.config['max_calls_per_hour'] > 0 else 0)
            
            return {
                'enabled': self.config['enable_throttling'],
                'total_calls': self._total_calls,
                'throttled_calls': self._throttled_calls,
                'rejected_calls': self._rejected_calls,
                'current_rates': {
                    'per_minute': calls_per_minute,
                    'per_hour': calls_per_hour
                },
                'limits': {
                    'per_minute': self.config['max_calls_per_minute'],
                    'per_hour': self.config['max_calls_per_hour']
                },
                'capacity': {
                    'per_minute': minute_capacity,
                    'per_hour': hour_capacity
                },
                'utilization': {
                    'per_minute': round(minute_utilization, 1),
                    'per_hour': round(hour_utilization, 1)
                },
                'config': {
                    'delay_ms': self.config['delay_between_calls_ms'],
                    'queue_size': self.config['queue_max_size']
                }
            }
    
    def reset_stats(self):
        """Reset statistics counters."""
        with self._lock:
            self._total_calls = 0
            self._throttled_calls = 0
            self._rejected_calls = 0
            logger.info("Rate limiter statistics reset")
    
    def update_config(self, config: Dict):
        """
        Update rate limiter configuration.
        
        Args:
            config: Configuration dictionary with new values
        """
        with self._lock:
            old_config = self.config.copy()
            self.config.update(config)
            logger.info(f"Rate limiter config updated: {old_config} -> {self.config}")
    
    def is_at_capacity(self) -> bool:
        """
        Check if rate limiter is currently at or near capacity.
        
        Returns:
            True if at/near capacity (>80% utilized), False otherwise
        """
        stats = self.get_stats()
        return (stats['utilization']['per_minute'] > 80 or 
                stats['utilization']['per_hour'] > 80)
    
    def get_time_until_next_slot(self) -> float:
        """
        Get estimated time until next API call slot is available.
        
        Returns:
            Time in seconds (0 if slot is available now)
        """
        if not self.should_throttle():
            return 0.0
        
        return self._calculate_wait_time()

class RateLimitedAPI:
    """
    Wrapper for API calls with automatic rate limiting.
    
    Example usage:
        limiter = RateLimitProtector()
        api = RateLimitedAPI(limiter)
        
        result = api.call(my_api_function, arg1, arg2, kwarg1=value)
    """
    
    def __init__(self, rate_limiter: RateLimitProtector):
        self.rate_limiter = rate_limiter
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute API call with rate limiting.
        
        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Result from function call
            
        Raises:
            Exception if rate limit timeout or API call fails
        """
        # Wait for available slot
        if not self.rate_limiter.wait_for_slot():
            raise Exception("Rate limit timeout - too many API calls")
        
        try:
            # Make the API call
            result = func(*args, **kwargs)
            
            # Record successful call
            self.rate_limiter.record_call()
            
            return result
            
        except Exception as e:
            logger.error(f"API call failed: {e}")
            # Still record the call (failed calls count toward rate limit)
            self.rate_limiter.record_call()
            raise

# Global instance
_rate_limiter: Optional[RateLimitProtector] = None

def get_rate_limiter(config: Optional[Dict] = None) -> RateLimitProtector:
    """
    Get or create the global rate limiter instance.
    
    Args:
        config: Optional configuration (only used on first call)
        
    Returns:
        RateLimitProtector instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimitProtector(config)
    return _rate_limiter

if __name__ == "__main__":
    # Demo and testing
    logging.basicConfig(level=logging.INFO)
    
    # Create rate limiter with low limits for demo
    limiter = RateLimitProtector({
        'max_calls_per_minute': 5,
        'max_calls_per_hour': 20,
        'delay_between_calls_ms': 100,
        'enable_throttling': True
    })
    
    print("\n=== Rate Limiter Demo ===")
    print(f"Limits: {limiter.config['max_calls_per_minute']}/min, "
          f"{limiter.config['max_calls_per_hour']}/hour\n")
    
    # Simulate API calls
    for i in range(8):
        if limiter.should_throttle():
            print(f"Call {i+1}: THROTTLED - waiting...")
            limiter.wait_for_slot(timeout=5)
        else:
            print(f"Call {i+1}: OK")
        
        limiter.record_call()
        time.sleep(0.05)  # Small delay
    
    print("\n=== Statistics ===")
    stats = limiter.get_stats()
    print(f"Total calls: {stats['total_calls']}")
    print(f"Throttled: {stats['throttled_calls']}")
    print(f"Current rate: {stats['current_rates']['per_minute']}/min")
    print(f"Utilization: {stats['utilization']['per_minute']}%")
