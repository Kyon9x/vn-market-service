"""
IP-based Rate Limiter - Extends global rate limiting with per-IP address tracking.

This module provides IP-aware rate limiting that wraps the existing global rate limiter,
allowing fair resource allocation among different client IP addresses while maintaining
the global rate limiting protection for the vnstock API.
"""

import threading
import time
from typing import Dict, Any, Optional, List
from collections import defaultdict

from .rate_limit_protector import RateLimitProtector


class IPRateLimiter:
    """
    IP-aware rate limiter that provides per-IP address rate limiting.

    Features:
    - Per-IP rate limit tracking separate from global limits
    - Memory-efficient tracking with automatic cleanup
    - Integration with existing global rate limiter
    - Configurable limits per IP
    - Thread-safe operations
    """

    DEFAULT_CONFIG = {
        'max_calls_per_minute': 60,
        'max_calls_per_hour': 500,
        'delay_between_calls_ms': 200,
        'enable_throttling': True,
        'max_tracked_ips': 10000,  # Prevent memory exhaustion
        'cleanup_interval_seconds': 300,  # Clean up every 5 minutes
    }

    def __init__(self, global_limiter: RateLimitProtector, config: Optional[Dict] = None):
        """
        Initialize IP-based rate limiter.

        Args:
            global_limiter: The existing global rate limiter instance
            config: Optional configuration dictionary
        """
        self.global_limiter = global_limiter
        self.config = self.DEFAULT_CONFIG.copy()
        if config:
            self.config.update(config)

        # Thread-safe IP tracking
        self._lock = threading.RLock()
        self._ip_limiters: Dict[str, RateLimitProtector] = {}
        self._last_cleanup = time.time()

        # Statistics
        self._total_ips_tracked = 0
        self._cleanup_count = 0

    def check_ip_rate_limit(self, client_ip: str) -> bool:
        """
        Check if IP-specific rate limit allows the request.

        Args:
            client_ip: Client IP address string

        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.config['enable_throttling']:
            return True

        with self._lock:
            # Periodic cleanup to prevent memory leaks
            self._periodic_cleanup()

            # Get or create IP-specific limiter
            if client_ip not in self._ip_limiters:
                self._ip_limiters[client_ip] = RateLimitProtector(self.config)
                self._total_ips_tracked = len(self._ip_limiters)

            ip_limiter = self._ip_limiters[client_ip]
            return not ip_limiter.should_throttle()

    def record_ip_call(self, client_ip: str):
        """
        Record that an API call was made for this IP.

        Args:
            client_ip: Client IP address string
        """
        with self._lock:
            if client_ip in self._ip_limiters:
                self._ip_limiters[client_ip].record_call()

    def should_throttle_ip(self, client_ip: str) -> bool:
        """
        Check if the given IP should be throttled.

        Args:
            client_ip: Client IP address string

        Returns:
            True if IP should be throttled, False otherwise
        """
        return not self.check_ip_rate_limit(client_ip)

    def get_ip_stats(self, client_ip: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific IP.

        Args:
            client_ip: Client IP address string

        Returns:
            Dictionary with IP-specific stats, or None if IP not tracked
        """
        with self._lock:
            if client_ip not in self._ip_limiters:
                return None
            return self._ip_limiters[client_ip].get_stats()

    def get_all_ip_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all tracked IPs.

        Returns:
            Dictionary mapping IP addresses to their statistics
        """
        with self._lock:
            # Clean up before reporting stats
            self._cleanup_inactive_ips()

            return {
                ip: limiter.get_stats()
                for ip, limiter in self._ip_limiters.items()
            }

    def get_stats_summary(self) -> Dict[str, Any]:
        """
        Get summary statistics for the IP rate limiter.

        Returns:
            Dictionary with overall IP rate limiting statistics
        """
        with self._lock:
            all_stats = self.get_all_ip_stats()

            # Calculate aggregate statistics
            total_ips = len(all_stats)
            throttled_ips = sum(1 for stats in all_stats.values() if stats['throttled_calls'] > 0)
            active_ips = sum(1 for stats in all_stats.values()
                           if stats['current_rates']['per_minute'] > 0 or stats['current_rates']['per_hour'] > 0)

            return {
                'enabled': self.config['enable_throttling'],
                'total_ips_tracked': total_ips,
                'active_ips': active_ips,
                'throttled_ips': throttled_ips,
                'cleanup_count': self._cleanup_count,
                'config': {
                    'max_calls_per_minute': self.config['max_calls_per_minute'],
                    'max_calls_per_hour': self.config['max_calls_per_hour'],
                    'delay_ms': self.config['delay_between_calls_ms'],
                    'max_tracked_ips': self.config['max_tracked_ips'],
                }
            }

    def reset_ip_stats(self, client_ip: Optional[str] = None):
        """
        Reset statistics for a specific IP or all IPs.

        Args:
            client_ip: Specific IP to reset, or None to reset all
        """
        with self._lock:
            if client_ip:
                if client_ip in self._ip_limiters:
                    self._ip_limiters[client_ip].reset_stats()
            else:
                for limiter in self._ip_limiters.values():
                    limiter.reset_stats()
                self._cleanup_count = 0

    def _periodic_cleanup(self):
        """Perform periodic cleanup of inactive IPs."""
        now = time.time()
        if now - self._last_cleanup > self.config['cleanup_interval_seconds']:
            self._cleanup_inactive_ips()
            self._last_cleanup = now

    def _cleanup_inactive_ips(self):
        """Remove IPs that haven't made calls recently to prevent memory leaks."""
        # Keep only IPs that have made calls in the last hour
        cutoff_time = time.time() - 3600  # 1 hour ago

        ips_to_remove = []
        for ip, limiter in self._ip_limiters.items():
            stats = limiter.get_stats()
            # If no calls in the last hour and below capacity, consider for removal
            if (stats['current_rates']['per_hour'] == 0 and
                len(limiter._call_timestamps) == 0):
                # Check if all timestamps are old
                if limiter._last_call_time == 0 or limiter._last_call_time < cutoff_time:
                    ips_to_remove.append(ip)

        # Remove inactive IPs, but respect the max_tracked_ips limit
        # Keep the most recently active IPs
        if len(self._ip_limiters) > self.config['max_tracked_ips']:
            # Sort by last call time (most recent first)
            sorted_ips = sorted(
                self._ip_limiters.items(),
                key=lambda x: x[1]._last_call_time,
                reverse=True
            )

            # Remove oldest IPs beyond the limit
            for ip, _ in sorted_ips[self.config['max_tracked_ips']:]:
                if ip not in ips_to_remove:
                    ips_to_remove.append(ip)

        # Perform the removal
        for ip in ips_to_remove:
            del self._ip_limiters[ip]

        if ips_to_remove:
            self._cleanup_count += len(ips_to_remove)

    def update_config(self, config: Dict):
        """
        Update IP rate limiter configuration.

        Args:
            config: Configuration dictionary with new values
        """
        with self._lock:
            old_config = self.config.copy()
            self.config.update(config)

            # If limits changed, we might need to update existing IP limiters
            # For simplicity, we'll let existing limiters keep their old config
            # New IPs will use the new config
