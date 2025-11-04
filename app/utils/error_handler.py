"""
Common error handling utilities and decorators to eliminate repeated error handling patterns.
"""

import logging
import functools
from typing import Callable, Any, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def handle_api_errors(
    status_code: int = 500,
    log_message: Optional[str] = None,
    reraise_httpexception: bool = True
) -> Callable:
    """
    Decorator to handle common API errors and convert them to HTTPExceptions.

    Args:
        status_code: HTTP status code to return on error
        log_message: Custom log message (optional)
        reraise_httpexception: Whether to re-raise HTTPExceptions as-is

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                if reraise_httpexception:
                    raise
                else:
                    raise HTTPException(status_code=status_code, detail="API error")
            except Exception as e:
                error_msg = log_message or f"Error in {func.__name__}: {str(e)}"
                logger.error(error_msg)
                raise HTTPException(status_code=status_code, detail=str(e))
        return wrapper
    return decorator


def handle_client_errors(
    service_name: str,
    status_code: int = 503,
    unavailable_message: Optional[str] = None
) -> Callable:
    """
    Decorator specifically for client-related errors (service unavailable).

    Args:
        service_name: Name of the service/client for error messages
        status_code: HTTP status code (default 503 for service unavailable)
        unavailable_message: Custom unavailable message

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Check if client is available (first arg is typically the client instance)
                if args and hasattr(args[0], '__class__') and args[0] is None:
                    message = unavailable_message or f"{service_name} service is temporarily unavailable"
                    raise HTTPException(status_code=status_code, detail=message)

                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error in {service_name} {func.__name__}: {str(e)}")
                message = unavailable_message or f"{service_name} service error: {str(e)}"
                raise HTTPException(status_code=status_code, detail=message)
        return wrapper
    return decorator


def validate_client_available(client, service_name: str, detail: Optional[str] = None):
    """
    Validate that a client is available and raise HTTPException if not.

    Args:
        client: The client instance to check
        service_name: Name of the service for error message
        detail: Custom error detail message

    Raises:
        HTTPException: If client is not available
    """
    if client is None:
        detail = detail or f"{service_name} service is temporarily unavailable. API timeout or connection issue detected."
        raise HTTPException(status_code=503, detail=detail)
