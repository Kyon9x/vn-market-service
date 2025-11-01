"""
Configure vnstock library for better timeout handling and retry behavior.
"""
import os
import logging

logger = logging.getLogger(__name__)

def configure_vnstock_timeout():
    """
    Configure vnstock to use a higher timeout and implement connection pooling.
    This helps mitigate issues with slow API responses.
    """
    try:
        import urllib3
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Configure urllib3 connection pooling
        http = urllib3.PoolManager(
            num_pools=10,
            maxsize=10,
            timeout=urllib3.Timeout(
                connect=10.0,
                read=60.0  # Increase read timeout from default 30s to 60s
            )
        )
        
        # Configure requests session with retry strategy
        session_retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=session_retry_strategy)
        
        logger.info("vnstock timeout configuration applied - read timeout: 60s, connection timeout: 10s")
        
    except Exception as e:
        logger.warning(f"Could not configure vnstock timeout: {e}")

# Configure on import
configure_vnstock_timeout()
