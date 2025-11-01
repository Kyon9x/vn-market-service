import asyncio
from typing import List, Dict, Any, Optional, Callable, Awaitable
import logging
from functools import wraps

logger = logging.getLogger(__name__)

async def parallel_search(
    search_functions: List[Callable[[], Awaitable[List[Dict]]]],
    timeout: float = 5.0
) -> List[Dict]:
    """
    Execute multiple search functions in parallel and combine results.
    
    Args:
        search_functions: List of async functions that return search results
        timeout: Maximum time to wait for all searches to complete
        
    Returns:
        Combined list of search results from all functions
    """
    try:
        # Execute all searches concurrently with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    *[func() for func in search_functions],
                    return_exceptions=True
                ),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Parallel search timed out after {timeout} seconds")
            return []
        
        combined_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"Search function {i} failed: {result}")
                continue
            if isinstance(result, list):
                combined_results.extend(result)
        
        return combined_results
    except Exception as e:
        logger.error(f"Error in parallel search: {e}")
        return []

def async_cache_result(cache_key_func: Callable, cache, ttl: int = 300):
    """
    Decorator to cache async function results.
    
    Args:
        cache_key_func: Function to generate cache key from arguments
        cache: Cache instance to use
        ttl: Time to live for cached results
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = cache_key_func(*args, **kwargs)
            
            # Try to get from cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for key: {cache_key}")
                return cached_result
            
            # Execute function and cache result
            try:
                result = await func(*args, **kwargs)
                cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for key: {cache_key}")
                return result
            except Exception as e:
                logger.error(f"Error executing {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator

def batch_requests(items: List[Any], batch_size: int = 10):
    """
    Split items into batches for processing.
    
    Args:
        items: List of items to batch
        batch_size: Size of each batch
        
    Yields:
        Batches of items
    """
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

async def execute_with_fallback(
    primary_func: Callable[[], Awaitable[Any]],
    fallback_func: Callable[[], Awaitable[Any]],
    timeout: float = 3.0
) -> Any:
    """
    Execute primary function with timeout, fallback to secondary function.
    
    Args:
        primary_func: Primary async function to execute
        fallback_func: Fallback async function if primary fails/times out
        timeout: Timeout for primary function
        
    Returns:
        Result from primary or fallback function
    """
    try:
        # Try primary function with timeout
        result = await asyncio.wait_for(primary_func(), timeout=timeout)
        return result
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Primary function failed: {e}, using fallback")
        try:
            return await fallback_func()
        except Exception as fallback_error:
            logger.error(f"Fallback function also failed: {fallback_error}")
            raise

class SearchOptimizer:
    """Optimizes search operations with caching and parallel execution."""
    
    def __init__(self, cache_manager, memory_cache):
        self.cache_manager = cache_manager
        self.memory_cache = memory_cache
    
    async def optimized_search(
        self,
        query: str,
        search_functions: Dict[str, Callable[[], Awaitable[List[Dict]]]],
        limit: int = 20,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Perform optimized search with caching and parallel execution.
        
        Args:
            query: Search query
            search_functions: Dict of asset_type -> search_function
            limit: Maximum number of results
            use_cache: Whether to use cached results
            
        Returns:
            Combined and ranked search results
        """
        # Check cache first
        if use_cache:
            cached_results = self.memory_cache.get_search_results(query)
            if cached_results:
                logger.debug(f"Using cached search results for '{query}'")
                return cached_results[:limit]
        
        # Check persistent cache
        if use_cache:
            persistent_results = self.cache_manager.get_search_results(query)
            if persistent_results:
                logger.debug(f"Using persistent cached search results for '{query}'")
                # Also store in memory cache for faster access
                self.memory_cache.set_search_results(query, persistent_results)
                return persistent_results[:limit]
        
        # Execute searches in parallel
        search_tasks = list(search_functions.values())
        combined_results = await parallel_search(search_tasks)
        
        # Remove duplicates and rank results
        unique_results = self._deduplicate_and_rank(combined_results, query)
        
        # Limit results
        final_results = unique_results[:limit]
        
        # Cache results
        if use_cache and final_results:
            self.memory_cache.set_search_results(query, final_results)
            self.cache_manager.set_search_results(query, final_results)
        
        return final_results
    
    def _deduplicate_and_rank(self, results: List[Dict], query: str) -> List[Dict]:
        """
        Remove duplicate results and rank by relevance.
        
        Args:
            results: List of search results
            query: Original search query
            
        Returns:
            Deduplicated and ranked results
        """
        query_upper = query.upper()
        seen = set()
        unique_results = []
        
        for result in results:
            # Create unique key
            key = (result.get('symbol', ''), result.get('asset_type', ''))
            if key in seen:
                continue
            
            seen.add(key)
            
            # Calculate relevance score
            score = self._calculate_relevance_score(result, query_upper)
            result['_relevance_score'] = score
            unique_results.append(result)
        
        # Sort by relevance score (descending)
        unique_results.sort(key=lambda x: x.get('_relevance_score', 0), reverse=True)
        
        # Remove internal score field
        for result in unique_results:
            result.pop('_relevance_score', None)
        
        return unique_results
    
    def _calculate_relevance_score(self, result: Dict, query: str) -> float:
        """
        Calculate relevance score for a search result.
        
        Args:
            result: Search result dictionary
            query: Upper-case search query
            
        Returns:
            Relevance score (higher is more relevant)
        """
        score = 0.0
        symbol = result.get('symbol', '').upper()
        name = result.get('name', '').upper()
        
        # Exact symbol match gets highest score
        if symbol == query:
            score += 100
        # Symbol starts with query
        elif symbol.startswith(query):
            score += 80
        # Query contains symbol or symbol contains query
        elif query in symbol or symbol in query:
            score += 60
        
        # Name-based scoring
        if query in name:
            score += 40
        elif name.startswith(query):
            score += 30
        
        # Asset type preferences (can be customized)
        asset_type = result.get('asset_type', '').upper()
        if asset_type == 'STOCK':
            score += 10  # Prefer stocks slightly
        elif asset_type == 'FUND':
            score += 5
        
        return score

# Global search optimizer instance
_search_optimizer = None

def get_search_optimizer(cache_manager, memory_cache) -> SearchOptimizer:
    """Get or create global search optimizer instance."""
    global _search_optimizer
    if _search_optimizer is None:
        _search_optimizer = SearchOptimizer(cache_manager, memory_cache)
    return _search_optimizer