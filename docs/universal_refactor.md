# Universal Refactor for responses

## /search/{symbol} Endpoint and /Search Endpoint
    In these endpoints, I want to refactor the asset profile construction to better categorize assets.
    I want to categorize gold assets under a more specific asset class and subclass.
    Stock also need to fill more specific asset class and subclass.

    Here are the changes I want to make:
    1. For gold assets: 
         - Set `asset_class` to "Commodity"
         - Set `asset_sub_class` to "Precious Metal"
    2. For stock assets:
        - Set `asset_class` to "Equity"
        - Set `asset_sub_class` to "Stock"
        - get more asset data from vnstock via Company Information Commands in docs/docs/VNSTOCK_COMMANDS_REFERENCE.md
    3. For fund assets:
        - Set `asset_class` to "Investment Fund"
        - Set `asset_sub_class` to "Mutual Fund"
        - get more asset data from vnstock via Mutual Funds Commands in docs/docs/VNSTOCK_COMMANDS_REFERENCE.md
    4. For index assets:
        - Set `asset_class` to "Index"
        - Set `asset_sub_class` to "Market Index"
        - get more asset data from vnstock via International Markets Commands in docs/docs/VNSTOCK_COMMANDS_REFERENCE.md
    5. For other asset types, retain the existing logic for determining `asset_class` and `asset_sub_class`.
    Here is the updated code snippet for constructing the `AssetProfile`:

    Consider to create general enum or constant mapping for asset types to their respective classes and subclasses to avoid hardcoding strings multiple times.

    ```json
        {
            "isin": asset.isin,
            "name": asset.name,
            "asset_type": asset.asset_type,
            "symbol": asset.symbol,
            "asset_class": "",
            "asset_sub_class": asset.asset_sub_class,
            "notes": "",
            "countries": "Vietnam",
            "categories": asset.categories,
            "exchange": "",
            "attributes": "",
            "currency": "VND",
            "data_source": "VN_MARKET",
            "sectors": "",
            "url": "",
        })
    ```

## /quote and /history/{symbol} Endpoints
    In these endpoints, I want to ensure that the response structure is consistent and includes all necessary fields for different asset types.
    I want to add additional fields to the response to provide more comprehensive information about the assets.
    1. Add a `currency` field to indicate the currency of the asset prices.
    2. Add a `data_source` field to specify the source of the data
    3. for `price` if other assets like gold fund close price is must have adjclose same as close

    Here is the updated code snippet for constructing the response:

    ```json
        history_response = {
            "symbol": "DCDS",
            "history": [
                {
                "date": "2025-09-15",
                "open": 108248.43,
                "high": 108248.43,
                "low": 108248.43,
                "close": 108248.43,
                "adjclose": 108248.43,
                "volume": 0
                }
            ],
            "currency": "VND",
            "data_source": "VN_MARKET"
        }

        quote_response = {
            "symbol": "FPT",
            "open": 108248.43,
            "high": 108248.43,
            "low": 108248.43,
            "close": 108248.43,
            "adjclose": 108248.43,
            "volume": 0,
            "currency": "VND",
            "data_source": "VN_MARKET"
        }
    ```
## General Improvements
    1. Create enums or constant mappings for asset classes and subclasses to avoid hardcoding strings multiple times.
    2. Implement validation to ensure that the new fields are correctly populated based on the asset type.
    3. anywhere data_source is used, ensure it is consistently set to "VN_MARKET" for all relevant responses.
    4. make sure all assets have the same response structure with necessary fields included.
   