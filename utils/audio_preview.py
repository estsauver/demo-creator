"""
Audio preview utilities for demo-creator.

Generates short audio previews before committing to full narration generation.
Helps users verify voice settings and narration style before expensive TTS calls.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .elevenlabs_client import ElevenLabsClient

logger = logging.getLogger(__name__)


@dataclass
class AudioPreviewResult:
    """Result of audio preview generation."""

    status: str  # success, failed
    audio_path: Optional[Path] = None
    duration_seconds: Optional[float] = None
    voice_name: Optional[str] = None
    error: Optional[str] = None


class AudioPreview:
    """
    Generates audio previews for narration verification.

    Creates short ~15 second previews of the first narration segment
    so users can confirm voice and style before full generation.
    """

    MAX_PREVIEW_CHARS = 300  # Roughly 15-20 seconds of speech
    MAX_PREVIEW_DURATION = 20.0  # Seconds

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
    ):
        """
        Initialize audio preview generator.

        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID to use
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")

    def generate_preview(
        self,
        text: str,
        output_path: Optional[Path] = None,
    ) -> AudioPreviewResult:
        """
        Generate a preview audio clip.

        Args:
            text: Full narration text (will be truncated for preview)
            output_path: Optional path for output (uses temp file if not provided)

        Returns:
            AudioPreviewResult
        """
        if not self.api_key:
            return AudioPreviewResult(
                status="failed",
                error="ElevenLabs API key not configured",
            )

        if not self.voice_id:
            return AudioPreviewResult(
                status="failed",
                error="Voice ID not configured",
            )

        # Truncate text for preview
        preview_text = self._truncate_for_preview(text)

        # Generate output path
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix=".mp3", prefix="preview_"))

        try:
            client = ElevenLabsClient(
                api_key=self.api_key,
                voice_id=self.voice_id,
            )

            result = client.generate_audio(
                text=preview_text,
                output_path=str(output_path),
            )

            return AudioPreviewResult(
                status="success",
                audio_path=output_path,
                duration_seconds=result.get("duration"),
            )

        except Exception as e:
            logger.exception("Failed to generate audio preview")
            return AudioPreviewResult(
                status="failed",
                error=str(e),
            )

    def _truncate_for_preview(self, text: str) -> str:
        """
        Truncate text to preview length while keeping complete sentences.

        Args:
            text: Full text

        Returns:
            Truncated text ending at a sentence boundary
        """
        if len(text) <= self.MAX_PREVIEW_CHARS:
            return text

        # Find last sentence end within limit
        truncated = text[:self.MAX_PREVIEW_CHARS]

        # Look for sentence endings
        for end_char in [". ", "! ", "? "]:
            last_end = truncated.rfind(end_char)
            if last_end > len(truncated) // 2:  # Don't truncate too much
                return truncated[:last_end + 1]

        # Fallback: truncate at word boundary
        last_space = truncated.rfind(" ")
        if last_space > 0:
            return truncated[:last_space] + "..."

        return truncated + "..."

    def generate_preview_from_narration(
        self,
        narration_path: Path,
        output_dir: Path,
    ) -> AudioPreviewResult:
        """
        Generate preview from a narration script file.

        Extracts the first segment(s) for preview.

        Args:
            narration_path: Path to narration script (JSON or TXT)
            output_dir: Directory for output

        Returns:
            AudioPreviewResult
        """
        import json

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Try to read as JSON first
            with open(narration_path) as f:
                content = f.read()

            if narration_path.suffix == ".json":
                data = json.loads(content)
                segments = data.get("segments", [])

                if not segments:
                    return AudioPreviewResult(
                        status="failed",
                        error="No segments found in narration file",
                    )

                # Get first segment(s) up to preview limit
                preview_text = ""
                for segment in segments:
                    segment_text = segment.get("text", "")
                    if len(preview_text) + len(segment_text) < self.MAX_PREVIEW_CHARS:
                        preview_text += segment_text + " "
                    else:
                        break

                preview_text = preview_text.strip()
            else:
                # Plain text file
                preview_text = self._truncate_for_preview(content)

            return self.generate_preview(
                text=preview_text,
                output_path=output_dir / "preview_audio.mp3",
            )

        except Exception as e:
            logger.exception("Failed to generate preview from narration")
            return AudioPreviewResult(
                status="failed",
                error=str(e),
            )


def play_audio(audio_path: Path) -> bool:
    """
    Play an audio file using system audio player.

    Args:
        audio_path: Path to audio file

    Returns:
        True if playback succeeded
    """
    import platform

    system = platform.system()

    try:
        if system == "Darwin":  # macOS
            subprocess.run(["afplay", str(audio_path)], check=True)
        elif system == "Linux":
            # Try various players
            for player in ["aplay", "paplay", "mpv", "ffplay"]:
                try:
                    subprocess.run([player, str(audio_path)], check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False
        elif system == "Windows":
            import winsound
            winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
        else:
            logger.warning(f"Unsupported platform for audio playback: {system}")
            return False

        return True

    except Exception as e:
        logger.warning(f"Failed to play audio: {e}")
        return False


def generate_preview(
    text: str,
    output_path: Optional[Path] = None,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> AudioPreviewResult:
    """
    Convenience function to generate audio preview.

    Args:
        text: Text to generate preview for
        output_path: Optional output path
        api_key: Optional API key
        voice_id: Optional voice ID

    Returns:
        AudioPreviewResult
    """
    preview = AudioPreview(api_key=api_key, voice_id=voice_id)
    return preview.generate_preview(text, output_path)


def generate_and_play_preview(
    text: str,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> AudioPreviewResult:
    """
    Generate and immediately play an audio preview.

    Args:
        text: Text to preview
        api_key: Optional API key
        voice_id: Optional voice ID

    Returns:
        AudioPreviewResult
    """
    result = generate_preview(text, api_key=api_key, voice_id=voice_id)

    if result.status == "success" and result.audio_path:
        play_audio(result.audio_path)

    return result
