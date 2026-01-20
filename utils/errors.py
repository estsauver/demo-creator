"""
Error handling utilities with actionable suggestions.

Provides structured errors with clear explanations and fixes.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for appropriate handling."""
    CONFIGURATION = "configuration"
    NETWORK = "network"
    AUTHENTICATION = "authentication"
    SELECTOR = "selector"
    TIMEOUT = "timeout"
    FILE_SYSTEM = "file_system"
    API = "api"
    RECORDING = "recording"
    COMPOSITING = "compositing"
    UNKNOWN = "unknown"


@dataclass
class ActionableSuggestion:
    """A specific action the user can take to fix an error."""

    description: str
    command: Optional[str] = None  # Shell command to run
    code: Optional[str] = None  # Code snippet to try
    link: Optional[str] = None  # Documentation link


@dataclass
class DemoError:
    """
    A structured error with actionable suggestions.

    Provides clear explanation of what went wrong and
    specific steps to resolve it.
    """

    category: ErrorCategory
    message: str
    details: Optional[str] = None
    stage: Optional[str] = None
    suggestions: List[ActionableSuggestion] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "details": self.details,
            "stage": self.stage,
            "suggestions": [
                {
                    "description": s.description,
                    "command": s.command,
                    "code": s.code,
                    "link": s.link,
                }
                for s in self.suggestions
            ],
            "recoverable": self.recoverable,
        }

    def format(self) -> str:
        """Format error for display."""
        lines = [
            f"❌ {self.category.value.upper()} ERROR: {self.message}",
        ]

        if self.details:
            lines.append(f"\n   {self.details}")

        if self.stage:
            lines.append(f"\n   Stage: {self.stage}")

        if self.suggestions:
            lines.append("\n   💡 Suggestions:")
            for i, suggestion in enumerate(self.suggestions, 1):
                lines.append(f"      {i}. {suggestion.description}")
                if suggestion.command:
                    lines.append(f"         $ {suggestion.command}")
                if suggestion.link:
                    lines.append(f"         📖 {suggestion.link}")

        return "\n".join(lines)


class ErrorHandler:
    """
    Handles errors and generates actionable suggestions.

    Analyzes error messages and provides specific fixes
    based on common failure patterns.
    """

    def __init__(self):
        self.error_patterns = self._build_error_patterns()

    def _build_error_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Build mapping of error patterns to suggestions."""
        return {
            # Configuration errors
            "ELEVENLABS_API_KEY": {
                "category": ErrorCategory.CONFIGURATION,
                "message": "ElevenLabs API key not configured",
                "suggestions": [
                    ActionableSuggestion(
                        description="Set the ElevenLabs API key environment variable",
                        command="export ELEVENLABS_API_KEY='your_api_key_here'",
                    ),
                    ActionableSuggestion(
                        description="Add to your shell profile for persistence",
                        command="echo 'export ELEVENLABS_API_KEY=\"your_key\"' >> ~/.zshrc",
                    ),
                    ActionableSuggestion(
                        description="Get an API key from ElevenLabs",
                        link="https://elevenlabs.io/api",
                    ),
                ],
            },
            "HEYGEN_API_KEY": {
                "category": ErrorCategory.CONFIGURATION,
                "message": "HeyGen API key not configured",
                "suggestions": [
                    ActionableSuggestion(
                        description="Set the HeyGen API key environment variable",
                        command="export HEYGEN_API_KEY='your_api_key_here'",
                    ),
                    ActionableSuggestion(
                        description="Get an API key from HeyGen",
                        link="https://heygen.com",
                    ),
                ],
            },
            "ELEVENLABS_VOICE_ID": {
                "category": ErrorCategory.CONFIGURATION,
                "message": "Voice ID not configured",
                "suggestions": [
                    ActionableSuggestion(
                        description="Set the voice ID environment variable",
                        command="export ELEVENLABS_VOICE_ID='your_voice_id'",
                    ),
                    ActionableSuggestion(
                        description="List available voices",
                        command="python list_voices.py",
                    ),
                ],
            },

            # Selector errors
            "ElementNotFound": {
                "category": ErrorCategory.SELECTOR,
                "message": "Element not found on page",
                "suggestions": [
                    ActionableSuggestion(
                        description="Re-run selector discovery to find updated selectors",
                        code="await discover_selectors(page)",
                    ),
                    ActionableSuggestion(
                        description="Add a wait before the action",
                        code="await page.wait_for_selector('.my-element', timeout=10000)",
                    ),
                    ActionableSuggestion(
                        description="Check if the element is inside an iframe",
                    ),
                ],
            },
            "selector": {
                "category": ErrorCategory.SELECTOR,
                "message": "Selector failed",
                "suggestions": [
                    ActionableSuggestion(
                        description="Try using a data-testid selector instead",
                        code="page.click('[data-testid=\"my-button\"]')",
                    ),
                    ActionableSuggestion(
                        description="Use text-based selector as fallback",
                        code="page.click('button:has-text(\"Submit\")')",
                    ),
                ],
            },

            # Timeout errors
            "TimeoutError": {
                "category": ErrorCategory.TIMEOUT,
                "message": "Operation timed out",
                "suggestions": [
                    ActionableSuggestion(
                        description="Increase the timeout value",
                        code="page.set_default_timeout(60000)  # 60 seconds",
                    ),
                    ActionableSuggestion(
                        description="Check if the page is loading slowly",
                    ),
                    ActionableSuggestion(
                        description="Verify the application is running",
                        command="curl -I http://localhost:3000",
                    ),
                ],
            },
            "timeout": {
                "category": ErrorCategory.TIMEOUT,
                "message": "Request timed out",
                "suggestions": [
                    ActionableSuggestion(
                        description="Check your internet connection",
                    ),
                    ActionableSuggestion(
                        description="Retry the operation",
                    ),
                ],
            },

            # Network errors
            "ConnectionError": {
                "category": ErrorCategory.NETWORK,
                "message": "Connection failed",
                "suggestions": [
                    ActionableSuggestion(
                        description="Check if the application is running",
                        command="lsof -i :3000",
                    ),
                    ActionableSuggestion(
                        description="Start the development server",
                        command="npm run dev",
                    ),
                ],
            },
            "ECONNREFUSED": {
                "category": ErrorCategory.NETWORK,
                "message": "Connection refused",
                "suggestions": [
                    ActionableSuggestion(
                        description="Verify the app is running on the expected port",
                        command="lsof -i :3000",
                    ),
                    ActionableSuggestion(
                        description="Check for port conflicts",
                        command="netstat -an | grep 3000",
                    ),
                ],
            },

            # API errors
            "rate limit": {
                "category": ErrorCategory.API,
                "message": "API rate limit exceeded",
                "suggestions": [
                    ActionableSuggestion(
                        description="Wait a few minutes before retrying",
                    ),
                    ActionableSuggestion(
                        description="Use caching to reduce API calls",
                        code="cache.get_audio(text) or generate_and_cache(text)",
                    ),
                ],
            },
            "401": {
                "category": ErrorCategory.AUTHENTICATION,
                "message": "Authentication failed",
                "suggestions": [
                    ActionableSuggestion(
                        description="Verify your API key is correct",
                    ),
                    ActionableSuggestion(
                        description="Check if your API key has expired",
                    ),
                ],
            },
            "403": {
                "category": ErrorCategory.AUTHENTICATION,
                "message": "Access forbidden",
                "suggestions": [
                    ActionableSuggestion(
                        description="Check if your API key has the required permissions",
                    ),
                ],
            },

            # Recording errors
            "video": {
                "category": ErrorCategory.RECORDING,
                "message": "Video recording failed",
                "suggestions": [
                    ActionableSuggestion(
                        description="Ensure Playwright is installed correctly",
                        command="npx playwright install chromium",
                    ),
                    ActionableSuggestion(
                        description="Check available disk space",
                        command="df -h",
                    ),
                ],
            },

            # File system errors
            "FileNotFoundError": {
                "category": ErrorCategory.FILE_SYSTEM,
                "message": "File not found",
                "suggestions": [
                    ActionableSuggestion(
                        description="Check the file path is correct",
                    ),
                    ActionableSuggestion(
                        description="Verify the file exists",
                        command="ls -la /path/to/file",
                    ),
                ],
            },
            "PermissionError": {
                "category": ErrorCategory.FILE_SYSTEM,
                "message": "Permission denied",
                "suggestions": [
                    ActionableSuggestion(
                        description="Check file permissions",
                        command="ls -la /path/to/file",
                    ),
                    ActionableSuggestion(
                        description="Try running with appropriate permissions",
                    ),
                ],
            },
        }

    def analyze(
        self,
        error: Exception,
        stage: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DemoError:
        """
        Analyze an exception and generate actionable error.

        Args:
            error: The exception that occurred
            stage: Optional stage name where error occurred
            context: Optional additional context

        Returns:
            DemoError with suggestions
        """
        error_str = str(error)
        error_type = type(error).__name__

        # Check for matching patterns
        for pattern, info in self.error_patterns.items():
            if pattern.lower() in error_str.lower() or pattern == error_type:
                return DemoError(
                    category=info["category"],
                    message=info["message"],
                    details=error_str,
                    stage=stage,
                    suggestions=info["suggestions"],
                    context=context or {},
                )

        # Default error
        return DemoError(
            category=ErrorCategory.UNKNOWN,
            message=f"An error occurred: {error_type}",
            details=error_str,
            stage=stage,
            suggestions=[
                ActionableSuggestion(
                    description="Check the error details above",
                ),
                ActionableSuggestion(
                    description="Try running the operation again",
                ),
            ],
            context=context or {},
        )

    def format_error(
        self,
        error: Exception,
        stage: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Format an exception as an actionable error message.

        Args:
            error: The exception
            stage: Optional stage name
            context: Optional context

        Returns:
            Formatted error string
        """
        demo_error = self.analyze(error, stage, context)
        return demo_error.format()


# Global error handler
_handler = ErrorHandler()


def handle_error(
    error: Exception,
    stage: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> DemoError:
    """
    Handle an exception and return structured error.

    Args:
        error: The exception
        stage: Optional stage name
        context: Optional context

    Returns:
        DemoError with suggestions
    """
    return _handler.analyze(error, stage, context)


def format_error(
    error: Exception,
    stage: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Format an exception as actionable error message.

    Args:
        error: The exception
        stage: Optional stage name
        context: Optional context

    Returns:
        Formatted error string
    """
    return _handler.format_error(error, stage, context)
