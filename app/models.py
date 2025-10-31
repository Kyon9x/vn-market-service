from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class AssetClass(str, Enum):
    COMMODITY = "Commodity"
    EQUITY = "Equity"
    INVESTMENT_FUND = "Investment Fund"
    INDEX = "Index"
    OTHER = "Other"


class AssetSubClass(str, Enum):
    PRECIOUS_METAL = "Precious Metal"
    STOCK = "Stock"
    MUTUAL_FUND = "Mutual Fund"
    MARKET_INDEX = "Market Index"
    OTHER = "Other"

class FundBasicInfo(BaseModel):
    symbol: str
    fund_name: str
    asset_type: str
    asset_class: str = "Investment Fund"
    asset_sub_class: str = "Mutual Fund"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Investment Fund"
    asset_sub_class: str = "Mutual Fund"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Investment Fund"
    asset_sub_class: str = "Mutual Fund"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Investment Fund"
    asset_sub_class: str = "Mutual Fund"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

class StockSearchResponse(BaseModel):
    symbol: str
    company_name: str
    exchange: str
    industry: Optional[str] = None
    company_type: Optional[str] = None
    asset_class: str = "Equity"
    asset_sub_class: str = "Stock"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

class StockQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float
    date: str
    asset_class: str = "Equity"
    asset_sub_class: str = "Stock"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Equity"
    asset_sub_class: str = "Stock"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

class IndexSearchResponse(BaseModel):
    symbol: str
    name: str
    asset_type: str = "INDEX"
    asset_class: str = "Index"
    asset_sub_class: str = "Market Index"
    exchange: str
    currency: str = "VND"
    data_source: str = "VN_MARKET"


class IndexQuoteResponse(BaseModel):
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adjclose: float
    volume: float
    date: str
    asset_class: str = "Index"
    asset_sub_class: str = "Market Index"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Index"
    asset_sub_class: str = "Market Index"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    currency: str = "VND"
    data_source: str = "VN_MARKET"

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int

class GoldSearchResponse(BaseModel):
    symbol: str
    name: str
    provider: str
    provider_name: str
    asset_type: str
    asset_class: str = "Commodity"
    asset_sub_class: str = "Precious Metal"
    exchange: str
    currency: str = "VND"
    data_source: str = "VN_MARKET"

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
    asset_class: str = "Commodity"
    asset_sub_class: str = "Precious Metal"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

class GoldHistoryItem(BaseModel):
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
    asset_class: str = "Commodity"
    asset_sub_class: str = "Precious Metal"
    currency: str = "VND"
    data_source: str = "VN_MARKET"

