from behave import when
from support.data_utils import TestDataGenerator


@when('I select the first search result')
def step_select_first_result(context):
    """Select the first result from search"""
    assert context.search_results is not None, "Search results should not be None"
    assert "results" in context.search_results, "Search results should contain 'results' field"
    assert len(context.search_results["results"]) > 0, "Search results should not be empty"

    context.selected_symbol = context.search_results["results"][0]["symbol"]
    print(f"🐛 TEST LOG: Selected symbol: {context.selected_symbol}")


@when('I select the first search result to get the symbol')
def step_select_first_result_to_get_symbol(context):
    """Select the first result from search and extract symbol"""
    assert context.search_results is not None, "Search results should not be None"
    assert "results" in context.search_results, "Search results should contain 'results' field"
    assert len(context.search_results["results"]) > 0, "Search results should not be empty"
    
    context.selected_symbol = context.search_results["results"][0]["symbol"]


@when('I request the latest quote for that symbol')
def step_request_quote(context):
    """Request latest quote for selected symbol"""
    context.quote_response = context.api.get_quote(context.selected_symbol)
    if context.quote_response and "close" in context.quote_response:
        print(f"🐛 TEST LOG: Quote close value: {context.quote_response['close']}")
    else:
        print(f"🐛 TEST LOG: Quote response: {context.quote_response}")


@when('I request historical data for the past x days')
def step_request_history(context):
    """Request historical data for selected symbol"""
    context.history_response = context.api.get_history(context.selected_symbol, days=context.history_days)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: History latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: History latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: History response: {context.history_response}")


@when('I request the latest NAV for that fund')
def step_request_nav(context):
    """Request latest NAV for selected fund"""
    context.quote_response = context.api.get_quote(context.selected_symbol)


@when('I request historical NAV data for the past year')
def step_request_fund_history(context):
    """Request historical NAV data for selected fund"""
    context.history_response = context.api.get_history(context.selected_symbol, days=365)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: Fund history latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: Fund history latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: Fund history response: {context.history_response}")


@when('I select VNINDEX from the results')
def step_select_vnindex(context):
    """Select VNINDEX from search results"""
    assert context.search_results is not None, "Search results should not be None"
    assert "results" in context.search_results, "Search results should contain 'results' field"
    
    # Find VNINDEX in results
    vnindex_found = False
    for result in context.search_results["results"]:
        if result["symbol"] == "VNINDEX":
            context.selected_symbol = "VNINDEX"
            vnindex_found = True
            break
    
    assert vnindex_found, "VNINDEX should be found in search results"


@when('I request the latest index value')
def step_request_index_quote(context):
    """Request latest index value"""
    context.quote_response = context.api.get_quote(context.selected_symbol)


@when('I request historical index data')
def step_request_index_history(context):
    """Request historical index data"""
    context.history_response = context.api.get_history(context.selected_symbol, days=365)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: Index history latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: Index history latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: Index history response: {context.history_response}")


@when('I select SJC gold from the results')
def step_select_sjc_gold(context):
    """Select SJC gold from search results"""
    assert context.search_results is not None, "Search results should not be None"
    assert "results" in context.search_results, "Search results should contain 'results' field"
    
    # Find SJC gold in results
    sjc_found = False
    for result in context.search_results["results"]:
        if "SJC" in result["symbol"].upper():
            context.selected_symbol = result["symbol"]
            sjc_found = True
            break
    
    assert sjc_found, "SJC gold should be found in search results"


@when('I request the latest gold price')
def step_request_gold_quote(context):
    """Request latest gold price"""
    context.quote_response = context.api.get_quote(context.selected_symbol)


@when('I request historical gold prices')
def step_request_gold_history(context):
    """Request historical gold prices"""
    context.history_response = context.api.get_history(context.selected_symbol, days=365)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: Gold history latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: Gold history latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: Gold history response: {context.history_response}")


@when('I request the latest quote')
def step_request_latest_quote(context):
    """Request latest quote for asset type scenario"""
    context.quote_response = context.api.get_quote(context.search_query)


@when('I call the quote endpoint')
def step_call_quote_endpoint(context):
    """Call quote endpoint with invalid symbol"""
    context.quote_response = context.api.get_quote(context.invalid_symbol)


@when('I call the search endpoint')
def step_call_search_endpoint(context):
    """Call search endpoint with empty query"""
    context.search_response = context.api.search(context.empty_query)


@when('I call the history endpoint')
def step_call_history_endpoint(context):
    """Call history endpoint with invalid dates"""
    context.history_response = context.api.get_history(
        TestDataGenerator.get_random_stock_symbol(),
        start_date=context.invalid_start_date,
        end_date=context.invalid_end_date
    )


@when('I request market data')
def step_request_market_data(context):
    """Request market data with unavailable symbol"""
    context.quote_response = context.api.get_quote(context.unavailable_symbol)


@when('I request the latest data for that symbol')
def step_request_latest_data_for_symbol(context):
    """Request latest data for the selected symbol"""
    context.quote_response = context.api.get_quote(context.selected_symbol)


@when('I request the historical data for the past 365 days for that symbol')
def step_request_historical_data_for_symbol(context):
    """Request historical data for the past 365 days for the selected symbol"""
    context.history_response = context.api.get_history(context.selected_symbol, days=365)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: Regression history latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: Regression history latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: Regression history response: {context.history_response}")


@when('I request the historical data for the past {days:d} days for that symbol')
def step_request_historical_data_with_days(context, days):
    """Request historical data for specified number of days for the selected symbol"""
    context.history_response = context.api.get_history(context.selected_symbol, days=days)
    if context.history_response and "history" in context.history_response and context.history_response["history"]:
        latest_record = context.history_response["history"][-1]  # Most recent
        if "close" in latest_record:
            print(f"🐛 TEST LOG: Custom days ({days}) history latest close value: {latest_record['close']}")
        else:
            print(f"🐛 TEST LOG: Custom days ({days}) history latest record: {latest_record}")
    else:
        print(f"🐛 TEST LOG: Custom days ({days}) history response: {context.history_response}")