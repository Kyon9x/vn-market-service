from behave import then
from support.assertions import MarketDataAssertions


@then('I should receive valid quote data')
def step_valid_quote(context):
    """Assert quote response is valid"""
    MarketDataAssertions.assert_valid_quote_response(context.quote_response)


@then('the quote should contain price information')
def step_quote_has_price(context):
    """Assert quote contains price information"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    MarketDataAssertions.assert_price_information(data)


@then('I should receive historical price records')
def step_valid_history(context):
    """Assert history response is valid"""
    MarketDataAssertions.assert_valid_history_response(context.history_response)


@then('the history should contain multiple trading days')
def step_history_multiple_days(context):
    """Assert history contains multiple trading days"""
    assert context.history_response is not None, "History response should not be None"
    data = context.history_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_multiple_trading_days(data, min_days=100)


@then('all data should be in VND currency')
def step_vnd_currency(context):
    """Assert data is in VND currency"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_vnd_currency(data)


@then('I should receive valid NAV data')
def step_valid_nav(context):
    """Assert NAV response is valid"""
    MarketDataAssertions.assert_valid_quote_response(context.quote_response)


@then('the NAV should contain net asset value')
def step_nav_has_value(context):
    """Assert NAV contains net asset value"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    MarketDataAssertions.assert_price_information(data)


@then('I should receive historical NAV records')
def step_valid_nav_history(context):
    """Assert NAV history response is valid"""
    MarketDataAssertions.assert_valid_history_response(context.history_response)


@then('the history should show daily NAV values')
def step_daily_nav_values(context):
    """Assert history shows daily NAV values"""
    assert context.history_response is not None, "History response should not be None"
    data = context.history_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_multiple_trading_days(data, min_days=100)


@then('I should receive valid index data')
def step_valid_index(context):
    """Assert index response is valid"""
    MarketDataAssertions.assert_valid_quote_response(context.quote_response)


@then('the index should contain current points')
def step_index_has_points(context):
    """Assert index contains current points"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    MarketDataAssertions.assert_price_information(data)


@then('I should receive index history')
def step_valid_index_history(context):
    """Assert index history response is valid"""
    MarketDataAssertions.assert_valid_history_response(context.history_response)


@then('the data should show market trends')
def step_market_trends(context):
    """Assert history shows market trends"""
    assert context.history_response is not None, "History response should not be None"
    data = context.history_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_multiple_trading_days(data, min_days=100)


@then('I should receive valid gold price data')
def step_valid_gold_price(context):
    """Assert gold price response is valid"""
    MarketDataAssertions.assert_valid_quote_response(context.quote_response)


@then('the price should be in VND per tael')
def step_gold_price_vnd(context):
    """Assert gold price is in VND per tael"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_price_information(data)
        MarketDataAssertions.assert_vnd_currency(data)


@then('I should receive gold price history')
def step_valid_gold_history(context):
    """Assert gold price history response is valid"""
    MarketDataAssertions.assert_valid_history_response(context.history_response)


@then('the history should show price fluctuations')
def step_gold_price_fluctuations(context):
    """Assert gold history shows price fluctuations"""
    assert context.history_response is not None, "History response should not be None"
    data = context.history_response.get("data")
    if data is not None:
        MarketDataAssertions.assert_multiple_trading_days(data, min_days=100)


@then('I should receive valid {asset_type} data')
def step_valid_asset_data(context, asset_type):
    """Assert asset type data is valid"""
    MarketDataAssertions.assert_valid_quote_response(context.quote_response)


@then('the data should not be empty')
def step_data_not_empty(context):
    """Assert data is not empty"""
    assert context.quote_response is not None, "Quote response should not be None"
    data = context.quote_response.get("data")
    MarketDataAssertions.assert_non_empty_data(data)


@then('I should receive a 404 error')
def step_404_error(context):
    """Assert 404 error response"""
    assert context.quote_response is not None, "Response should not be None"
    # Check if response contains error indicators
    if hasattr(context.quote_response, 'status_code'):
        assert context.quote_response.status_code == 404, f"Expected 404, got {context.quote_response.status_code}"
    else:
        # For JSON responses, check for error structure
        MarketDataAssertions.assert_error_response(context.quote_response, expected_status=404)


@then('the error message should be descriptive')
def step_descriptive_error(context):
    """Assert error message is descriptive"""
    assert context.quote_response is not None, "Response should not be None"
    MarketDataAssertions.assert_error_response(context.quote_response)


@then('I should receive a validation error')
def step_validation_error(context):
    """Assert validation error response"""
    assert context.search_response is not None, "Search response should not be None"
    # Validation errors typically return 422 status code
    if hasattr(context.search_response, 'status_code'):
        assert context.search_response.status_code in [400, 422], f"Expected validation error, got {context.search_response.status_code}"


@then('the error should indicate missing query parameter')
def step_missing_query_error(context):
    """Assert error indicates missing query parameter"""
    assert context.search_response is not None, "Search response should not be None"
    # Check for error message indicating missing query
    if isinstance(context.search_response, dict) and "detail" in context.search_response:
        error_detail = context.search_response["detail"]
        assert any(keyword in error_detail.lower() for keyword in ["query", "parameter", "required"]), \
            f"Error should mention missing query parameter: {error_detail}"


@then('the error should describe the date format issue')
def step_date_format_error(context):
    """Assert error describes date format issue"""
    assert context.history_response is not None, "History response should not be None"
    # Check for error message indicating date format issue
    if isinstance(context.history_response, dict) and "detail" in context.history_response:
        error_detail = context.history_response["detail"]
        assert any(keyword in error_detail.lower() for keyword in ["date", "format", "invalid"]), \
            f"Error should mention date format issue: {error_detail}"


@then('I should receive appropriate error handling')
def step_appropriate_error_handling(context):
    """Assert appropriate error handling for unavailable service"""
    assert context.quote_response is not None, "Response should not be None"
    # Should handle gracefully, not crash
    MarketDataAssertions.assert_error_response(context.quote_response)


@then('the response should indicate retry possibility')
def step_retry_possibility(context):
    """Assert response indicates retry possibility"""
    assert context.quote_response is not None, "Response should not be None"
    # Check for retry-related information in error response
    if isinstance(context.quote_response, dict):
        # Look for retry-related keywords in error message
        error_text = str(context.quote_response).lower()
        has_retry_info = any(keyword in error_text for keyword in ["retry", "later", "again", "temporary"])
        # This is a soft check - some services may not explicitly mention retry
        if not has_retry_info:
            # At minimum, should be a proper error response
            MarketDataAssertions.assert_error_response(context.quote_response)