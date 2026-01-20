"""Tests for hybrid demo compositing utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.hybrid_compositor import (
    HybridCompositor,
    HybridConfig,
    HybridResult,
    LayoutType,
    composite_hybrid_demo,
)


class TestLayoutType:
    """Tests for LayoutType enum."""

    def test_layout_types(self):
        """Should have all expected layout types."""
        assert LayoutType.SPLIT.value == "split"
        assert LayoutType.SEQUENTIAL.value == "sequential"
        assert LayoutType.PIP.value == "pip"


class TestHybridConfig:
    """Tests for HybridConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = HybridConfig()

        assert config.layout == LayoutType.SPLIT
        assert config.terminal_position == "left"
        assert config.terminal_width_percent == 40
        assert config.output_width == 1920
        assert config.output_height == 1080

    def test_custom_values(self):
        """Should accept custom values."""
        config = HybridConfig(
            layout=LayoutType.PIP,
            terminal_position="right",
            terminal_width_percent=30,
            pip_position="top-left",
            pip_scale=0.25,
        )

        assert config.layout == LayoutType.PIP
        assert config.terminal_position == "right"
        assert config.pip_scale == 0.25


class TestHybridResult:
    """Tests for HybridResult dataclass."""

    def test_success_result(self):
        """Should represent successful compositing."""
        result = HybridResult(
            status="success",
            video_path=Path("/tmp/hybrid.mp4"),
            duration_seconds=120.0,
        )

        assert result.status == "success"
        assert result.video_path is not None
        assert result.duration_seconds == 120.0

    def test_failed_result(self):
        """Should represent failed compositing."""
        result = HybridResult(
            status="failed",
            error="FFmpeg not found",
        )

        assert result.status == "failed"
        assert result.error == "FFmpeg not found"
        assert result.video_path is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = HybridResult(
            status="success",
            video_path=Path("/tmp/hybrid.mp4"),
            duration_seconds=60.0,
        )

        d = result.to_dict()

        assert d["status"] == "success"
        assert d["video_path"] == "/tmp/hybrid.mp4"
        assert d["duration_seconds"] == 60.0


class TestHybridCompositor:
    """Tests for HybridCompositor class."""

    def test_init_with_defaults(self):
        """Should initialize with default config."""
        compositor = HybridCompositor()

        assert compositor.config is not None
        assert compositor.config.layout == LayoutType.SPLIT

    def test_init_with_custom_config(self):
        """Should accept custom config."""
        config = HybridConfig(layout=LayoutType.PIP)
        compositor = HybridCompositor(config=config)

        assert compositor.config.layout == LayoutType.PIP

    def test_hex_to_rgb(self):
        """Should convert hex colors to RGB."""
        compositor = HybridCompositor()

        assert compositor._hex_to_rgb("#ffffff") == (255, 255, 255)
        assert compositor._hex_to_rgb("#000000") == (0, 0, 0)
        assert compositor._hex_to_rgb("#1e1e1e") == (30, 30, 30)
        assert compositor._hex_to_rgb("ff0000") == (255, 0, 0)  # Without #

    @patch("subprocess.run")
    def test_get_video_duration(self, mock_run, tmp_path):
        """Should get video duration using ffprobe."""
        mock_run.return_value = MagicMock(
            stdout='{"format": {"duration": "120.5"}}'
        )

        compositor = HybridCompositor()
        duration = compositor._get_video_duration(tmp_path / "video.mp4")

        assert duration == 120.5

    @patch("subprocess.run")
    def test_get_video_duration_error(self, mock_run, tmp_path):
        """Should return None on error."""
        mock_run.side_effect = Exception("ffprobe not found")

        compositor = HybridCompositor()
        duration = compositor._get_video_duration(tmp_path / "video.mp4")

        assert duration is None

    def test_composite_unknown_layout(self, tmp_path):
        """Should fail for unknown layout type."""
        config = HybridConfig()
        config.layout = "unknown"  # Force invalid layout

        compositor = HybridCompositor(config=config)
        result = compositor.composite(
            terminal_video=tmp_path / "terminal.mp4",
            browser_video=tmp_path / "browser.mp4",
            output_path=tmp_path / "output.mp4",
        )

        assert result.status == "failed"
        assert "Unknown layout" in result.error


class TestCompositeHybridDemo:
    """Tests for composite_hybrid_demo convenience function."""

    @patch("utils.hybrid_compositor.HybridCompositor")
    def test_creates_compositor(self, mock_compositor_class, tmp_path):
        """Should create HybridCompositor internally."""
        mock_compositor = MagicMock()
        mock_compositor.composite.return_value = HybridResult(status="success")
        mock_compositor_class.return_value = mock_compositor

        composite_hybrid_demo(
            terminal_video=tmp_path / "terminal.mp4",
            browser_video=tmp_path / "browser.mp4",
            output_path=tmp_path / "output.mp4",
        )

        mock_compositor_class.assert_called_once()
        mock_compositor.composite.assert_called_once()

    @patch("utils.hybrid_compositor.HybridCompositor")
    def test_passes_layout_option(self, mock_compositor_class, tmp_path):
        """Should pass layout configuration."""
        mock_compositor = MagicMock()
        mock_compositor.composite.return_value = HybridResult(status="success")
        mock_compositor_class.return_value = mock_compositor

        composite_hybrid_demo(
            terminal_video=tmp_path / "terminal.mp4",
            browser_video=tmp_path / "browser.mp4",
            output_path=tmp_path / "output.mp4",
            layout="pip",
        )

        call_args = mock_compositor_class.call_args
        config = call_args[0][0]
        assert config.layout == LayoutType.PIP

    @patch("utils.hybrid_compositor.HybridCompositor")
    def test_passes_terminal_position(self, mock_compositor_class, tmp_path):
        """Should pass terminal position."""
        mock_compositor = MagicMock()
        mock_compositor.composite.return_value = HybridResult(status="success")
        mock_compositor_class.return_value = mock_compositor

        composite_hybrid_demo(
            terminal_video=tmp_path / "terminal.mp4",
            browser_video=tmp_path / "browser.mp4",
            output_path=tmp_path / "output.mp4",
            terminal_position="right",
            terminal_width_percent=50,
        )

        call_args = mock_compositor_class.call_args
        config = call_args[0][0]
        assert config.terminal_position == "right"
        assert config.terminal_width_percent == 50
