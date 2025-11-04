from behave import fixture, use_fixture
from support.api_client import MarketDataAPI


@fixture
def api_client(context):
    """Fixture to provide API client for tests"""
    api = MarketDataAPI()
    context.api = api
    yield api
    api.close()


def before_all(context):
    """Setup before all scenarios"""
    context.base_url = context.config.userdata.get("base_url", "http://localhost:8765")


def before_scenario(context, scenario):
    """Setup before each scenario"""
    # Clean up any previous context data
    context.search_results = None
    context.quote_response = None
    context.history_response = None
    context.selected_symbol = None
    context.search_query = None


def after_scenario(context, scenario):
    """Cleanup after each scenario"""
    # Clean up API client if it exists
    if hasattr(context, 'api') and context.api:
        try:
            context.api.close()
        except:
            pass


def after_all(context):
    """Cleanup after all scenarios"""
    pass