import httpx
import time
import os
from typing import Dict, Any, Optional


class MarketDataAPI:
    """HTTP client wrapper for VN Market Service API"""
    
    def __init__(self, base_url: Optional[str] = None):
        if base_url is None:
            base_url = os.getenv("TEST_BASE_URL", "http://localhost:8765")
        self.base_url = base_url
        # Use longer timeout for history requests which can be slow
        # Include test header to bypass rate limiting during automated tests
        self.client = httpx.Client(timeout=120.0, headers={"X-Test-Mode": "true"})
    
    def wait_for_service(self, timeout: int = 60) -> bool:
        """Wait for service to be healthy"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = self.client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(2)
        return False
    
    def get_health(self) -> Dict[str, Any]:
        """Get service health status"""
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def search(self, query: str) -> Dict[str, Any]:
        """Search for assets by query"""
        response = self.client.get(f"{self.base_url}/search", params={"query": query})
        response.raise_for_status()
        return response.json()
    
    def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get latest quote for symbol"""
        response = self.client.get(f"{self.base_url}/quote/{symbol}")
        return response.json()
    
    def get_history(self, symbol: str, days: int = 365) -> Dict[str, Any]:
        """Get historical data for symbol"""
        response = self.client.get(f"{self.base_url}/history/{symbol}", params={"days": days})
        return response.json()
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()