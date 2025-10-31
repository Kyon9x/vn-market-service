import sys

# Check Python version requirement (3.9+)
if sys.version_info < (3, 10):
    raise RuntimeError(
        f"Python 3.10 or higher is required. Current version: {sys.version_info.major}.{sys.version_info.minor}"
    )

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from app.models import (
    FundListResponse,
    FundSearchResponse,
    FundQuoteResponse,
    FundHistoryResponse,
    StockSearchResponse,
    StockQuoteResponse,
    StockHistoryResponse,
    IndexQuoteResponse,
    IndexHistoryResponse,
    GoldSearchResponse,
    GoldQuoteResponse,
    GoldHistoryResponse,
    HealthResponse,
    SearchResponse,
    SearchResult
)
from app.clients.fund_client import FundClient
from app.clients.stock_client import StockClient
from app.clients.index_client import IndexClient
from app.clients.gold_client import GoldClient
from app.config import HOST, PORT, CORS_ORIGINS
import logging
from datetime import datetime, timedelta

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Vietnamese Market Data Service",
    description="Market data provider for Vietnamese assets (stocks, funds, indices) using vnstock",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

fund_client = FundClient()
stock_client = StockClient()
index_client = IndexClient()
gold_client = GoldClient()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="vn-market-service",
        version="2.0.0"
    )

@app.get("/funds", response_model=FundListResponse)
async def get_funds_list():
    try:
        funds = fund_client.get_funds_list()
        return FundListResponse(
            funds=[
                {
                    "symbol": f["symbol"],
                    "fund_name": f["fund_name"],
                    "asset_type": f["asset_type"],
                    "data_source": "VN_MARKET"
                }
                for f in funds
            ],
            total=len(funds)
        )
    except Exception as e:
        logger.error(f"Error in get_funds_list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/funds/search/{symbol}", response_model=FundSearchResponse)
async def search_fund(symbol: str):
    try:
        symbol = symbol.upper()
        fund_info = fund_client.search_fund_by_symbol(symbol)
        
        if not fund_info:
            raise HTTPException(status_code=404, detail=f"Fund {symbol} not found")
        
        return FundSearchResponse(**fund_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_fund: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/funds/quote/{symbol}", response_model=FundQuoteResponse)
async def get_fund_quote(symbol: str):
    try:
        symbol = symbol.upper()
        quote = fund_client.get_latest_nav(symbol)
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Quote for {symbol} not found")
        
        return FundQuoteResponse(**quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_fund_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/funds/history/{symbol}", response_model=FundHistoryResponse)
async def get_fund_history(
    symbol: str,
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format")
):
    try:
        symbol = symbol.upper()
        
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        history = fund_client.get_fund_nav_history(symbol, start_date, end_date)
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for {symbol}"
            )
        
        return FundHistoryResponse(
            symbol=symbol,
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_fund_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/search/{symbol}", response_model=StockSearchResponse)
async def search_stock(symbol: str):
    try:
        symbol = symbol.upper()
        stock_info = stock_client.search_stock(symbol)
        
        if not stock_info:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")
        
        return StockSearchResponse(**stock_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_stock: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/quote/{symbol}", response_model=StockQuoteResponse)
async def get_stock_quote(symbol: str):
    try:
        symbol = symbol.upper()
        quote = stock_client.get_latest_quote(symbol)
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Quote for {symbol} not found")
        
        return StockQuoteResponse(**quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_stock_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stocks/history/{symbol}", response_model=StockHistoryResponse)
async def get_stock_history(
    symbol: str,
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format")
):
    try:
        symbol = symbol.upper()
        
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        history = stock_client.get_stock_history(symbol, start_date, end_date)
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for {symbol}"
            )
        
        return StockHistoryResponse(
            symbol=symbol,
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_stock_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/indices/quote/{symbol}", response_model=IndexQuoteResponse)
async def get_index_quote(symbol: str):
    try:
        symbol = symbol.upper()
        quote = index_client.get_latest_quote(symbol)
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Quote for index {symbol} not found")
        
        return IndexQuoteResponse(**quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_index_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/indices/history/{symbol}", response_model=IndexHistoryResponse)
async def get_index_history(
    symbol: str,
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format")
):
    try:
        symbol = symbol.upper()
        
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        history = index_client.get_index_history(symbol, start_date, end_date)
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for index {symbol}"
            )
        
        return IndexHistoryResponse(
            symbol=symbol,
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_index_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gold/search/{symbol}", response_model=GoldSearchResponse, tags=["Gold"])
async def search_gold(symbol: str):
    """
    Search for gold asset information by provider symbol.
    
    **Supported providers:**
    - SJC: `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC`
    - BTMC: `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC`
    - MSN: `GOLD_MSN`, `GOLD`, `MSN_GOLD`
    
    **Backward compatible:** `VN_GOLD` defaults to SJC provider.
    
    Args:
        symbol: Gold provider symbol (case-insensitive)
        
    Returns:
        GoldSearchResponse with provider information
        
    Raises:
        404: Provider symbol not found
        500: API error
    """
    try:
        gold_info = gold_client.search_gold(symbol)
        if not gold_info:
            raise HTTPException(status_code=404, detail=f"Gold provider {symbol} not found")
        return GoldSearchResponse(**gold_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_gold: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gold/quote/{symbol}", response_model=GoldQuoteResponse, tags=["Gold"])
async def get_gold_quote(symbol: str):
    """
    Get the latest gold price quote from a specific provider.
    
    **Provider symbols:**
    - SJC: `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC`
    - BTMC: `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC`
    - MSN: `GOLD_MSN`, `GOLD`, `MSN_GOLD`
    
    **Response includes:**
    - SJC/BTMC: buy_price and sell_price (prices per tael in VND)
    - MSN: close price (global commodity price)
    
    Args:
        symbol: Gold provider symbol (case-insensitive)
        
    Returns:
        GoldQuoteResponse with latest price data
        
    Raises:
        404: Provider symbol not found or quote unavailable
        500: API error
    """
    try:
        quote = gold_client.get_latest_quote(symbol)
        
        if not quote:
            raise HTTPException(status_code=404, detail=f"Gold quote for {symbol} not found")
        
        return GoldQuoteResponse(**quote)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_gold_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gold/history/{symbol}", response_model=GoldHistoryResponse, tags=["Gold"])
async def get_gold_history(
    symbol: str,
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format (default: 1 year ago)"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format (default: today)")
):
    """
    Get historical gold price data for a specific provider.
    
    **Provider symbols:**
    - SJC: `VN_GOLD`, `VN_GOLD_SJC`, `SJC_GOLD`, `SJC`
    - BTMC: `VN_GOLD_BTMC`, `BTMC_GOLD`, `BTMC`
    - MSN: `GOLD_MSN`, `GOLD`, `MSN_GOLD`
    
    **Default date range:** Last 365 days (if not specified)
    
    **Historical data includes:**
    - SJC/BTMC: Daily buy_price and sell_price
    - MSN: Full OHLCV candle data (Open, High, Low, Close, Volume)
    
    Args:
        symbol: Gold provider symbol (case-insensitive)
        start_date: Start date in YYYY-MM-DD format (optional)
        end_date: End date in YYYY-MM-DD format (optional)
        
    Returns:
        GoldHistoryResponse with historical price data
        
    Raises:
        400: Invalid date format
        404: Provider symbol not found or no history available
        500: API error
    """
    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date format. Use YYYY-MM-DD"
            )
        
        history = gold_client.get_gold_history(symbol, start_date, end_date)
        
        if not history:
            raise HTTPException(
                status_code=404,
                detail=f"No history found for {symbol}"
            )
        
        return GoldHistoryResponse(
            symbol=symbol,
            history=history
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_gold_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search", response_model=SearchResponse)
async def search_assets(
    query: str = Query(..., description="Search query by symbol or name for stocks, funds, indices, or gold"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of results to return (default: 20)")
):
    try:
        query_upper = query.upper()
        query_lower = query.lower()
        results = []
        exact_matches = []
        partial_matches = []
        
        # Search stocks by symbol (exact match first)
        try:
            stock_info = stock_client.search_stock(query_upper)
            if stock_info:
                exact_matches.append(SearchResult(
                    symbol=stock_info["symbol"],
                    name=stock_info["company_name"],
                    asset_type="STOCK",
                    exchange=stock_info.get("exchange", "HOSE"),
                    currency="VND",
                    data_source="VN_MARKET"
                ))
        except Exception as e:
            logger.debug(f"Error searching stock by symbol: {e}")
        
        # Search stocks by name (partial match)
        try:
            stocks = stock_client.search_stocks_by_name(query_lower, limit=10)
            for stock in stocks:
                partial_matches.append(SearchResult(
                    symbol=stock["symbol"],
                    name=stock["company_name"],
                    asset_type="STOCK",
                    exchange=stock.get("exchange", "HOSE"),
                    currency="VND",
                    data_source="VN_MARKET"
                ))
        except Exception as e:
            logger.debug(f"Error searching stocks by name: {e}")
        
        # Search funds by symbol and name
        try:
            funds = fund_client.search_funds_by_name(query_lower, limit=10)
            for fund in funds:
                # Check if exact symbol match
                if fund["symbol"].upper() == query_upper:
                    exact_matches.append(SearchResult(
                        symbol=fund["symbol"],
                        name=fund["fund_name"],
                        asset_type="FUND",
                        exchange="VN",
                        currency="VND",
                        data_source="VN_MARKET"
                    ))
                else:
                    partial_matches.append(SearchResult(
                        symbol=fund["symbol"],
                        name=fund["fund_name"],
                        asset_type="FUND",
                        exchange="VN",
                        currency="VND",
                        data_source="VN_MARKET"
                    ))
        except Exception as e:
            logger.debug(f"Error searching funds: {e}")
        
        # Search indices
        indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
        for idx in indices:
            if query_upper == idx:
                exact_matches.append(SearchResult(
                    symbol=idx,
                    name=f"Vietnam {idx} Index",
                    asset_type="INDEX",
                    exchange="HOSE" if idx.startswith("VN") else "HNX",
                    currency="VND",
                    data_source="VN_MARKET"
                ))
            elif query_upper in idx or idx in query_upper:
                partial_matches.append(SearchResult(
                    symbol=idx,
                    name=f"Vietnam {idx} Index",
                    asset_type="INDEX",
                    exchange="HOSE" if idx.startswith("VN") else "HNX",
                    currency="VND",
                    data_source="VN_MARKET"
                ))
        
        # Search gold - check for gold-related queries
        gold_patterns = ["gold", "vn gold", "vn_gold", "vngold", "sjc", "btmc", "msn"]
        query_normalized = query_lower.replace("_", " ").replace("-", " ").strip()
        is_gold_query = query_normalized == "gold" or any(pattern in query_normalized for pattern in gold_patterns)
        
        if is_gold_query:
            try:
                gold_providers = gold_client.get_all_gold_providers()
                for provider in gold_providers:
                    partial_matches.append(SearchResult(
                        symbol=provider["symbol"],
                        name=provider["name"],
                        asset_type=provider["asset_type"],
                        exchange=provider["exchange"],
                        currency=provider["currency"],
                        data_source="VN_MARKET"
                    ))
            except Exception as e:
                logger.debug(f"Error searching gold providers: {e}")
        else:
            # Try to match specific gold symbol
            try:
                gold_info = gold_client.search_gold(query_upper)
                if gold_info:
                    exact_matches.append(SearchResult(
                        symbol=gold_info["symbol"],
                        name=gold_info["name"],
                        asset_type=gold_info["asset_type"],
                        exchange=gold_info["exchange"],
                        currency=gold_info["currency"],
                        data_source="VN_MARKET"
                    ))
            except Exception as e:
                logger.debug(f"Error searching gold by symbol: {e}")
        
        # Combine results: exact matches first, then partial matches
        results = exact_matches + partial_matches
        
        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for result in results:
            key = (result.symbol, result.asset_type)
            if key not in seen:
                seen.add(key)
                unique_results.append(result)
        
        # Limit results
        final_results = unique_results[:limit]
        
        return SearchResponse(results=final_results, total=len(final_results))
    except Exception as e:
        logger.error(f"Error in search_assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{symbol}")
async def get_history(
    symbol: str,
    start_date: str = Query(None, description="Start date in YYYY-MM-DD format"),
    end_date: str = Query(None, description="End date in YYYY-MM-DD format")
):
    try:
        symbol = symbol.upper()
        
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        # Handle gold symbols
        try:
            history = gold_client.get_gold_history(symbol, start_date, end_date)
            
            if history:
                return {
                    "symbol": symbol,
                    "history": history,
                    "currency": "VND",
                    "data_source": "VN_MARKET"
                }
        except:
            pass
        
        indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
        if symbol in indices:
            result = await get_index_history(symbol, start_date, end_date)
            # Ensure response includes all required fields
            return {
                "symbol": result.symbol,
                "history": [item.dict() for item in result.history],
                "currency": result.currency,
                "data_source": result.data_source
            }
        
        fund_symbols = [f["symbol"] for f in fund_client.get_funds_list()]
        if symbol in fund_symbols:
            result = await get_fund_history(symbol, start_date, end_date)
            return {
                "symbol": result.symbol,
                "history": [item.dict() for item in result.history],
                "currency": result.currency,
                "data_source": result.data_source
            }
        
        result = await get_stock_history(symbol, start_date, end_date)
        return {
            "symbol": result.symbol,
            "history": [item.dict() for item in result.history],
            "currency": result.currency,
            "data_source": result.data_source
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_history: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/quote/{symbol}")
async def get_quote(symbol: str):
    """
    Universal quote endpoint - auto-detects asset type and returns latest price data.
    
    Supports all asset types:
    - Stocks (e.g., VNM, FPT, MWG)
    - Funds (e.g., VESAF, VOF, EVF)
    - Indices (e.g., VNINDEX, VN30, HNX)
    - Gold (e.g., VN_GOLD, SJC, BTMC, GOLD_MSN)
    
    Returns:
        Unified quote response with asset_type field indicating the detected asset type.
        Response includes dynamic fields based on asset type:
        - Stocks/Funds/Indices: close, date
        - Funds: nav (net asset value)
        - Gold: buy_price, sell_price (for SJC/BTMC), close (for MSN)
    """
    try:
        symbol = symbol.upper()
        
        # Try gold first
        try:
            quote = gold_client.get_latest_quote(symbol)
            if quote:
                return {
                    **quote,
                    "asset_type": "GOLD"
                }
        except:
            pass
        
        # Try indices
        indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
        if symbol in indices:
            result = await get_index_quote(symbol)
            return {
                **result.dict(),
                "asset_type": "INDEX"
            }
        
        # Try funds
        fund_symbols = [f["symbol"] for f in fund_client.get_funds_list()]
        if symbol in fund_symbols:
            result = await get_fund_quote(symbol)
            return {
                **result.dict(),
                "asset_type": "FUND"
            }
        
        # Try stocks (default)
        result = await get_stock_quote(symbol)
        return {
            **result.dict(),
            "asset_type": "STOCK"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_quote: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search/{symbol}", response_model=SearchResult)
async def search_asset(symbol: str):
    logger.info(f"search_asset called with symbol: {symbol}")
    try:
        symbol_upper = symbol.upper()
        logger.info(f"Processing symbol: {symbol_upper}")
        
        # Handle gold symbols
        try:
            gold_info = gold_client.search_gold(symbol)
            if gold_info:
                return SearchResult(
                    symbol=gold_info["symbol"],
                    name=gold_info["name"],
                    asset_type=gold_info["asset_type"],
                    exchange=gold_info["exchange"],
                    currency=gold_info["currency"],
                    data_source="VN_MARKET"
                )
        except Exception as e:
            logger.debug(f"Error searching gold: {e}")
            pass
        
        indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
        if symbol_upper in indices:
            return SearchResult(
                symbol=symbol_upper,
                name=f"Vietnam {symbol_upper} Index",
                asset_type="INDEX",
                exchange="HOSE" if symbol_upper.startswith("VN") else "HNX",
                currency="VND",
                data_source="VN_MARKET"
            )
        
        fund_info = fund_client.search_fund_by_symbol(symbol_upper)
        if fund_info:
            return SearchResult(
                symbol=fund_info["symbol"],
                name=fund_info["fund_name"],
                asset_type="FUND",
                exchange="VN",
                currency="VND",
                data_source="VN_MARKET"
            )
        
        stock_info = stock_client.search_stock(symbol_upper)
        if stock_info:
            logger.info(f"Found stock info for {symbol_upper}: {stock_info}")
            result = SearchResult(
                symbol=stock_info["symbol"],
                name=stock_info["company_name"],
                asset_type="STOCK",
                exchange=stock_info.get("exchange", "HOSE"),
                currency="VND",
                data_source="VN_MARKET"
            )
            logger.info(f"Returning SearchResult: {result}")
            # Log the actual dictionary being returned
            result_dict = result.dict()
            logger.info(f"Result dict: {result_dict}")
            return result_dict

# Intentional syntax error to test if this file is being used
# if True:
#     pass
        
        raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Vietnamese Market Data Service on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
