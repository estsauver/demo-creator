"""Tests for context monitoring utilities."""

import pytest

from utils.context_monitor import (
    ContextMonitor,
    ContextUsage,
    get_monitor,
    reset_monitor,
    track_context,
)


class TestContextUsage:
    """Tests for ContextUsage dataclass."""

    def test_basic_usage(self):
        """Should track basic usage."""
        usage = ContextUsage(
            stage_name="test",
            input_tokens=1000,
            output_tokens=500,
        )

        assert usage.total_tokens == 1500

    def test_files_tracking(self):
        """Should track files read and written."""
        usage = ContextUsage(stage_name="test")
        usage.files_read.append("file1.py")
        usage.files_written.append("file2.py")

        assert len(usage.files_read) == 1
        assert len(usage.files_written) == 1


class TestContextMonitor:
    """Tests for ContextMonitor class."""

    def test_default_limits(self):
        """Should have default context limits."""
        monitor = ContextMonitor()

        assert monitor.max_context == 200_000
        assert monitor.WARNING_THRESHOLD == 0.7
        assert monitor.CRITICAL_THRESHOLD == 0.9

    def test_custom_max_context(self):
        """Should accept custom max context."""
        monitor = ContextMonitor(max_context=100_000)

        assert monitor.max_context == 100_000

    def test_start_stage(self):
        """Should start tracking a stage."""
        monitor = ContextMonitor()
        monitor.start_stage("test_stage")

        assert "test_stage" in monitor.stages

    def test_add_input(self):
        """Should track input tokens."""
        monitor = ContextMonitor()
        monitor.add_input("test_stage", 1000)

        assert monitor.stages["test_stage"].input_tokens == 1000
        assert monitor.total_input == 1000

    def test_add_output(self):
        """Should track output tokens."""
        monitor = ContextMonitor()
        monitor.add_output("test_stage", 500)

        assert monitor.stages["test_stage"].output_tokens == 500
        assert monitor.total_output == 500

    def test_add_file_read(self):
        """Should track file reads."""
        monitor = ContextMonitor()
        monitor.add_file_read("test_stage", "/path/to/file.py", 100)

        assert "/path/to/file.py" in monitor.stages["test_stage"].files_read
        assert monitor.total_input == 100

    def test_add_file_write(self):
        """Should track file writes."""
        monitor = ContextMonitor()
        monitor.add_file_write("test_stage", "/path/to/output.py", 200)

        assert "/path/to/output.py" in monitor.stages["test_stage"].files_written
        assert monitor.total_output == 200

    def test_check_budget_within_limits(self):
        """Should return True when within limits."""
        monitor = ContextMonitor()
        monitor.add_input("test", 10000)

        assert monitor.check_budget("test") is True

    def test_check_budget_approaching_limit(self):
        """Should return True but warn when approaching limit."""
        monitor = ContextMonitor()
        # Add 75% of max context
        monitor.add_input("test", int(monitor.max_context * 0.75))

        assert monitor.check_budget("test") is True

    def test_check_budget_exceeds_critical(self):
        """Should return False when exceeding critical threshold."""
        monitor = ContextMonitor()
        # Add 95% of max context
        monitor.add_input("test", int(monitor.max_context * 0.95))

        assert monitor.check_budget("test") is False

    def test_estimate_operation(self):
        """Should return estimated tokens for operations."""
        monitor = ContextMonitor()

        assert monitor.estimate_operation("screenshot_base64") > 0
        assert monitor.estimate_operation("selector_map") > 0
        assert monitor.estimate_operation("unknown_op") == 1000  # default

    def test_can_fit(self):
        """Should check if operation can fit."""
        monitor = ContextMonitor()

        # Small operation should fit
        assert monitor.can_fit(1000) is True

        # Add most of the context
        monitor.add_input("test", int(monitor.max_context * 0.85))

        # Large operation should not fit
        assert monitor.can_fit(monitor.max_context * 0.1) is False

    def test_get_remaining(self):
        """Should return remaining tokens."""
        monitor = ContextMonitor()
        monitor.add_input("test", 50000)

        remaining = monitor.get_remaining()

        assert remaining == monitor.max_context - 50000

    def test_get_usage_report(self):
        """Should generate usage report."""
        monitor = ContextMonitor()
        monitor.add_input("stage1", 10000)
        monitor.add_output("stage1", 5000)
        monitor.add_file_read("stage1", "file.py")

        report = monitor.get_usage_report()

        assert report["total_tokens"] == 15000
        assert "stage1" in report["stages"]
        assert report["stages"]["stage1"]["input_tokens"] == 10000

    def test_get_recommendations(self):
        """Should generate recommendations."""
        monitor = ContextMonitor()
        # Add lots of tokens
        monitor.add_input("large_stage", 60000)

        recommendations = monitor.get_recommendations()

        assert len(recommendations) > 0


class TestGlobalMonitor:
    """Tests for global monitor functions."""

    def test_get_monitor(self):
        """Should return global monitor instance."""
        reset_monitor()
        monitor = get_monitor()

        assert isinstance(monitor, ContextMonitor)

    def test_get_monitor_same_instance(self):
        """Should return same instance on multiple calls."""
        reset_monitor()
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2

    def test_reset_monitor(self):
        """Should reset global monitor."""
        monitor1 = get_monitor()
        monitor1.add_input("test", 1000)

        reset_monitor()
        monitor2 = get_monitor()

        assert monitor2.total_input == 0


class TestTrackContext:
    """Tests for track_context convenience function."""

    def test_tracks_context(self):
        """Should track context using global monitor."""
        reset_monitor()

        result = track_context("test_stage", "selector_map")

        assert result is True
        assert get_monitor().total_input > 0

    def test_tracks_with_explicit_tokens(self):
        """Should track explicit token count."""
        reset_monitor()

        track_context("test_stage", "custom", tokens=5000)

        assert get_monitor().total_input == 5000
