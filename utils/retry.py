"""
Retry utilities with exponential backoff for demo-creator.

Provides decorators and utilities for robust retry logic on flaky operations
like browser automation, API calls, and K8s interactions.
"""

import functools
import logging
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Union

logger = logging.getLogger(__name__)


class RetryError(Exception):
    """Raised when all retry attempts have been exhausted."""

    def __init__(
        self,
        message: str,
        attempts: int,
        last_exception: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.attempts = attempts
        self.last_exception = last_exception


def is_retryable_exception(exc: Exception, retryable_types: Tuple[Type[Exception], ...]) -> bool:
    """Check if an exception should trigger a retry."""
    return isinstance(exc, retryable_types)


def calculate_backoff(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
) -> float:
    """
    Calculate delay with exponential backoff and optional jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential calculation
        jitter: Whether to add random jitter

    Returns:
        Delay in seconds
    """
    delay = min(base_delay * (exponential_base ** attempt), max_delay)

    if jitter:
        # Add up to 25% random jitter
        delay = delay * (0.75 + random.random() * 0.5)

    return delay


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        max_attempts: Maximum number of attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        jitter: Add random jitter to delays (default: True)
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry with (attempt, exception, delay)

    Returns:
        Decorated function

    Example:
        @retry(max_attempts=3, retryable_exceptions=(TimeoutError, ConnectionError))
        def fetch_data():
            return requests.get(url)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exception = exc

                    if attempt == max_attempts - 1:
                        # Last attempt failed
                        raise RetryError(
                            f"Failed after {max_attempts} attempts: {exc}",
                            attempts=max_attempts,
                            last_exception=exc,
                        ) from exc

                    # Calculate delay
                    delay = calculate_backoff(
                        attempt=attempt,
                        base_delay=base_delay,
                        max_delay=max_delay,
                        exponential_base=exponential_base,
                        jitter=jitter,
                    )

                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, exc, delay)
                    else:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                            f"Retrying in {delay:.2f}s..."
                        )

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise RetryError(
                f"Failed after {max_attempts} attempts",
                attempts=max_attempts,
                last_exception=last_exception,
            )

        return wrapper

    return decorator


async def retry_async(
    func: Callable,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
) -> Any:
    """
    Async retry helper with exponential backoff.

    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff
        jitter: Add random jitter to delays
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry

    Returns:
        Result of the function

    Example:
        result = await retry_async(
            lambda: fetch_data_async(),
            max_attempts=3,
            retryable_exceptions=(TimeoutError,)
        )
    """
    import asyncio

    last_exception = None

    for attempt in range(max_attempts):
        try:
            return await func()
        except retryable_exceptions as exc:
            last_exception = exc

            if attempt == max_attempts - 1:
                raise RetryError(
                    f"Failed after {max_attempts} attempts: {exc}",
                    attempts=max_attempts,
                    last_exception=exc,
                ) from exc

            delay = calculate_backoff(
                attempt=attempt,
                base_delay=base_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
            )

            if on_retry:
                on_retry(attempt + 1, exc, delay)
            else:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )

            await asyncio.sleep(delay)

    raise RetryError(
        f"Failed after {max_attempts} attempts",
        attempts=max_attempts,
        last_exception=last_exception,
    )


class RetryContext:
    """
    Context manager for retry logic with state tracking.

    Example:
        async with RetryContext(max_attempts=3) as ctx:
            while ctx.should_retry():
                try:
                    result = await risky_operation()
                    ctx.success()
                    break
                except Exception as e:
                    ctx.failed(e)
    """

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.retryable_exceptions = retryable_exceptions

        self._attempt = 0
        self._succeeded = False
        self._last_exception: Optional[Exception] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    @property
    def attempt(self) -> int:
        """Current attempt number (1-indexed)."""
        return self._attempt

    @property
    def succeeded(self) -> bool:
        """Whether the operation succeeded."""
        return self._succeeded

    @property
    def last_exception(self) -> Optional[Exception]:
        """The last exception that occurred."""
        return self._last_exception

    def should_retry(self) -> bool:
        """Check if another retry should be attempted."""
        if self._succeeded:
            return False
        if self._attempt >= self.max_attempts:
            return False
        return True

    def success(self) -> None:
        """Mark the operation as successful."""
        self._succeeded = True

    def failed(self, exception: Exception) -> None:
        """
        Mark the current attempt as failed.

        Args:
            exception: The exception that caused the failure
        """
        self._last_exception = exception
        self._attempt += 1

        if self._attempt < self.max_attempts:
            delay = calculate_backoff(
                attempt=self._attempt - 1,
                base_delay=self.base_delay,
                max_delay=self.max_delay,
                exponential_base=self.exponential_base,
                jitter=self.jitter,
            )
            logger.warning(
                f"Attempt {self._attempt}/{self.max_attempts} failed: {exception}. "
                f"Retrying in {delay:.2f}s..."
            )
            time.sleep(delay)

    def raise_if_exhausted(self) -> None:
        """Raise RetryError if all attempts have been exhausted."""
        if not self._succeeded and self._attempt >= self.max_attempts:
            raise RetryError(
                f"Failed after {self.max_attempts} attempts",
                attempts=self.max_attempts,
                last_exception=self._last_exception,
            )


# Common exception sets for different use cases
BROWSER_EXCEPTIONS = (TimeoutError, ConnectionError)
API_EXCEPTIONS = (TimeoutError, ConnectionError, ConnectionRefusedError)
K8S_EXCEPTIONS = (TimeoutError, ConnectionError, subprocess.SubprocessError if 'subprocess' in dir() else Exception)


def log_retry(attempt: int, exception: Exception, delay: float) -> None:
    """Default retry logger for use with on_retry callback."""
    logger.warning(
        f"Retry {attempt}: {type(exception).__name__}: {exception}. "
        f"Waiting {delay:.2f}s before next attempt."
    )


def print_retry(attempt: int, exception: Exception, delay: float) -> None:
    """Print-based retry logger for CLI output."""
    print(f"  Attempt {attempt} failed: {exception}. Retrying in {delay:.1f}s...")


# Import subprocess for K8S_EXCEPTIONS if available
try:
    import subprocess
    K8S_EXCEPTIONS = (TimeoutError, ConnectionError, subprocess.SubprocessError)
except ImportError:
    pass
