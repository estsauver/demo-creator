"""Tests for parallel audio generation utilities."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.parallel_audio import (
    AudioResult,
    AudioSegment,
    ParallelAudioGenerator,
    generate_audio_parallel,
)


class TestAudioSegment:
    """Tests for AudioSegment dataclass."""

    def test_basic_segment(self):
        """Should represent an audio segment."""
        segment = AudioSegment(
            scene_id=1,
            text="Welcome to the demo",
            output_path=Path("/tmp/audio_1.mp3"),
        )

        assert segment.scene_id == 1
        assert segment.text == "Welcome to the demo"


class TestAudioResult:
    """Tests for AudioResult dataclass."""

    def test_success_result(self):
        """Should represent successful generation."""
        result = AudioResult(
            scene_id=1,
            status="success",
            path=Path("/tmp/audio_1.mp3"),
            duration=10.5,
        )

        assert result.status == "success"
        assert result.duration == 10.5
        assert result.from_cache is False

    def test_cached_result(self):
        """Should indicate cached results."""
        result = AudioResult(
            scene_id=1,
            status="cached",
            path=Path("/tmp/audio_1.mp3"),
            duration=10.5,
            from_cache=True,
        )

        assert result.status == "cached"
        assert result.from_cache is True

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = AudioResult(
            scene_id=1,
            status="success",
            path=Path("/tmp/audio_1.mp3"),
            duration=10.5,
        )

        d = result.to_dict()

        assert d["scene_id"] == 1
        assert d["status"] == "success"
        assert d["path"] == "/tmp/audio_1.mp3"


class TestParallelAudioGenerator:
    """Tests for ParallelAudioGenerator class."""

    def test_init_without_credentials(self, monkeypatch):
        """Should initialize without credentials."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        monkeypatch.delenv("ELEVENLABS_VOICE_ID", raising=False)

        generator = ParallelAudioGenerator(use_cache=False)

        assert generator.api_key is None
        assert generator.voice_id is None

    def test_init_with_credentials(self, monkeypatch):
        """Should initialize with credentials from env."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice")

        generator = ParallelAudioGenerator()

        assert generator.api_key == "test_key"
        assert generator.voice_id == "test_voice"

    def test_init_with_explicit_credentials(self, monkeypatch):
        """Should accept explicit credentials."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        generator = ParallelAudioGenerator(
            api_key="explicit_key",
            voice_id="explicit_voice",
        )

        assert generator.api_key == "explicit_key"
        assert generator.voice_id == "explicit_voice"

    @patch("utils.parallel_audio.ElevenLabsClient")
    def test_generate_single_segment(self, mock_client_class, monkeypatch, tmp_path):
        """Should generate a single audio segment."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice")

        mock_client = MagicMock()
        mock_client.generate_audio.return_value = {"duration": 5.0}
        mock_client_class.return_value = mock_client

        generator = ParallelAudioGenerator(use_cache=False)

        segments = [
            AudioSegment(
                scene_id=1,
                text="Test text",
                output_path=tmp_path / "audio_1.mp3",
            ),
        ]

        results = generator.generate_segments(segments)

        assert len(results) == 1
        assert results[0].status == "success"

    @patch("utils.parallel_audio.ElevenLabsClient")
    def test_generate_multiple_segments(self, mock_client_class, monkeypatch, tmp_path):
        """Should generate multiple segments in parallel."""
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test_key")
        monkeypatch.setenv("ELEVENLABS_VOICE_ID", "test_voice")

        mock_client = MagicMock()
        mock_client.generate_audio.return_value = {"duration": 5.0}
        mock_client_class.return_value = mock_client

        generator = ParallelAudioGenerator(max_workers=2, use_cache=False)

        segments = [
            AudioSegment(
                scene_id=i,
                text=f"Text {i}",
                output_path=tmp_path / f"audio_{i}.mp3",
            )
            for i in range(1, 4)
        ]

        results = generator.generate_segments(segments)

        assert len(results) == 3
        # Results should be sorted by scene_id
        assert results[0].scene_id == 1
        assert results[1].scene_id == 2
        assert results[2].scene_id == 3

    def test_generate_with_progress_callback(self, monkeypatch, tmp_path):
        """Should call progress callback."""
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

        generator = ParallelAudioGenerator(use_cache=False)
        progress_calls = []

        def progress_callback(completed, total):
            progress_calls.append((completed, total))

        # Without credentials, segments will fail but callback still called
        segments = [
            AudioSegment(scene_id=1, text="Test", output_path=tmp_path / "a.mp3"),
        ]

        generator.generate_segments(segments, progress_callback)

        assert len(progress_calls) == 1
        assert progress_calls[0][1] == 1  # total


class TestGenerateAudioParallel:
    """Tests for generate_audio_parallel convenience function."""

    @patch("utils.parallel_audio.ParallelAudioGenerator")
    def test_creates_generator(self, mock_generator_class, tmp_path):
        """Should create ParallelAudioGenerator internally."""
        mock_generator = MagicMock()
        mock_generator.generate_segments.return_value = []
        mock_generator_class.return_value = mock_generator

        segments = [{"scene": 1, "text": "Test"}]
        generate_audio_parallel(segments, tmp_path)

        mock_generator_class.assert_called_once()
        mock_generator.generate_segments.assert_called_once()
