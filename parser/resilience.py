"""Resilience utilities: retry decorator, exceptions."""

import asyncio
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class NoHealthyProxyError(Exception):
    """Raised when all proxies are dead."""


def retry_async(
    max_retries: int = 3,
    base_delay: float = 2,
    max_delay: float = 60,
    exceptions: tuple = (Exception,),
):
    """Decorator for async functions with exponential backoff retry.

    Args:
        max_retries: maximum number of attempts
        base_delay: initial delay in seconds
        max_delay: cap on delay
        exceptions: tuple of exception types to catch
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        "%s attempt %d/%d failed: %s. Retry in %.1fs",
                        func.__name__, attempt + 1, max_retries, e, delay,
                    )
                    await asyncio.sleep(delay)
        return wrapper
    return decorator
