"""Tests for HeyGen client utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.heygen_client import (
    AvatarConfig,
    AvatarResult,
    AvatarSegment,
    HeyGenClient,
    check_heygen_available,
    get_default_avatar_id,
)


class TestAvatarConfig:
    """Tests for AvatarConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = AvatarConfig(avatar_id="test_avatar")

        assert config.avatar_id == "test_avatar"
        assert config.voice_id is None
        assert config.style == "picture-in-picture"
        assert config.position == "bottom-right"
        assert config.size == "small"
        assert config.background == "transparent"

    def test_custom_values(self):
        """Should accept custom values."""
        config = AvatarConfig(
            avatar_id="custom_avatar",
            voice_id="custom_voice",
            style="side-by-side",
            position="top-left",
            size="large",
        )

        assert config.avatar_id == "custom_avatar"
        assert config.voice_id == "custom_voice"
        assert config.style == "side-by-side"
        assert config.position == "top-left"
        assert config.size == "large"


class TestAvatarSegment:
    """Tests for AvatarSegment dataclass."""

    def test_basic_segment(self):
        """Should represent an avatar segment."""
        segment = AvatarSegment(
            text="Welcome to our demo",
            start_time=0.0,
            end_time=5.0,
        )

        assert segment.text == "Welcome to our demo"
        assert segment.start_time == 0.0
        assert segment.end_time == 5.0

    def test_segment_with_audio(self):
        """Should support pre-generated audio."""
        segment = AvatarSegment(
            text="Narration text",
            start_time=10.0,
            audio_path=Path("/tmp/narration.mp3"),
        )

        assert segment.audio_path == Path("/tmp/narration.mp3")


class TestAvatarResult:
    """Tests for AvatarResult dataclass."""

    def test_success_result(self):
        """Should represent successful generation."""
        result = AvatarResult(
            status="success",
            video_path=Path("/tmp/avatar.mp4"),
            video_id="vid_123",
            duration_seconds=15.0,
        )

        assert result.status == "success"
        assert result.video_path == Path("/tmp/avatar.mp4")
        assert result.video_id == "vid_123"
        assert result.duration_seconds == 15.0

    def test_failed_result(self):
        """Should represent failed generation."""
        result = AvatarResult(
            status="failed",
            error="API rate limit exceeded",
        )

        assert result.status == "failed"
        assert result.error == "API rate limit exceeded"
        assert result.video_path is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = AvatarResult(
            status="success",
            video_path=Path("/tmp/avatar.mp4"),
            video_id="vid_123",
            duration_seconds=15.0,
        )

        d = result.to_dict()

        assert d["status"] == "success"
        assert d["video_path"] == "/tmp/avatar.mp4"
        assert d["video_id"] == "vid_123"


class TestHeyGenClient:
    """Tests for HeyGenClient class."""

    def test_init_without_api_key(self, monkeypatch):
        """Should raise error without API key."""
        monkeypatch.delenv("HEYGEN_API_KEY", raising=False)

        with pytest.raises(ValueError) as exc_info:
            HeyGenClient()

        assert "API key required" in str(exc_info.value)

    def test_init_with_api_key(self, monkeypatch):
        """Should initialize with API key."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        client = HeyGenClient()

        assert client.api_key == "test_key"

    def test_init_with_explicit_api_key(self, monkeypatch):
        """Should accept explicit API key."""
        monkeypatch.delenv("HEYGEN_API_KEY", raising=False)

        client = HeyGenClient(api_key="explicit_key")

        assert client.api_key == "explicit_key"

    @patch("requests.Session.get")
    def test_list_avatars(self, mock_get, monkeypatch):
        """Should list available avatars."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "avatars": [
                    {"id": "avatar1", "name": "Avatar 1"},
                    {"id": "avatar2", "name": "Avatar 2"},
                ]
            }
        }
        mock_get.return_value = mock_response

        client = HeyGenClient()
        avatars = client.list_avatars()

        assert len(avatars) == 2
        assert avatars[0]["id"] == "avatar1"

    @patch("requests.Session.get")
    def test_list_voices(self, mock_get, monkeypatch):
        """Should list available voices."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "voices": [
                    {"id": "voice1", "name": "Voice 1"},
                ]
            }
        }
        mock_get.return_value = mock_response

        client = HeyGenClient()
        voices = client.list_voices()

        assert len(voices) == 1
        assert voices[0]["id"] == "voice1"

    @patch("requests.Session.post")
    def test_generate_avatar_video(self, mock_post, monkeypatch):
        """Should generate avatar video."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {"video_id": "vid_abc123"}
        }
        mock_post.return_value = mock_response

        client = HeyGenClient()
        config = AvatarConfig(avatar_id="test_avatar")

        video_id = client.generate_avatar_video(
            text="Hello world",
            config=config,
        )

        assert video_id == "vid_abc123"
        mock_post.assert_called_once()

    @patch("requests.Session.get")
    def test_get_video_status(self, mock_get, monkeypatch):
        """Should get video generation status."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": {
                "status": "completed",
                "video_url": "https://example.com/video.mp4",
            }
        }
        mock_get.return_value = mock_response

        client = HeyGenClient()
        status = client.get_video_status("vid_abc123")

        assert status["status"] == "completed"
        assert status["video_url"] == "https://example.com/video.mp4"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_check_heygen_available_true(self, monkeypatch):
        """Should return True when API key is set."""
        monkeypatch.setenv("HEYGEN_API_KEY", "test_key")

        assert check_heygen_available() is True

    def test_check_heygen_available_false(self, monkeypatch):
        """Should return False when API key is not set."""
        monkeypatch.delenv("HEYGEN_API_KEY", raising=False)

        assert check_heygen_available() is False

    def test_get_default_avatar_id(self, monkeypatch):
        """Should return default avatar ID from env."""
        monkeypatch.setenv("HEYGEN_AVATAR_ID", "default_avatar")

        assert get_default_avatar_id() == "default_avatar"

    def test_get_default_avatar_id_not_set(self, monkeypatch):
        """Should return None when not set."""
        monkeypatch.delenv("HEYGEN_AVATAR_ID", raising=False)

        assert get_default_avatar_id() is None
