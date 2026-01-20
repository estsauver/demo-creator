"""Tests for retry utilities."""

import time
from unittest.mock import MagicMock, patch

import pytest

from utils.retry import (
    RetryError,
    RetryContext,
    calculate_backoff,
    retry,
)


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_base_delay(self):
        """First attempt should use base delay."""
        delay = calculate_backoff(attempt=0, base_delay=1.0, jitter=False)
        assert delay == 1.0

    def test_exponential_growth(self):
        """Delays should grow exponentially."""
        delays = [
            calculate_backoff(attempt=i, base_delay=1.0, jitter=False)
            for i in range(4)
        ]
        assert delays == [1.0, 2.0, 4.0, 8.0]

    def test_max_delay_cap(self):
        """Delay should not exceed max_delay."""
        delay = calculate_backoff(attempt=10, base_delay=1.0, max_delay=30.0, jitter=False)
        assert delay == 30.0

    def test_jitter_adds_randomness(self):
        """Jitter should add randomness to delays."""
        delays = [
            calculate_backoff(attempt=0, base_delay=1.0, jitter=True)
            for _ in range(100)
        ]
        # With jitter, not all delays should be the same
        assert len(set(delays)) > 1
        # All delays should be within expected range (0.75 to 1.25 of base)
        assert all(0.75 <= d <= 1.25 for d in delays)


class TestRetryDecorator:
    """Tests for retry decorator."""

    def test_success_on_first_attempt(self):
        """Function that succeeds immediately should only be called once."""
        mock_func = MagicMock(return_value="success")
        decorated = retry(max_attempts=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_on_failure(self):
        """Function should be retried on failure."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        decorated = retry(max_attempts=3, base_delay=0.01)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 2

    def test_exhausted_retries_raises(self):
        """Should raise RetryError when all attempts exhausted."""
        mock_func = MagicMock(side_effect=ValueError("always fails"))
        decorated = retry(max_attempts=3, base_delay=0.01)(mock_func)

        with pytest.raises(RetryError) as exc_info:
            decorated()

        assert exc_info.value.attempts == 3
        assert isinstance(exc_info.value.last_exception, ValueError)

    def test_only_retries_specified_exceptions(self):
        """Should only retry on specified exception types."""
        mock_func = MagicMock(side_effect=TypeError("not retryable"))
        decorated = retry(
            max_attempts=3,
            retryable_exceptions=(ValueError,),
            base_delay=0.01,
        )(mock_func)

        with pytest.raises(TypeError):
            decorated()

        assert mock_func.call_count == 1

    def test_on_retry_callback(self):
        """on_retry callback should be called on each retry."""
        mock_func = MagicMock(side_effect=[ValueError("fail"), "success"])
        mock_callback = MagicMock()
        decorated = retry(
            max_attempts=3,
            base_delay=0.01,
            on_retry=mock_callback,
        )(mock_func)

        decorated()

        assert mock_callback.call_count == 1
        call_args = mock_callback.call_args
        assert call_args[0][0] == 1  # attempt number
        assert isinstance(call_args[0][1], ValueError)  # exception


class TestRetryContext:
    """Tests for RetryContext class."""

    def test_successful_operation(self):
        """Context should track success."""
        with RetryContext(max_attempts=3) as ctx:
            while ctx.should_retry():
                ctx.success()
                break

        assert ctx.succeeded
        assert ctx.attempt == 0

    def test_failed_operation_retries(self):
        """Context should allow retries on failure."""
        attempts = 0

        with RetryContext(max_attempts=3, base_delay=0.01) as ctx:
            while ctx.should_retry():
                attempts += 1
                if attempts < 3:
                    ctx.failed(ValueError("fail"))
                else:
                    ctx.success()
                    break

        assert ctx.succeeded
        assert attempts == 3

    def test_exhausted_retries(self):
        """Context should stop retrying after max attempts."""
        attempts = 0

        with RetryContext(max_attempts=3, base_delay=0.01) as ctx:
            while ctx.should_retry():
                attempts += 1
                ctx.failed(ValueError("always fails"))

        assert not ctx.succeeded
        assert attempts == 3

    def test_raise_if_exhausted(self):
        """raise_if_exhausted should raise on failure."""
        with RetryContext(max_attempts=2, base_delay=0.01) as ctx:
            while ctx.should_retry():
                ctx.failed(ValueError("fail"))

        with pytest.raises(RetryError):
            ctx.raise_if_exhausted()

    def test_last_exception_tracked(self):
        """Last exception should be accessible."""
        original_error = ValueError("the error")

        with RetryContext(max_attempts=1, base_delay=0.01) as ctx:
            while ctx.should_retry():
                ctx.failed(original_error)

        assert ctx.last_exception is original_error
