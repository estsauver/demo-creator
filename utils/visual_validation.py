"""
Visual validation utilities using LLM vision.

Validates that page states match expected descriptions using
multimodal LLM capabilities.
"""

import base64
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of visual validation."""

    passed: bool
    confidence: float  # 0.0 to 1.0
    explanation: str
    suggestions: List[str]
    screenshot_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "suggestions": self.suggestions,
            "screenshot_path": str(self.screenshot_path) if self.screenshot_path else None,
        }


class VisualValidator:
    """
    Validates page states using LLM vision capabilities.

    Uses Claude or other multimodal LLMs to analyze screenshots
    and verify they match expected states.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize visual validator.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.base_url = "https://api.anthropic.com/v1"

    def validate_screenshot(
        self,
        screenshot_path: Path,
        expected_state: str,
        context: Optional[str] = None,
    ) -> ValidationResult:
        """
        Validate a screenshot matches the expected state.

        Args:
            screenshot_path: Path to screenshot image
            expected_state: Description of what should be visible
            context: Optional additional context about the page

        Returns:
            ValidationResult with pass/fail and explanation
        """
        if not self.api_key:
            logger.warning("No API key configured, skipping visual validation")
            return ValidationResult(
                passed=True,
                confidence=0.0,
                explanation="Visual validation skipped (no API key)",
                suggestions=[],
                screenshot_path=screenshot_path,
            )

        # Read and encode screenshot
        screenshot_path = Path(screenshot_path)
        if not screenshot_path.exists():
            return ValidationResult(
                passed=False,
                confidence=1.0,
                explanation=f"Screenshot not found: {screenshot_path}",
                suggestions=["Verify the screenshot was captured correctly"],
                screenshot_path=screenshot_path,
            )

        image_data = base64.b64encode(screenshot_path.read_bytes()).decode("utf-8")
        media_type = self._get_media_type(screenshot_path)

        # Build prompt
        prompt = self._build_validation_prompt(expected_state, context)

        try:
            response = self._call_vision_api(image_data, media_type, prompt)
            return self._parse_validation_response(response, screenshot_path)
        except Exception as e:
            logger.exception("Visual validation failed")
            return ValidationResult(
                passed=False,
                confidence=0.0,
                explanation=f"Validation error: {str(e)}",
                suggestions=["Check API key and network connectivity"],
                screenshot_path=screenshot_path,
            )

    def validate_action_result(
        self,
        before_screenshot: Path,
        after_screenshot: Path,
        action_description: str,
        expected_change: str,
    ) -> ValidationResult:
        """
        Validate that an action produced the expected change.

        Args:
            before_screenshot: Screenshot before the action
            after_screenshot: Screenshot after the action
            action_description: Description of the action taken
            expected_change: Description of what should have changed

        Returns:
            ValidationResult
        """
        if not self.api_key:
            logger.warning("No API key configured, skipping visual validation")
            return ValidationResult(
                passed=True,
                confidence=0.0,
                explanation="Visual validation skipped (no API key)",
                suggestions=[],
                screenshot_path=after_screenshot,
            )

        # Read both screenshots
        before_path = Path(before_screenshot)
        after_path = Path(after_screenshot)

        if not before_path.exists() or not after_path.exists():
            return ValidationResult(
                passed=False,
                confidence=1.0,
                explanation="One or both screenshots not found",
                suggestions=["Verify screenshots were captured"],
                screenshot_path=after_path,
            )

        before_data = base64.b64encode(before_path.read_bytes()).decode("utf-8")
        after_data = base64.b64encode(after_path.read_bytes()).decode("utf-8")
        media_type = self._get_media_type(after_path)

        prompt = self._build_comparison_prompt(action_description, expected_change)

        try:
            response = self._call_comparison_api(
                before_data, after_data, media_type, prompt
            )
            return self._parse_validation_response(response, after_path)
        except Exception as e:
            logger.exception("Visual comparison failed")
            return ValidationResult(
                passed=False,
                confidence=0.0,
                explanation=f"Comparison error: {str(e)}",
                suggestions=["Check API key and network connectivity"],
                screenshot_path=after_path,
            )

    def _build_validation_prompt(
        self,
        expected_state: str,
        context: Optional[str],
    ) -> str:
        """Build the validation prompt."""
        prompt = f"""Analyze this screenshot and determine if it matches the expected state.

Expected state: {expected_state}
"""
        if context:
            prompt += f"\nAdditional context: {context}\n"

        prompt += """
Respond with a JSON object containing:
- "passed": boolean - true if the screenshot matches the expected state
- "confidence": float 0.0-1.0 - how confident you are in your assessment
- "explanation": string - brief explanation of what you see vs what was expected
- "suggestions": array of strings - if not passed, actionable suggestions to fix

Only respond with the JSON object, no other text."""

        return prompt

    def _build_comparison_prompt(
        self,
        action_description: str,
        expected_change: str,
    ) -> str:
        """Build the comparison prompt."""
        return f"""Compare these two screenshots (before and after an action) and determine if the expected change occurred.

Action taken: {action_description}
Expected change: {expected_change}

The first image is BEFORE the action, the second is AFTER.

Respond with a JSON object containing:
- "passed": boolean - true if the expected change is visible in the after image
- "confidence": float 0.0-1.0 - how confident you are
- "explanation": string - what changed between the images vs what was expected
- "suggestions": array of strings - if not passed, suggestions to achieve the expected result

Only respond with the JSON object, no other text."""

    def _call_vision_api(
        self,
        image_data: str,
        media_type: str,
        prompt: str,
    ) -> str:
        """Call the vision API with a single image."""
        response = requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    def _call_comparison_api(
        self,
        before_data: str,
        after_data: str,
        media_type: str,
        prompt: str,
    ) -> str:
        """Call the vision API with two images."""
        response = requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1024,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": before_data,
                                },
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": after_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt,
                            },
                        ],
                    }
                ],
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]

    def _parse_validation_response(
        self,
        response: str,
        screenshot_path: Path,
    ) -> ValidationResult:
        """Parse the LLM response into a ValidationResult."""
        try:
            # Try to parse as JSON
            data = json.loads(response)
            return ValidationResult(
                passed=data.get("passed", False),
                confidence=float(data.get("confidence", 0.5)),
                explanation=data.get("explanation", "No explanation provided"),
                suggestions=data.get("suggestions", []),
                screenshot_path=screenshot_path,
            )
        except json.JSONDecodeError:
            # Fallback: try to extract info from text
            passed = "yes" in response.lower() or "passed" in response.lower()
            return ValidationResult(
                passed=passed,
                confidence=0.5,
                explanation=response[:500],
                suggestions=[],
                screenshot_path=screenshot_path,
            )

    def _get_media_type(self, path: Path) -> str:
        """Get MIME type for an image file."""
        suffix = path.suffix.lower()
        return {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(suffix, "image/png")


def validate_page_state(
    screenshot_path: Path,
    expected_state: str,
    context: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ValidationResult:
    """
    Convenience function to validate a page state.

    Args:
        screenshot_path: Path to screenshot
        expected_state: Description of expected state
        context: Optional additional context
        api_key: Optional API key

    Returns:
        ValidationResult
    """
    validator = VisualValidator(api_key)
    return validator.validate_screenshot(screenshot_path, expected_state, context)


def validate_action(
    before_screenshot: Path,
    after_screenshot: Path,
    action: str,
    expected_change: str,
    api_key: Optional[str] = None,
) -> ValidationResult:
    """
    Convenience function to validate an action's result.

    Args:
        before_screenshot: Screenshot before action
        after_screenshot: Screenshot after action
        action: Description of action taken
        expected_change: Description of expected change
        api_key: Optional API key

    Returns:
        ValidationResult
    """
    validator = VisualValidator(api_key)
    return validator.validate_action_result(
        before_screenshot, after_screenshot, action, expected_change
    )
