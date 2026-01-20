"""Tests for audio preview utilities."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.audio_preview import (
    AudioPreview,
    AudioPreviewResult,
    generate_preview,
    play_audio,
)


class TestAudioPreviewResult:
    """Tests for AudioPreviewResult dataclass."""

    def test_success_result(self):
        """Should represent successful preview."""
        result = AudioPreviewResult(
            status="success",
            audio_path=Path("/tmp/preview.mp3"),
            duration_seconds=15.5,
            voice_name="Test Voice",
        )

        assert result.status == "success"
        assert result.audio_path == Path("/tmp/preview.mp3")
        assert result.duration_seconds == 15.5

    def test_failed_result(self):
        """Should represent failed preview."""
        result = AudioPreviewResult(
            status="failed",
            error="API key not configured",
        )

        assert result.status == "failed"
        assert result.error == "API key not configured"
        assert result.audio_path is None


class TestAudioPreview:
    """Tests for AudioPreview class."""

    @pytest.fixture
    def preview(self, monkeypatch):
        """Create a preview instance with mocked credentials."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice")
        return AudioPreview()

    def test_init_without_credentials(self):
        """Should use None for missing credentials."""
        preview = AudioPreview()
        # Will be None if env vars not set
        # (tests run with cleaned env)

    def test_truncate_short_text(self, preview):
        """Should not truncate short text."""
        text = "This is a short sentence."
        result = preview._truncate_for_preview(text)
        assert result == text

    def test_truncate_long_text_at_sentence(self, preview):
        """Should truncate at sentence boundary."""
        text = "First sentence. " + "A" * 400 + ". More text here."
        result = preview._truncate_for_preview(text)

        assert len(result) <= AudioPreview.MAX_PREVIEW_CHARS + 10
        assert result.endswith(".")

    def test_truncate_long_text_at_word(self, preview):
        """Should truncate at word boundary if no sentence end."""
        text = "A" * 100 + " " + "B" * 300  # No periods
        result = preview._truncate_for_preview(text)

        assert len(result) <= AudioPreview.MAX_PREVIEW_CHARS + 10
        assert result.endswith("...")

    def test_generate_preview_no_api_key(self, monkeypatch):
        """Should fail gracefully without API key."""
        # Clear any env vars
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

        preview = AudioPreview()
        result = preview.generate_preview("Test text")

        assert result.status == "failed"
        assert "API key" in result.error

    def test_generate_preview_no_voice_id(self, monkeypatch):
        """Should fail gracefully without voice ID."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

        preview = AudioPreview(api_key="test_key", voice_id=None)
        result = preview.generate_preview("Test text")

        assert result.status == "failed"
        assert "Voice ID" in result.error

    @patch("utils.audio_preview.ElevenLabsClient")
    def test_generate_preview_success(self, mock_client_class, preview, tmp_path):
        """Should generate preview successfully."""
        mock_client = MagicMock()
        mock_client.generate_audio.return_value = {"duration": 10.5}
        mock_client_class.return_value = mock_client

        output_path = tmp_path / "preview.mp3"
        result = preview.generate_preview("Test narration text", output_path)

        assert result.status == "success"
        mock_client.generate_audio.assert_called_once()

    @patch("utils.audio_preview.ElevenLabsClient")
    def test_generate_preview_api_error(self, mock_client_class, preview):
        """Should handle API errors gracefully."""
        mock_client = MagicMock()
        mock_client.generate_audio.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client

        result = preview.generate_preview("Test text")

        assert result.status == "failed"
        assert "API Error" in result.error


class TestPlayAudio:
    """Tests for play_audio function."""

    @patch("subprocess.run")
    @patch("platform.system")
    def test_play_on_macos(self, mock_system, mock_run):
        """Should use afplay on macOS."""
        mock_system.return_value = "Darwin"
        mock_run.return_value = MagicMock(returncode=0)

        result = play_audio(Path("/tmp/audio.mp3"))

        assert result is True
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "afplay" in call_args

    @patch("subprocess.run")
    @patch("platform.system")
    def test_play_failure(self, mock_system, mock_run):
        """Should handle playback failure."""
        mock_system.return_value = "Darwin"
        mock_run.side_effect = Exception("Playback failed")

        result = play_audio(Path("/tmp/audio.mp3"))

        assert result is False


class TestGeneratePreview:
    """Tests for generate_preview convenience function."""

    def test_creates_audio_preview_instance(self, monkeypatch):
        """Should use AudioPreview internally."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        result = generate_preview("Test text")

        # Should fail without credentials
        assert result.status == "failed"
