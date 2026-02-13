"""Network retry with exponential backoff for Gmail API calls."""

from __future__ import annotations

import logging
import socket
import time
from typing import Any, Callable, TypeVar

from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient error types that should trigger a retry
_TRANSIENT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    socket.gaierror,
    ConnectionError,
    ConnectionResetError,
    TimeoutError,
    OSError,
    BrokenPipeError,
)

# HTTP status codes worth retrying
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Defaults
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0  # seconds


def _is_retryable(exc: BaseException) -> bool:
    """Check whether an exception is transient and worth retrying."""
    if isinstance(exc, _TRANSIENT_EXCEPTIONS):
        return True
    if isinstance(exc, HttpError) and exc.resp.status in _RETRYABLE_STATUS_CODES:
        return True
    # httplib2 wraps socket errors in its own exception hierarchy
    cause = exc.__cause__ or exc.__context__
    if cause and isinstance(cause, _TRANSIENT_EXCEPTIONS):
        return True
    return False


def execute_with_retry(
    request: Any,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    operation: str = "API call",
) -> Any:
    """Execute a Google API request with retry on transient network errors.

    Wraps ``request.execute()`` with exponential backoff. Only retries on
    network-level failures (DNS, connection, timeout) and server errors
    (429, 5xx). Client errors (4xx) are raised immediately.

    Args:
        request: A Google API request object (has an ``.execute()`` method).
        max_retries: Maximum number of retry attempts after the first failure.
        base_delay: Base delay in seconds (doubled each retry).
        operation: Human-readable label for log messages.

    Returns:
        The result of ``request.execute()``.
    """
    last_exc: BaseException | None = None
    for attempt in range(1 + max_retries):
        try:
            return request.execute()
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                    operation,
                    attempt + 1,
                    1 + max_retries,
                    delay,
                    exc,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    operation,
                    1 + max_retries,
                    exc,
                )
    raise last_exc  # type: ignore[misc]


async def async_execute_with_retry(
    call: Callable[[], T],
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    operation: str = "API call",
) -> T:
    """Async version — runs blocking API call in a thread with retry.

    Useful for async code that needs to call the synchronous Google API client.
    """
    import asyncio

    last_exc: BaseException | None = None
    for attempt in range(1 + max_retries):
        try:
            return await asyncio.to_thread(call)
        except Exception as exc:
            last_exc = exc
            if not _is_retryable(exc):
                raise
            if attempt < max_retries:
                delay = base_delay * (2**attempt)
                logger.warning(
                    "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                    operation,
                    attempt + 1,
                    1 + max_retries,
                    delay,
                    exc,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "%s failed after %d attempts: %s",
                    operation,
                    1 + max_retries,
                    exc,
                )
    raise last_exc  # type: ignore[misc]
