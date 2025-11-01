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
from app.cache.cache_manager import CacheManager
from app.cache.memory_cache import quote_cache, search_cache, cleanup_expired_caches, get_cache_stats
from app.cache.search_optimizer import get_search_optimizer
from app.cache.background_manager import start_cache_background_tasks, stop_cache_background_tasks
from app.cache.data_seeder import get_data_seeder
import logging
from datetime import datetime, timedelta
import asyncio

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_asset_classification(asset_type: str, asset_class: str, asset_sub_class: str) -> bool:
    """
    Validate that the asset classification is correct based on the asset type.
    
    Args:
        asset_type: The type of asset (STOCK, FUND, INDEX, GOLD, etc.)
        asset_class: The asset class
        asset_sub_class: The asset sub-class
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    asset_type = asset_type.upper()
    
    if asset_type == "STOCK":
        return asset_class == "Equity" and asset_sub_class == "Stock"
    elif asset_type == "FUND":
        return asset_class == "Investment Fund" and asset_sub_class == "Mutual Fund"
    elif asset_type == "INDEX":
        return asset_class == "Index" and asset_sub_class == "Market Index"
    elif asset_type == "GOLD":
        return asset_class == "Commodity" and asset_sub_class == "Precious Metal"
    else:
        # For other asset types, we'll allow any classification
        return True


def validate_response_fields(response: dict, expected_asset_type: str) -> bool:
    """
    Validate that the response contains all required fields with correct values.
    
    Args:
        response: The response dictionary to validate
        expected_asset_type: The expected asset type
        
    Returns:
        bool: True if validation passes, False otherwise
    """
    required_fields = ["asset_class", "asset_sub_class", "currency", "data_source"]
    
    # Check that all required fields are present
    for field in required_fields:
        if field not in response:
            logger.warning(f"Missing required field: {field}")
            return False
    
    # Validate asset classification
    if not validate_asset_classification(
        expected_asset_type, 
        response.get("asset_class", ""), 
        response.get("asset_sub_class", "")
    ):
        logger.warning(f"Invalid asset classification for {expected_asset_type}")
        return False
    
    # Validate currency (should be VND for most assets, USD for MSN gold)
    currency = response.get("currency")
    if currency not in ["VND", "USD"]:
        logger.warning(f"Invalid currency: {currency}")
        return False
    
    # Validate data_source
    if response.get("data_source") != "VN_MARKET":
        logger.warning(f"Invalid data_source: {response.get('data_source')}")
        return False
    
    return True

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

# Initialize cache manager and clients
cache_manager = CacheManager()
fund_client = FundClient(cache_manager, quote_cache)
stock_client = StockClient(cache_manager, quote_cache)
index_client = IndexClient(cache_manager, quote_cache)
gold_client = GoldClient(cache_manager, quote_cache)
search_optimizer = get_search_optimizer(cache_manager, search_cache)
data_seeder = get_data_seeder(cache_manager, stock_client, fund_client, gold_client)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        status="healthy",
        service="vn-market-service",
        version="2.0.0"
    )

@app.get("/cache/stats")
async def get_cache_statistics():
    """Get cache statistics for monitoring."""
    try:
        memory_stats = get_cache_stats()
        persistent_stats = cache_manager.get_stats()
        
        return {
            "memory_cache": memory_stats,
            "persistent_cache": persistent_stats,
            "cache_enabled": True
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/cleanup")
async def cleanup_cache():
    """Manually trigger cache cleanup."""
    try:
        # Clean memory caches
        cleanup_expired_caches()
        
        # Clean persistent cache
        cache_manager.cleanup_expired()
        
        return {"message": "Cache cleanup completed successfully"}
    except Exception as e:
        logger.error(f"Error during cache cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/seed")
async def seed_cache(force_refresh: bool = False):
    """Manually trigger cache seeding with all available assets."""
    try:
        logger.info(f"Manual cache seeding triggered (force_refresh={force_refresh})")
        counts = await data_seeder.seed_all_assets(force_refresh=force_refresh)
        
        # Note: Not refreshing popular asset quotes to avoid delays
        # Quotes will be fetched on-demand when accessed
        
        return {
            "message": "Cache seeding completed successfully",
            "counts": counts,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error during cache seeding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/seed/progress")
async def get_seeding_progress():
    """Get current seeding progress."""
    try:
        progress = data_seeder.get_seeding_progress()
        return progress
    except Exception as e:
        logger.error(f"Error getting seeding progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/funds", response_model=FundListResponse)
async def get_funds_list():
    try:
        funds = fund_client.get_funds_list()
        validated_funds = []
        for f in funds:
            fund_dict = {
                "symbol": f["symbol"],
                "fund_name": f["fund_name"],
                "asset_type": f["asset_type"],
                "asset_class": "Investment Fund",
                "asset_sub_class": "Mutual Fund",
                "data_source": "VN_MARKET"
            }
            # Validate the response
            if not validate_response_fields(fund_dict, "FUND"):
                logger.warning(f"Validation failed for fund list item {f['symbol']}")
            validated_funds.append(fund_dict)
        
        return FundListResponse(
            funds=validated_funds,
            total=len(validated_funds)
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
    - SJC: `VN.GOLD`, `VN.GOLD.SJC`, `SJC.GOLD`, 
    - BTMC: `VN.GOLD.BTMC`, `BTMC.GOLD`
    - MSN: `GOLD.MSN`, `MSN.GOLD`
    
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
    - SJC: `VN.GOLD`, `VN.GOLD.SJC`, `SJC.GOLD`, 
    - BTMC: `VN.GOLD.BTMC`, `BTMC.GOLD`
    - MSN: `GOLD.MSN`, `MSN.GOLD`
    
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
        # Define async search functions for parallel execution
        async def search_stocks():
            try:
                query_upper = query.upper()
                query_lower = query.lower()
                results = []
                
                # Search by symbol (exact match)
                stock_info = stock_client.search_stock(query_upper)
                if stock_info:
                    results.append({
                        "symbol": stock_info["symbol"],
                        "name": stock_info["company_name"],
                        "asset_type": "STOCK",
                        "asset_class": "Equity",
                        "asset_sub_class": "Stock",
                        "exchange": stock_info.get("exchange", ""),
                        "currency": "VND",
                        "data_source": "VN_MARKET"
                    })
                
                # Search by name (partial match)
                stocks = stock_client.search_stocks_by_name(query_lower, limit=10)
                for stock in stocks:
                    # Avoid duplicates
                    if not any(r["symbol"] == stock["symbol"] for r in results):
                        results.append({
                            "symbol": stock["symbol"],
                            "name": stock["company_name"],
                            "asset_type": "STOCK",
                            "asset_class": "Equity",
                            "asset_sub_class": "Stock",
                            "exchange": stock.get("exchange", ""),
                            "currency": "VND",
                            "data_source": "VN_MARKET"
                        })
                
                return results
            except Exception as e:
                logger.debug(f"Error searching stocks: {e}")
                return []
        
        async def search_funds():
            try:
                query_lower = query.lower()
                query_upper = query.upper()
                results = []
                
                funds = fund_client.search_funds_by_name(query_lower, limit=10)
                for fund in funds:
                    results.append({
                        "symbol": fund["symbol"],
                        "name": fund["fund_name"],
                        "asset_type": "FUND",
                        "asset_class": "Investment Fund",
                        "asset_sub_class": "Mutual Fund",
                        "exchange": "VN",
                        "currency": "VND",
                        "data_source": "VN_MARKET"
                    })
                
                return results
            except Exception as e:
                logger.debug(f"Error searching funds: {e}")
                return []
        
        async def search_indices():
            try:
                query_upper = query.upper()
                results = []
                
                indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
                for idx in indices:
                    if query_upper == idx or query_upper in idx or idx in query_upper:
                        results.append({
                            "symbol": idx,
                            "name": f"Vietnam {idx} Index",
                            "asset_type": "INDEX",
                            "asset_class": "Index",
                            "asset_sub_class": "Market Index",
                            "exchange": "HOSE" if idx.startswith("VN") else "HNX",
                            "currency": "VND",
                            "data_source": "VN_MARKET"
                        })
                
                return results
            except Exception as e:
                logger.debug(f"Error searching indices: {e}")
                return []
        
        async def search_gold():
            try:
                query_upper = query.upper()
                query_lower = query.lower()
                results = []
                
                # Check for gold-related queries
                gold_patterns = ["gold", "vn gold", "vn_gold", "vngold", "sjc", "btmc", "msn"]
                query_normalized = query_lower.replace("_", " ").replace("-", " ").strip()
                is_gold_query = query_normalized == "gold" or any(pattern in query_normalized for pattern in gold_patterns)
                
                if is_gold_query:
                    gold_providers = gold_client.get_all_gold_providers()
                    for provider in gold_providers:
                        results.append({
                            "symbol": provider["symbol"],
                            "name": provider["name"],
                            "asset_type": provider["asset_type"],
                            "asset_class": "Commodity",
                            "asset_sub_class": "Precious Metal",
                            "exchange": provider["exchange"],
                            "currency": provider["currency"],
                            "data_source": "VN_MARKET"
                        })
                else:
                    # Try to match specific gold symbol
                    gold_info = gold_client.search_gold(query_upper)
                    if gold_info:
                        results.append({
                            "symbol": gold_info["symbol"],
                            "name": gold_info["name"],
                            "asset_type": gold_info["asset_type"],
                            "asset_class": "Commodity",
                            "asset_sub_class": "Precious Metal",
                            "exchange": gold_info["exchange"],
                            "currency": gold_info["currency"],
                            "data_source": "VN_MARKET"
                        })
                
                return results
            except Exception as e:
                logger.debug(f"Error searching gold: {e}")
                return []
        
        # Use optimized search with caching and parallel execution
        search_functions = {
            "stocks": search_stocks,
            "funds": search_funds,
            "indices": search_indices,
            "gold": search_gold
        }
        
        # Execute optimized search
        combined_results = await search_optimizer.optimized_search(
            query=query,
            search_functions=search_functions,
            limit=limit,
            use_cache=True
        )
        
        # Convert to SearchResult objects
        search_results = [
            SearchResult(
                symbol=result["symbol"],
                name=result["name"],
                asset_type=result["asset_type"],
                asset_class=result["asset_class"],
                asset_sub_class=result["asset_sub_class"],
                exchange=result["exchange"],
                currency=result["currency"],
                data_source=result["data_source"]
            )
            for result in combined_results[:limit]
        ]
        
        return SearchResponse(results=search_results, total=len(search_results))
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
                    "asset_class": "Commodity",
                    "asset_sub_class": "Precious Metal",
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
                "asset_class": "Index",
                "asset_sub_class": "Market Index",
                "currency": result.currency,
                "data_source": result.data_source
            }
        
        fund_symbols = [f["symbol"] for f in fund_client.get_funds_list()]
        if symbol in fund_symbols:
            result = await get_fund_history(symbol, start_date, end_date)
            return {
                "symbol": result.symbol,
                "history": [item.dict() for item in result.history],
                "asset_class": "Investment Fund",
                "asset_sub_class": "Mutual Fund",
                "currency": result.currency,
                "data_source": result.data_source
            }
        
        result = await get_stock_history(symbol, start_date, end_date)
        return {
            "symbol": result.symbol,
            "history": [item.dict() for item in result.history],
            "asset_class": "Equity",
            "asset_sub_class": "Stock",
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
    - Gold (e.g., VN.GOLD, SJC.GOLD, BTMC.GOLD, MSN.GOLD)
    
    Returns:
        Unified quote response with standardized OHLCV data structure:
        - open, high, low, close, adjclose, volume: Price data
        - nav: Net asset value (for funds)
        - buy_price, sell_price: Gold prices (for SJC/BTMC gold)
        - asset_type: Detected asset type
        - asset_class, asset_sub_class: Asset classification
        - currency: Pricing currency
        - data_source: Data source identifier
    """
    try:
        symbol = symbol.upper()
        
        # Try gold first
        try:
            quote = gold_client.get_latest_quote(symbol)
            if quote:
                return {
                    **quote,
                    "asset_type": "GOLD",
                    "asset_class": "Commodity",
                    "asset_sub_class": "Precious Metal"
                }
        except:
            pass
        
        # Try indices
        indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
        if symbol in indices:
            result = await get_index_quote(symbol)
            return {
                **result.dict(),
                "asset_type": "INDEX",
                "asset_class": "Index",
                "asset_sub_class": "Market Index"
            }
        
        # Try funds
        fund_symbols = [f["symbol"] for f in fund_client.get_funds_list()]
        if symbol in fund_symbols:
            result = await get_fund_quote(symbol)
            return {
                **result.dict(),
                "asset_type": "FUND",
                "asset_class": "Investment Fund",
                "asset_sub_class": "Mutual Fund"
            }
        
        # Try stocks (default)
        result = await get_stock_quote(symbol)
        return {
            **result.dict(),
            "asset_type": "STOCK",
            "asset_class": "Equity",
            "asset_sub_class": "Stock"
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
        
        result_dict = None
        asset_type = None
        
        # Handle gold symbols
        try:
            gold_info = gold_client.search_gold(symbol)
            if gold_info:
                result_dict = {
                    "symbol": gold_info["symbol"],
                    "name": gold_info["name"],
                    "asset_type": gold_info["asset_type"],
                    "asset_class": "Commodity",
                    "asset_sub_class": "Precious Metal",
                    "exchange": gold_info["exchange"],
                    "currency": gold_info["currency"],
                    "data_source": "VN_MARKET"
                }
                asset_type = "GOLD"
        except Exception as e:
            logger.debug(f"Error searching gold: {e}")
            pass
        
        if result_dict is None:
            indices = ["VNINDEX", "VN30", "HNX", "HNX30", "UPCOM"]
            if symbol_upper in indices:
                result_dict = {
                    "symbol": symbol_upper,
                    "name": f"Vietnam {symbol_upper} Index",
                    "asset_type": "INDEX",
                    "asset_class": "Index",
                    "asset_sub_class": "Market Index",
                    "exchange": "HOSE" if symbol_upper.startswith("VN") else "HNX",
                    "currency": "VND",
                    "data_source": "VN_MARKET"
                }
                asset_type = "INDEX"
        
        if result_dict is None:
            fund_info = fund_client.search_fund_by_symbol(symbol_upper)
            if fund_info:
                result_dict = {
                    "symbol": fund_info["symbol"],
                    "name": fund_info["fund_name"],
                    "asset_type": "FUND",
                    "asset_class": "Investment Fund",
                    "asset_sub_class": "Mutual Fund",
                    "exchange": "VN",
                    "currency": "VND",
                    "data_source": "VN_MARKET"
                }
                asset_type = "FUND"
        
        if result_dict is None:
            stock_info = stock_client.search_stock(symbol_upper)
            if stock_info:
                logger.info(f"Found stock info for {symbol_upper}: {stock_info}")
                result_dict = {
                    "symbol": stock_info["symbol"],
                    "name": stock_info["company_name"],
                    "asset_type": "STOCK",
                    "asset_class": "Equity",
                    "asset_sub_class": "Stock",
                    "exchange": stock_info.get("exchange", ""),
                    "currency": "VND",
                    "data_source": "VN_MARKET"
                }
                asset_type = "STOCK"
        
        if result_dict is None:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        
        # Validate the response
        if not validate_response_fields(result_dict, asset_type):
            logger.warning(f"Validation failed for asset {symbol}")
        
        logger.info(f"Returning SearchResult: {result_dict}")
        return result_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search_asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup."""
    try:
        # First, seed the cache with all available assets
        logger.info("Starting cache seeding on startup...")
        counts = await data_seeder.seed_all_assets(force_refresh=False)
        logger.info(f"Initial seeding completed: {counts}")
        
        # Note: Not refreshing popular asset quotes on startup to avoid delays
        # Quotes will be fetched on-demand when accessed
        
        # Start background cache tasks
        await start_cache_background_tasks(cache_manager, stock_client, fund_client, gold_client)
        logger.info("Background cache tasks started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Continue startup even if seeding fails

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background tasks on shutdown."""
    try:
        await stop_cache_background_tasks()
        logger.info("Background cache tasks stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping background tasks: {e}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Vietnamese Market Data Service on {HOST}:{PORT}")
    uvicorn.run(app, host=HOST, port=PORT)
