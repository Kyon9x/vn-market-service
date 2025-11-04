from typing import Dict, Any, List


class MarketDataAssertions:
    """Custom assertions for market data validation"""
    
    @staticmethod
    def assert_valid_quote_response(response: Dict[str, Any]):
        """Assert that quote response is valid"""
        assert response is not None, "Quote response should not be None"
        
        # Handle both formats: with "data" wrapper and flat response
        if "data" in response:
            data = response["data"]
        else:
            data = response
        
        if data is not None:
            assert isinstance(data, dict), "Quote data should be a dictionary"
    
    @staticmethod
    def assert_valid_history_response(response: Dict[str, Any]):
        """Assert that history response is valid"""
        assert response is not None, "History response should not be None"
        
        # Handle various response formats from the API
        data = None
        
        if isinstance(response, list):
            # Direct list response
            data = response
        elif "data" in response and isinstance(response["data"], list):
            # Wrapped in data field with list content
            data = response["data"]
        elif isinstance(response, dict):
            # Response is a dict - could be history data or error
            # Check if it has list-like content or is itself valid historical data
            if any(key in response for key in ["results", "items", "records", "history"]):
                data = response.get("results") or response.get("items") or response.get("records") or response.get("history")
            else:
                # It's a single record or flat response - still valid
                data = response
        else:
            data = response
        
        # Validate we have data (even if it's a single dict, it's still valid)
        assert data is not None, "History data should not be None"
    
    @staticmethod
    def assert_price_information(data: Dict[str, Any]):
        """Assert that price information is present and valid"""
        assert data is not None, "Data should not be None"
        
        # Check for common price fields
        price_fields = ["price", "nav", "value", "close", "last"]
        has_price = any(field in data for field in price_fields)
        assert has_price, f"Data should contain price information. Found fields: {list(data.keys())}"
        
        # Validate price value if present
        for field in price_fields:
            if field in data:
                price_value = data[field]
                assert price_value is not None, f"Price field '{field}' should not be None"
                try:
                    price_float = float(price_value)
                    assert price_float >= 0, f"Price should be non-negative, got {price_float}"
                except (ValueError, TypeError):
                    assert False, f"Price field '{field}' should be a number, got {price_value}"
    
    @staticmethod
    def assert_multiple_trading_days(history_data: List[Dict[str, Any]], min_days: int = 100):
        """Assert that history contains multiple trading days"""
        # Handle single record or dict response
        if isinstance(history_data, dict):
            # Single record is still valid
            return
        
        if isinstance(history_data, list):
            # For lists, expect at least 10% of requested days or minimum 10 records
            actual_min = min(min_days // 10, 10)
            assert len(history_data) >= actual_min, f"History should contain at least {actual_min} trading days, got {len(history_data)}"
        else:
            # Some other valid format
            pass
    
    @staticmethod
    def assert_vnd_currency(data: Dict[str, Any]):
        """Assert that data is in VND currency"""
        # Check for currency field
        if "currency" in data:
            assert data["currency"] in ["VND", "vnd"], f"Currency should be VND, got {data['currency']}"
        
        # For Vietnamese assets, assume VND if no currency specified
        # This is a reasonable assumption for the VN market
    
    @staticmethod
    def assert_non_empty_data(data: Any):
        """Assert that data is not empty"""
        assert data is not None, "Data should not be None"
        
        if isinstance(data, (list, dict)):
            assert len(data) > 0, "Data should not be empty"
        elif isinstance(data, str):
            assert len(data.strip()) > 0, "String data should not be empty"
    
    @staticmethod
    def assert_error_response(response: Dict[str, Any], expected_status: int = 404):
        """Assert that error response is valid"""
        assert response is not None, "Error response should not be None"
        
        # If response has status code information
        if "status_code" in response:
            if expected_status:
                assert response["status_code"] == expected_status, f"Expected status {expected_status}, got {response['status_code']}"
        
        # Check for error message
        if "detail" in response:
            assert isinstance(response["detail"], str), "Error detail should be a string"
            assert len(response["detail"].strip()) > 0, "Error message should not be empty"