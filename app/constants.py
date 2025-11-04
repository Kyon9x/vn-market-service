# Asset classification constants to eliminate hardcoded values across the codebase

# Asset Type Classifications
ASSET_TYPE_FUND = "FUND"
ASSET_TYPE_STOCK = "STOCK"
ASSET_TYPE_INDEX = "INDEX"
ASSET_TYPE_GOLD = "GOLD"

# Asset Class Mappings
ASSET_CLASS_FUND = "Investment Fund"
ASSET_CLASS_STOCK = "Equity"
ASSET_CLASS_INDEX = "Index"
ASSET_CLASS_GOLD = "Commodity"

# Asset Sub-Class Mappings
ASSET_SUB_CLASS_FUND = "Mutual Fund"
ASSET_SUB_CLASS_STOCK = "Stock"
ASSET_SUB_CLASS_INDEX = "Market Index"
ASSET_SUB_CLASS_GOLD = "Precious Metal"

# Currency Mappings
CURRENCY_VND = "VND"
CURRENCY_USD = "USD"

# Data Source
DATA_SOURCE_VN_MARKET = "VN_MARKET"

# Asset Classification Mapping Dictionary
ASSET_CLASSIFICATION = {
    ASSET_TYPE_FUND: {
        "asset_class": ASSET_CLASS_FUND,
        "asset_sub_class": ASSET_SUB_CLASS_FUND,
        "currency": CURRENCY_VND,
        "data_source": DATA_SOURCE_VN_MARKET
    },
    ASSET_TYPE_STOCK: {
        "asset_class": ASSET_CLASS_STOCK,
        "asset_sub_class": ASSET_SUB_CLASS_STOCK,
        "currency": CURRENCY_VND,
        "data_source": DATA_SOURCE_VN_MARKET
    },
    ASSET_TYPE_INDEX: {
        "asset_class": ASSET_CLASS_INDEX,
        "asset_sub_class": ASSET_SUB_CLASS_INDEX,
        "currency": CURRENCY_VND,
        "data_source": DATA_SOURCE_VN_MARKET
    },
    ASSET_TYPE_GOLD: {
        "asset_class": ASSET_CLASS_GOLD,
        "asset_sub_class": ASSET_SUB_CLASS_GOLD,
        "currency": CURRENCY_VND,  # Default to VND
        "data_source": DATA_SOURCE_VN_MARKET
    }
}

# Index Symbol Mappings
INDEX_SYMBOLS = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]

# Gold Provider Symbols (for detection)
GOLD_PROVIDERS = {
    "VN.GOLD": "SJC",
    "VN.GOLD.C": "SJC"
}
