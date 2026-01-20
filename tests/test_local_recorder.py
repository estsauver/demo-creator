"""Tests for local recorder utilities."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.local_recorder import (
    LocalRecorder,
    RecordingConfig,
    RecordingResult,
    convert_webm_to_mp4,
)


class TestRecordingConfig:
    """Tests for RecordingConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = RecordingConfig()

        assert config.viewport_width == 1920
        assert config.viewport_height == 1080
        assert config.frame_rate == 30
        assert config.headless is True
        assert config.timeout == 30000

    def test_custom_values(self):
        """Should accept custom values."""
        config = RecordingConfig(
            viewport_width=1280,
            viewport_height=720,
            headless=False,
        )

        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.headless is False


class TestRecordingResult:
    """Tests for RecordingResult dataclass."""

    def test_success_result(self):
        """Should represent successful recording."""
        result = RecordingResult(
            status="success",
            video_path=Path("/tmp/video.webm"),
            duration_seconds=45.5,
            screenshots=[Path("/tmp/scene_1.png")],
        )

        assert result.status == "success"
        assert result.video_path == Path("/tmp/video.webm")
        assert result.duration_seconds == 45.5
        assert len(result.screenshots) == 1

    def test_failed_result(self):
        """Should represent failed recording."""
        result = RecordingResult(
            status="failed",
            error="Element not found",
        )

        assert result.status == "failed"
        assert result.error == "Element not found"
        assert result.video_path is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = RecordingResult(
            status="success",
            video_path=Path("/tmp/video.webm"),
            duration_seconds=30.0,
        )

        d = result.to_dict()

        assert d["status"] == "success"
        assert d["video_path"] == "/tmp/video.webm"
        assert d["duration_seconds"] == 30.0


class TestLocalRecorder:
    """Tests for LocalRecorder class."""

    @pytest.fixture
    def recorder(self):
        """Create a recorder instance."""
        return LocalRecorder()

    @pytest.fixture
    def recorder_with_config(self):
        """Create a recorder with custom config."""
        config = RecordingConfig(
            viewport_width=1280,
            viewport_height=720,
            headless=True,
        )
        return LocalRecorder(config)

    def test_init_with_default_config(self, recorder):
        """Should initialize with default config."""
        assert recorder.config.viewport_width == 1920
        assert recorder.config.viewport_height == 1080

    def test_init_with_custom_config(self, recorder_with_config):
        """Should accept custom config."""
        assert recorder_with_config.config.viewport_width == 1280

    def test_execute_action_goto(self, recorder):
        """Should handle goto action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "goto",
            "url": "http://localhost:3000",
        })

        mock_page.goto.assert_called_once_with("http://localhost:3000")
        mock_page.wait_for_load_state.assert_called_once_with("networkidle")

    def test_execute_action_click(self, recorder):
        """Should handle click action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "click",
            "selector": "button.submit",
        })

        mock_page.click.assert_called_once_with("button.submit")

    def test_execute_action_fill(self, recorder):
        """Should handle fill action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "fill",
            "selector": "input[name='email']",
            "text": "test@example.com",
        })

        mock_page.fill.assert_called_once_with("input[name='email']", "test@example.com")

    def test_execute_action_type_human_like(self, recorder):
        """Should handle human-like typing."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "type",
            "selector": "input",
            "text": "hello",
            "human_like": True,
        })

        mock_page.type.assert_called_once_with("input", "hello", delay=100)

    def test_execute_action_wait(self, recorder):
        """Should handle wait action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "wait",
            "duration": 1000,
        })

        mock_page.wait_for_timeout.assert_called_once_with(1000)

    def test_execute_action_wait_for_selector(self, recorder):
        """Should handle wait_for_selector action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "wait_for_selector",
            "selector": ".results",
        })

        mock_page.wait_for_selector.assert_called_once()

    def test_execute_action_hover(self, recorder):
        """Should handle hover action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "hover",
            "selector": "button.menu",
        })

        mock_page.hover.assert_called_once_with("button.menu")

    def test_execute_action_select(self, recorder):
        """Should handle select action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "select",
            "selector": "select[name='country']",
            "value": "US",
        })

        mock_page.select_option.assert_called_once_with("select[name='country']", "US")

    def test_execute_action_assert_visible(self, recorder):
        """Should handle assert_visible action."""
        mock_page = MagicMock()
        mock_locator = MagicMock()
        mock_locator.is_visible.return_value = True
        mock_page.locator.return_value = mock_locator

        # Should not raise
        recorder._execute_action(mock_page, {
            "type": "assert_visible",
            "selector": ".result",
        })

        mock_page.locator.assert_called_once_with(".result")

    def test_execute_action_highlight(self, recorder):
        """Should handle highlight action."""
        mock_page = MagicMock()

        recorder._execute_action(mock_page, {
            "type": "highlight",
            "selector": ".important",
            "duration": 2000,
        })

        mock_page.evaluate.assert_called_once()
        mock_page.wait_for_timeout.assert_called_once_with(2000)


class TestConvertWebmToMp4:
    """Tests for convert_webm_to_mp4 function."""

    @patch("subprocess.run")
    def test_converts_with_default_output(self, mock_run):
        """Should convert to MP4 with default output path."""
        mock_run.return_value = MagicMock(returncode=0)

        input_path = Path("/tmp/recording.webm")
        result = convert_webm_to_mp4(input_path)

        assert result == Path("/tmp/recording.mp4")
        mock_run.assert_called_once()

        # Check ffmpeg was called with correct args
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-i" in call_args
        assert "libx264" in call_args

    @patch("subprocess.run")
    def test_converts_with_custom_output(self, mock_run):
        """Should convert to specified output path."""
        mock_run.return_value = MagicMock(returncode=0)

        input_path = Path("/tmp/recording.webm")
        output_path = Path("/tmp/final.mp4")
        result = convert_webm_to_mp4(input_path, output_path)

        assert result == output_path

    @patch("subprocess.run")
    def test_converts_with_custom_quality(self, mock_run):
        """Should use custom quality setting."""
        mock_run.return_value = MagicMock(returncode=0)

        input_path = Path("/tmp/recording.webm")
        convert_webm_to_mp4(input_path, quality=23)

        call_args = mock_run.call_args[0][0]
        assert "23" in call_args
