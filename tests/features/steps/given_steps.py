from behave import given
from support.api_client import MarketDataAPI
from support.data_utils import TestDataGenerator


@given('the market data service is running')
def step_service_running(context):
    """Initialize API client and wait for service"""
    context.api = MarketDataAPI()
    if not context.api.wait_for_service():
        raise Exception("Service not available within timeout")


@given('the service health check passes')
def step_health_check(context):
    """Verify service health"""
    health = context.api.get_health()
    assert health['status'] == 'healthy', f"Service health check failed: {health}"


@given('I search for stocks with a common symbol')
def step_search_stocks(context):
    """Search for stocks using a random common symbol"""
    context.search_query = TestDataGenerator.get_random_stock_symbol()
    context.search_results = context.api.search(context.search_query)


@given('I search for mutual funds with a fund symbol')
def step_search_funds(context):
    """Search for mutual funds using a random fund symbol"""
    context.search_query = TestDataGenerator.get_random_fund_symbol()
    context.search_results = context.api.search(context.search_query)


@given('I search for market indices')
def step_search_indices(context):
    """Search for market indices"""
    context.search_query = "VNINDEX"
    context.search_results = context.api.search(context.search_query)


@given('I search for gold prices')
def step_search_gold(context):
    """Search for gold prices"""
    context.search_query = "SJC"
    context.search_results = context.api.search(context.search_query)


@given('I search for {asset_type} with query {query}')
def step_search_asset_type(context, asset_type, query):
    """Search for specific asset type with given query"""
    context.search_query = query
    context.asset_type = asset_type
    context.search_results = context.api.search(query)


@given('I request data for an invalid symbol')
def step_invalid_symbol(context):
    """Set up invalid symbol for testing"""
    context.invalid_symbol = TestDataGenerator.get_invalid_symbol()


@given('I provide an empty search query')
def step_empty_search_query(context):
    """Set up empty search query"""
    context.empty_query = ""


@given('I request historical data with invalid dates')
def step_invalid_dates(context):
    """Set up invalid date parameters"""
    context.invalid_start_date = "invalid-date"
    context.invalid_end_date = "also-invalid"


@given('the external data source is unavailable')
def step_external_unavailable(context):
    """Simulate external data source unavailability"""
    # This would typically involve mocking or service manipulation
    # For now, we'll use a symbol that's unlikely to exist
    context.unavailable_symbol = "UNAVAILABLE_DATA_SOURCE"