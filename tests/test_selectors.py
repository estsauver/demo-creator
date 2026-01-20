"""Tests for selector discovery utilities."""

from unittest.mock import MagicMock, patch

import pytest

from utils.selectors import (
    DiscoveredElement,
    SelectorDiscovery,
    discover_selectors,
    suggest_alternative_selectors,
    validate_selector,
)


class TestDiscoveredElement:
    """Tests for DiscoveredElement dataclass."""

    def test_to_dict(self):
        """Should convert to dictionary."""
        element = DiscoveredElement(
            tag="button",
            text="Submit",
            selector="button:has-text('Submit')",
            selector_type="text",
            priority=3,
            attributes={"class": "btn-primary"},
            bounding_box={"x": 100, "y": 200, "width": 80, "height": 40},
        )

        result = element.to_dict()

        assert result["tag"] == "button"
        assert result["text"] == "Submit"
        assert result["selector"] == "button:has-text('Submit')"
        assert result["priority"] == 3


class TestSelectorDiscovery:
    """Tests for SelectorDiscovery class."""

    @pytest.fixture
    def discovery(self):
        """Create a SelectorDiscovery instance."""
        return SelectorDiscovery(base_url="http://localhost:3000")

    def test_generate_selector_prefers_test_id(self, discovery):
        """Should prefer data-testid selectors."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="button",
            text="Submit",
            attributes={"data-testid": "submit-btn", "aria-label": "Submit form"},
            element_type="button",
        )

        assert selector == "[data-testid='submit-btn']"
        assert selector_type == "test-id"
        assert priority == SelectorDiscovery.PRIORITY_TEST_ID

    def test_generate_selector_prefers_aria_label_over_text(self, discovery):
        """Should prefer aria-label over text when no test-id."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="button",
            text="Submit",
            attributes={"aria-label": "Submit form"},
            element_type="button",
        )

        assert selector == "[aria-label='Submit form']"
        assert selector_type == "aria-label"
        assert priority == SelectorDiscovery.PRIORITY_ARIA_LABEL

    def test_generate_selector_uses_text_for_buttons(self, discovery):
        """Should use text-based selector for buttons without better options."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="button",
            text="Submit",
            attributes={"class": "btn-primary"},
            element_type="button",
        )

        assert selector == "button:has-text('Submit')"
        assert selector_type == "text"
        assert priority == SelectorDiscovery.PRIORITY_TEXT

    def test_generate_selector_uses_placeholder_for_inputs(self, discovery):
        """Should use placeholder for input elements."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="input",
            text="",
            attributes={"placeholder": "Enter email"},
            element_type="input",
        )

        assert selector == "input[placeholder='Enter email']"
        assert selector_type == "placeholder"
        assert priority == SelectorDiscovery.PRIORITY_PLACEHOLDER

    def test_generate_selector_uses_name_attribute(self, discovery):
        """Should use name attribute when available."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="input",
            text="",
            attributes={"name": "email"},
            element_type="input",
        )

        assert selector == "input[name='email']"
        assert selector_type == "name"
        assert priority == SelectorDiscovery.PRIORITY_NAME

    def test_generate_selector_falls_back_to_css(self, discovery):
        """Should fall back to CSS class as last resort."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="div",
            text="",
            attributes={"class": "custom-widget special-item"},
            element_type="button",
        )

        assert "custom-widget" in selector
        assert selector_type == "css"
        assert priority == SelectorDiscovery.PRIORITY_CSS_CLASS

    def test_generate_selector_filters_utility_classes(self, discovery):
        """Should filter out utility CSS classes."""
        selector, selector_type, priority = discovery._generate_selector(
            tag="div",
            text="",
            attributes={"class": "p-4 m-2 text-lg custom-widget"},
            element_type="button",
        )

        # Should only use meaningful class
        assert "custom-widget" in selector
        assert "p-4" not in selector
        assert "m-2" not in selector

    def test_generate_name_from_text(self, discovery):
        """Should generate semantic name from text."""
        element = DiscoveredElement(
            tag="button",
            text="Submit Form",
            selector="button",
            selector_type="text",
            priority=3,
        )

        name = discovery._generate_name(element, "button")

        assert name == "button_submit_form"

    def test_generate_name_from_aria(self, discovery):
        """Should generate name from aria-label."""
        element = DiscoveredElement(
            tag="button",
            text="",
            selector="button",
            selector_type="aria-label",
            priority=2,
            attributes={"aria-label": "Close dialog"},
        )

        name = discovery._generate_name(element, "button")

        assert name == "button_close_dialog"


class TestDiscoverSelectors:
    """Tests for discover_selectors convenience function."""

    def test_discover_selectors_returns_dict(self):
        """Should return dict of name to selector."""
        mock_page = MagicMock()
        mock_page.url = "http://localhost:3000"

        # Mock locators for buttons
        mock_button = MagicMock()
        mock_button.is_visible.return_value = True
        mock_button.evaluate.return_value = "button"
        mock_button.inner_text.return_value = "Submit"
        mock_button.get_attribute.side_effect = lambda attr: {
            "data-testid": "submit-btn",
            "aria-label": None,
            "name": None,
            "placeholder": None,
            "id": None,
            "class": "btn",
            "type": "submit",
        }.get(attr)
        mock_button.bounding_box.return_value = {"x": 0, "y": 0, "width": 100, "height": 40}

        mock_page.locator.return_value.all.return_value = [mock_button]

        result = discover_selectors(mock_page)

        assert isinstance(result, dict)


class TestValidateSelector:
    """Tests for validate_selector function."""

    def test_validate_selector_success(self):
        """Should return True for valid selector."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_page.locator.return_value = mock_locator

        result = validate_selector(mock_page, "[data-testid='submit']")

        assert result is True
        mock_locator.wait_for.assert_called_once()

    def test_validate_selector_failure(self):
        """Should return False for invalid selector."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.wait_for.side_effect = Exception("Element not found")
        mock_page.locator.return_value = mock_locator

        result = validate_selector(mock_page, "[data-testid='nonexistent']")

        assert result is False
