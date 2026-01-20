"""Tests for smart waiting utilities."""

from unittest.mock import MagicMock, patch

import pytest

from utils.smart_wait import (
    DEFAULT_LOADING_SELECTORS,
    smart_wait,
    wait_for_element_stable,
    wait_for_idle,
    wait_for_no_animation,
)


class TestDefaultLoadingSelectors:
    """Tests for default loading selectors."""

    def test_contains_common_selectors(self):
        """Should include common loading indicators."""
        assert ".loading" in DEFAULT_LOADING_SELECTORS
        assert ".spinner" in DEFAULT_LOADING_SELECTORS
        assert "[aria-busy='true']" in DEFAULT_LOADING_SELECTORS


class TestSmartWait:
    """Tests for smart_wait function."""

    def test_waits_for_network_idle(self):
        """Should wait for network idle."""
        page = MagicMock()

        smart_wait(page)

        page.wait_for_load_state.assert_called_once()
        args = page.wait_for_load_state.call_args
        assert args[0][0] == "networkidle"

    def test_waits_for_loading_indicators(self):
        """Should wait for loading indicators to disappear."""
        page = MagicMock()

        smart_wait(page)

        page.wait_for_function.assert_called()

    def test_waits_for_animation_settle(self):
        """Should wait for animations to settle."""
        page = MagicMock()

        smart_wait(page, animation_settle_ms=500)

        page.wait_for_timeout.assert_called_with(500)

    def test_custom_loading_selectors(self):
        """Should use custom loading selectors."""
        page = MagicMock()
        custom_selectors = [".my-loader", ".custom-spinner"]

        smart_wait(page, loading_selectors=custom_selectors)

        call_args = page.wait_for_function.call_args
        js_code = call_args[0][0]
        assert ".my-loader" in js_code
        assert ".custom-spinner" in js_code

    def test_handles_network_idle_timeout(self):
        """Should continue if network idle times out."""
        page = MagicMock()
        page.wait_for_load_state.side_effect = Exception("Timeout")

        # Should not raise
        smart_wait(page)

    def test_handles_loading_indicator_timeout(self):
        """Should continue if loading indicator wait times out."""
        page = MagicMock()
        page.wait_for_function.side_effect = Exception("Timeout")

        # Should not raise
        smart_wait(page)


class TestWaitForElementStable:
    """Tests for wait_for_element_stable function."""

    def test_returns_true_on_success(self):
        """Should return True when element stabilizes."""
        page = MagicMock()
        page.wait_for_function.return_value = True

        result = wait_for_element_stable(page, ".my-element")

        assert result is True

    def test_returns_false_on_timeout(self):
        """Should return False when timeout occurs."""
        page = MagicMock()
        page.wait_for_function.side_effect = Exception("Timeout")

        result = wait_for_element_stable(page, ".my-element")

        assert result is False

    def test_passes_selector_to_function(self):
        """Should pass selector to JavaScript function."""
        page = MagicMock()

        wait_for_element_stable(page, ".test-element")

        call_args = page.wait_for_function.call_args
        js_code = call_args[0][0]
        assert "querySelector" in js_code

    def test_custom_stability_time(self):
        """Should use custom stability time."""
        page = MagicMock()

        wait_for_element_stable(page, ".my-element", stability_ms=1000)

        call_args = page.wait_for_function.call_args
        assert 1000 in call_args[0][1]


class TestWaitForNoAnimation:
    """Tests for wait_for_no_animation function."""

    def test_returns_true_on_success(self):
        """Should return True when animations complete."""
        page = MagicMock()

        result = wait_for_no_animation(page)

        assert result is True

    def test_returns_false_on_timeout(self):
        """Should return False on timeout."""
        page = MagicMock()
        page.wait_for_function.side_effect = Exception("Timeout")

        result = wait_for_no_animation(page)

        assert result is False

    def test_checks_animations(self):
        """Should check document.getAnimations()."""
        page = MagicMock()

        wait_for_no_animation(page)

        call_args = page.wait_for_function.call_args
        js_code = call_args[0][0]
        assert "getAnimations" in js_code


class TestWaitForIdle:
    """Tests for wait_for_idle function."""

    def test_returns_true_on_success(self):
        """Should return True when page becomes idle."""
        page = MagicMock()

        result = wait_for_idle(page)

        assert result is True

    def test_returns_false_on_timeout(self):
        """Should return False on timeout."""
        page = MagicMock()
        page.wait_for_function.side_effect = Exception("Timeout")

        result = wait_for_idle(page)

        assert result is False

    def test_uses_mutation_observer(self):
        """Should use MutationObserver for DOM changes."""
        page = MagicMock()

        wait_for_idle(page)

        call_args = page.wait_for_function.call_args
        js_code = call_args[0][0]
        assert "MutationObserver" in js_code

    def test_custom_idle_time(self):
        """Should use custom idle time."""
        page = MagicMock()

        wait_for_idle(page, idle_time_ms=1000)

        call_args = page.wait_for_function.call_args
        assert call_args[0][1] == 1000
