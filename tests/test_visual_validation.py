"""Tests for visual validation utilities."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.visual_validation import (
    ValidationResult,
    VisualValidator,
    validate_page_state,
)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_success_result(self):
        """Should represent successful validation."""
        result = ValidationResult(
            passed=True,
            confidence=0.95,
            explanation="Page shows expected search results",
            suggestions=[],
        )

        assert result.passed is True
        assert result.confidence == 0.95
        assert len(result.suggestions) == 0

    def test_failed_result_with_suggestions(self):
        """Should include suggestions for failures."""
        result = ValidationResult(
            passed=False,
            confidence=0.8,
            explanation="Search button not visible",
            suggestions=["Try scrolling down", "Check if element exists"],
        )

        assert result.passed is False
        assert len(result.suggestions) == 2

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = ValidationResult(
            passed=True,
            confidence=0.9,
            explanation="Test",
            suggestions=["Fix this"],
            screenshot_path=Path("/tmp/test.png"),
        )

        d = result.to_dict()

        assert d["passed"] is True
        assert d["confidence"] == 0.9
        assert d["screenshot_path"] == "/tmp/test.png"


class TestVisualValidator:
    """Tests for VisualValidator class."""

    def test_init_without_api_key(self, monkeypatch):
        """Should initialize without API key but skip validation."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        validator = VisualValidator()

        assert validator.api_key is None

    def test_init_with_api_key(self, monkeypatch):
        """Should initialize with API key."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        validator = VisualValidator()

        assert validator.api_key == "test_key"

    def test_validate_without_api_key(self, monkeypatch, tmp_path):
        """Should skip validation without API key."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        # Create test screenshot
        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"fake image data")

        validator = VisualValidator()
        result = validator.validate_screenshot(screenshot, "expected state")

        # Should pass but with 0 confidence
        assert result.passed is True
        assert result.confidence == 0.0
        assert "skipped" in result.explanation.lower()

    def test_validate_missing_screenshot(self, monkeypatch, tmp_path):
        """Should fail for missing screenshot."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        validator = VisualValidator()
        result = validator.validate_screenshot(
            tmp_path / "nonexistent.png",
            "expected state",
        )

        assert result.passed is False
        assert "not found" in result.explanation.lower()

    @patch("requests.post")
    def test_validate_with_api(self, mock_post, monkeypatch, tmp_path):
        """Should call API and parse response."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        # Create test screenshot
        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"fake image data")

        # Mock API response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{
                "text": json.dumps({
                    "passed": True,
                    "confidence": 0.95,
                    "explanation": "Page matches expected state",
                    "suggestions": [],
                })
            }]
        }
        mock_post.return_value = mock_response

        validator = VisualValidator()
        result = validator.validate_screenshot(screenshot, "shows search results")

        assert result.passed is True
        assert result.confidence == 0.95
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_validate_api_error(self, mock_post, monkeypatch, tmp_path):
        """Should handle API errors gracefully."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")

        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"fake image data")

        mock_post.side_effect = Exception("API Error")

        validator = VisualValidator()
        result = validator.validate_screenshot(screenshot, "expected state")

        assert result.passed is False
        assert "API Error" in result.explanation

    def test_get_media_type(self, monkeypatch):
        """Should return correct MIME type."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test_key")
        validator = VisualValidator()

        assert validator._get_media_type(Path("test.png")) == "image/png"
        assert validator._get_media_type(Path("test.jpg")) == "image/jpeg"
        assert validator._get_media_type(Path("test.jpeg")) == "image/jpeg"
        assert validator._get_media_type(Path("test.webp")) == "image/webp"


class TestValidatePageState:
    """Tests for validate_page_state convenience function."""

    def test_calls_validator(self, monkeypatch, tmp_path):
        """Should use VisualValidator internally."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        screenshot = tmp_path / "test.png"
        screenshot.write_bytes(b"fake data")

        result = validate_page_state(screenshot, "expected state")

        # Without API key, should skip
        assert result.passed is True
        assert result.confidence == 0.0
