import logging
import time
from functools import wraps
from typing import Any, Callable, Optional, Dict

logger = logging.getLogger(__name__)


def log_provider_call(
    provider_name: str = "vnstock",
    metadata_fields: Optional[Dict[str, Callable]] = None
):
    """
    Decorator to log external provider library calls.
    
    Logs calls to external providers (e.g., vnstock) with [provider=call] tag
    for easy filtering and monitoring.
    
    Args:
        provider_name: Name of the provider library (default: "vnstock")
        metadata_fields: Dict mapping field names to callables that extract metadata from result.
                        Example: {"symbol": lambda result: result.get("symbol")}
    
    Example:
        @log_provider_call(provider_name="vnstock", metadata_fields={"symbol": lambda r: r.get("symbol")})
        def get_quote(self, symbol):
            return {"symbol": "VNM", "price": 100}
    """
    metadata_fields = metadata_fields or {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            method_name = f"{func.__module__.split('.')[-1]}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                # Extract metadata from result if available
                metadata_str = ""
                if metadata_fields and result is not None:
                    metadata_parts = []
                    for field_name, extractor in metadata_fields.items():
                        try:
                            value = extractor(result)
                            if value is not None:
                                metadata_parts.append(f"{field_name}={value}")
                        except Exception:
                            pass
                    if metadata_parts:
                        metadata_str = " " + " ".join(metadata_parts)
                
                logger.info(
                    f"[provider=call] [provider_name={provider_name}] method={method_name} "
                    f"status=success duration={duration_ms}ms{metadata_str}"
                )
                return result
            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.warning(
                    f"[provider=call] [provider_name={provider_name}] method={method_name} "
                    f"status=error duration={duration_ms}ms error_type={type(e).__name__}: {str(e)}"
                )
                raise
        
        return wrapper
    return decorator
