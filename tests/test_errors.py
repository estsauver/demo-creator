"""Tests for error handling utilities."""

import pytest

from utils.errors import (
    ActionableSuggestion,
    DemoError,
    ErrorCategory,
    ErrorHandler,
    format_error,
    handle_error,
)


class TestActionableSuggestion:
    """Tests for ActionableSuggestion dataclass."""

    def test_basic_suggestion(self):
        """Should represent a basic suggestion."""
        suggestion = ActionableSuggestion(
            description="Check your API key",
        )

        assert suggestion.description == "Check your API key"
        assert suggestion.command is None

    def test_suggestion_with_command(self):
        """Should include command."""
        suggestion = ActionableSuggestion(
            description="Set API key",
            command="export ELEVENLABS_API_KEY='your_key'",
        )

        assert suggestion.command is not None

    def test_suggestion_with_link(self):
        """Should include documentation link."""
        suggestion = ActionableSuggestion(
            description="Get an API key",
            link="https://elevenlabs.io/api",
        )

        assert suggestion.link is not None


class TestDemoError:
    """Tests for DemoError dataclass."""

    def test_basic_error(self):
        """Should represent a basic error."""
        error = DemoError(
            category=ErrorCategory.CONFIGURATION,
            message="API key not set",
        )

        assert error.category == ErrorCategory.CONFIGURATION
        assert error.message == "API key not set"
        assert error.recoverable is True

    def test_error_with_suggestions(self):
        """Should include suggestions."""
        error = DemoError(
            category=ErrorCategory.SELECTOR,
            message="Element not found",
            suggestions=[
                ActionableSuggestion(description="Try a different selector"),
                ActionableSuggestion(description="Add a wait"),
            ],
        )

        assert len(error.suggestions) == 2

    def test_to_dict(self):
        """Should convert to dictionary."""
        error = DemoError(
            category=ErrorCategory.NETWORK,
            message="Connection failed",
            stage="record",
        )

        d = error.to_dict()

        assert d["category"] == "network"
        assert d["message"] == "Connection failed"
        assert d["stage"] == "record"

    def test_format(self):
        """Should format error for display."""
        error = DemoError(
            category=ErrorCategory.API,
            message="Rate limit exceeded",
            details="Too many requests",
            stage="audio",
            suggestions=[
                ActionableSuggestion(
                    description="Wait before retrying",
                    command="sleep 60",
                ),
            ],
        )

        formatted = error.format()

        assert "API ERROR" in formatted
        assert "Rate limit" in formatted
        assert "Wait before" in formatted
        assert "sleep 60" in formatted


class TestErrorHandler:
    """Tests for ErrorHandler class."""

    def test_analyze_configuration_error(self):
        """Should identify configuration errors."""
        handler = ErrorHandler()

        error = ValueError("ELEVENLABS_API_KEY not set")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.CONFIGURATION
        assert len(result.suggestions) > 0

    def test_analyze_selector_error(self):
        """Should identify selector errors."""
        handler = ErrorHandler()

        error = Exception("ElementNotFound: button.submit")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.SELECTOR

    def test_analyze_timeout_error(self):
        """Should identify timeout errors."""
        handler = ErrorHandler()

        error = TimeoutError("Operation timed out")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.TIMEOUT

    def test_analyze_network_error(self):
        """Should identify network errors."""
        handler = ErrorHandler()

        error = ConnectionError("ECONNREFUSED")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.NETWORK

    def test_analyze_rate_limit_error(self):
        """Should identify rate limit errors."""
        handler = ErrorHandler()

        error = Exception("rate limit exceeded")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.API

    def test_analyze_auth_error_401(self):
        """Should identify 401 auth errors."""
        handler = ErrorHandler()

        error = Exception("HTTP 401 Unauthorized")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.AUTHENTICATION

    def test_analyze_unknown_error(self):
        """Should handle unknown errors."""
        handler = ErrorHandler()

        error = Exception("Something completely unexpected")
        result = handler.analyze(error)

        assert result.category == ErrorCategory.UNKNOWN
        assert len(result.suggestions) > 0

    def test_analyze_with_stage(self):
        """Should include stage in error."""
        handler = ErrorHandler()

        error = Exception("test error")
        result = handler.analyze(error, stage="record")

        assert result.stage == "record"

    def test_analyze_with_context(self):
        """Should include context in error."""
        handler = ErrorHandler()

        error = Exception("test error")
        result = handler.analyze(error, context={"selector": ".button"})

        assert "selector" in result.context

    def test_format_error(self):
        """Should format error with suggestions."""
        handler = ErrorHandler()

        error = ValueError("HEYGEN_API_KEY not set")
        formatted = handler.format_error(error)

        assert "HEYGEN" in formatted
        assert "Suggestions" in formatted


class TestHandleError:
    """Tests for handle_error convenience function."""

    def test_handles_error(self):
        """Should return DemoError."""
        error = Exception("test error")
        result = handle_error(error)

        assert isinstance(result, DemoError)


class TestFormatError:
    """Tests for format_error convenience function."""

    def test_formats_error(self):
        """Should return formatted string."""
        error = ValueError("API key missing")
        formatted = format_error(error)

        assert isinstance(formatted, str)
        assert "API key" in formatted.lower() or "error" in formatted.lower()
