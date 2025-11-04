from typing import Dict, Any, List


class MarketDataAssertions:
    """Custom assertions for market data validation"""
    
    @staticmethod
    def assert_valid_quote_response(response: Dict[str, Any]):
        """Assert that quote response is valid"""
        assert response is not None, "Quote response should not be None"
        assert "data" in response, "Response should contain 'data' field"
        
        data = response["data"]
        if data is not None:
            assert isinstance(data, dict), "Quote data should be a dictionary"
    
    @staticmethod
    def assert_valid_history_response(response: Dict[str, Any]):
        """Assert that history response is valid"""
        assert response is not None, "History response should not be None"
        assert "data" in response, "Response should contain 'data' field"
        
        data = response["data"]
        if data is not None:
            assert isinstance(data, list), "History data should be a list"
    
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
        assert len(history_data) >= min_days, f"History should contain at least {min_days} trading days, got {len(history_data)}"
    
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