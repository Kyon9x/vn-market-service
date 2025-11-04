from pydantic import BaseModel
from typing import List, Optional
from enum import Enum
from app.constants import (
    ASSET_CLASS_FUND, ASSET_CLASS_STOCK, ASSET_CLASS_INDEX, ASSET_CLASS_GOLD,
    ASSET_SUB_CLASS_FUND, ASSET_SUB_CLASS_STOCK, ASSET_SUB_CLASS_INDEX, ASSET_SUB_CLASS_GOLD,
    CURRENCY_VND, CURRENCY_USD, DATA_SOURCE_VN_MARKET
)


class AssetClass(str, Enum):
    COMMODITY = ASSET_CLASS_GOLD
    EQUITY = ASSET_CLASS_STOCK
    INVESTMENT_FUND = ASSET_CLASS_FUND
    INDEX = ASSET_CLASS_INDEX
    OTHER = "Other"


class AssetSubClass(str, Enum):
    PRECIOUS_METAL = ASSET_SUB_CLASS_GOLD
    STOCK = ASSET_SUB_CLASS_STOCK
    MUTUAL_FUND = ASSET_SUB_CLASS_FUND
    MARKET_INDEX = ASSET_SUB_CLASS_INDEX
    OTHER = "Other"

class FundBasicInfo(BaseModel):
    symbol: str
    fund_name: str
    asset_type: str
    asset_class: str = ASSET_CLASS_FUND
    asset_sub_class: str = ASSET_SUB_CLASS_FUND
    data_source: str = DATA_SOURCE_VN_MARKET

class FundListResponse(BaseModel):
    funds: List[FundBasicInfo]
    total: int

class FundSearchResponse(BaseModel):
    symbol: str
    fund_name: str
    fund_type: Optional[str] = None
    management_company: Optional[str] = None
    inception_date: Optional[str] = None
    nav_per_unit: Optional[float] = None
    asset_class: str = ASSET_CLASS_FUND
    asset_sub_class: str = ASSET_SUB_CLASS_FUND
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class FundQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float = 0.0
    nav: float
    date: str
    asset_class: str = ASSET_CLASS_FUND
    asset_sub_class: str = ASSET_SUB_CLASS_FUND
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class FundHistoryItem(BaseModel):
    date: str
    nav: float
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float = 0.0

class FundHistoryResponse(BaseModel):
    symbol: str
    history: List[FundHistoryItem]
    asset_class: str = ASSET_CLASS_FUND
    asset_sub_class: str = ASSET_SUB_CLASS_FUND
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class StockSearchResponse(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    industry: Optional[str] = None
    company_type: Optional[str] = None
    asset_class: str = ASSET_CLASS_STOCK
    asset_sub_class: str = ASSET_SUB_CLASS_STOCK
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class StockQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float
    date: str
    asset_class: str = ASSET_CLASS_STOCK
    asset_sub_class: str = ASSET_SUB_CLASS_STOCK
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class StockHistoryItem(BaseModel):
    date: str
    nav: float
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float

class StockHistoryResponse(BaseModel):
    symbol: str
    history: List[StockHistoryItem]
    asset_class: str = ASSET_CLASS_STOCK
    asset_sub_class: str = ASSET_SUB_CLASS_STOCK
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class IndexSearchResponse(BaseModel):
    symbol: str
    name: str
    asset_type: str = "INDEX"
    asset_class: str = ASSET_CLASS_INDEX
    asset_sub_class: str = ASSET_SUB_CLASS_INDEX
    exchange: str
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET


class IndexQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float
    date: str
    asset_class: str = ASSET_CLASS_INDEX
    asset_sub_class: str = ASSET_SUB_CLASS_INDEX
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class IndexHistoryItem(BaseModel):
    date: str
    nav: float
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float

class IndexHistoryResponse(BaseModel):
    symbol: str
    history: List[IndexHistoryItem]
    asset_class: str = ASSET_CLASS_INDEX
    asset_sub_class: str = ASSET_SUB_CLASS_INDEX
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

class SearchResult(BaseModel):
    symbol: str
    name: str
    asset_type: str
    asset_class: str = ""
    asset_sub_class: str = ""
    exchange: str
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int

class GoldSearchResponse(BaseModel):
    symbol: str
    name: str
    provider: str
    provider_name: str
    asset_type: str
    asset_class: str = ASSET_CLASS_GOLD
    asset_sub_class: str = ASSET_SUB_CLASS_GOLD
    exchange: str
    currency: str = CURRENCY_VND
    unit: Optional[str] = None
    unit_description: Optional[str] = None
    data_source: str = DATA_SOURCE_VN_MARKET

class GoldQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float = 0.0
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None
    date: str
    asset_class: str = ASSET_CLASS_GOLD
    asset_sub_class: str = ASSET_SUB_CLASS_GOLD
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

class GoldHistoryItem(BaseModel):
    symbol: str
    date: str
    nav: float
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float = 0.0
    buy_price: Optional[float] = None
    sell_price: Optional[float] = None

class GoldHistoryResponse(BaseModel):
    symbol: str
    history: List[GoldHistoryItem]
    asset_class: str = ASSET_CLASS_GOLD
    asset_sub_class: str = ASSET_SUB_CLASS_GOLD
    currency: str = CURRENCY_VND
    data_source: str = DATA_SOURCE_VN_MARKET

