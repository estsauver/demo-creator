"""
HeyGen API client for AI presenter avatar generation.

Generates avatar video overlays that make demos look like they were
recorded by a human presenter.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from .retry import retry, print_retry

logger = logging.getLogger(__name__)


@dataclass
class AvatarConfig:
    """Configuration for avatar generation."""

    avatar_id: str
    voice_id: Optional[str] = None  # Use HeyGen voice or provide audio
    style: str = "picture-in-picture"  # pip, side-by-side, intro-outro
    position: str = "bottom-right"  # For PiP: top-left, top-right, bottom-left, bottom-right
    size: str = "small"  # small, medium, large
    background: str = "transparent"


@dataclass
class AvatarSegment:
    """A segment of avatar video."""

    text: str
    start_time: float
    end_time: Optional[float] = None
    audio_path: Optional[Path] = None


@dataclass
class AvatarResult:
    """Result of avatar generation."""

    status: str  # success, failed, pending
    video_path: Optional[Path] = None
    video_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "video_path": str(self.video_path) if self.video_path else None,
            "video_id": self.video_id,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class HeyGenClient:
    """
    Client for HeyGen avatar video generation API.

    Generates AI presenter videos that can be composited onto demo recordings.
    """

    BASE_URL = "https://api.heygen.com/v2"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize HeyGen client.

        Args:
            api_key: HeyGen API key (defaults to HEYGEN_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("HEYGEN_API_KEY")
        if not self.api_key:
            raise ValueError(
                "HeyGen API key required. Set HEYGEN_API_KEY env var "
                "or pass api_key parameter."
            )

        self._session = requests.Session()
        self._session.headers.update({
            "X-Api-Key": self.api_key,
            "Content-Type": "application/json",
        })

    def list_avatars(self) -> List[Dict[str, Any]]:
        """
        List available avatars.

        Returns:
            List of avatar metadata dicts
        """
        response = self._session.get(f"{self.BASE_URL}/avatars")
        response.raise_for_status()
        return response.json().get("data", {}).get("avatars", [])

    def list_voices(self) -> List[Dict[str, Any]]:
        """
        List available voices.

        Returns:
            List of voice metadata dicts
        """
        response = self._session.get(f"{self.BASE_URL}/voices")
        response.raise_for_status()
        return response.json().get("data", {}).get("voices", [])

    @retry(max_attempts=3, on_retry=print_retry)
    def generate_avatar_video(
        self,
        text: str,
        config: AvatarConfig,
        audio_path: Optional[Path] = None,
    ) -> str:
        """
        Generate an avatar video.

        Args:
            text: Text for the avatar to speak
            config: Avatar configuration
            audio_path: Optional pre-generated audio file (overrides text-to-speech)

        Returns:
            Video ID for polling status
        """
        # Build request payload
        payload = {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": config.avatar_id,
                    "avatar_style": "normal",
                },
                "voice": {
                    "type": "text",
                    "input_text": text,
                },
                "background": {
                    "type": "color",
                    "value": config.background if config.background != "transparent" else "#00FF00",
                },
            }],
            "dimension": {
                "width": 512 if config.size == "small" else 768 if config.size == "medium" else 1024,
                "height": 512 if config.size == "small" else 768 if config.size == "medium" else 1024,
            },
        }

        # Use voice_id if specified
        if config.voice_id:
            payload["video_inputs"][0]["voice"]["voice_id"] = config.voice_id

        # If audio_path provided, use audio URL instead
        if audio_path and audio_path.exists():
            # Note: HeyGen requires audio to be accessible via URL
            # In production, this would upload to a temporary URL
            logger.warning("Audio file path provided but HeyGen requires URL. Using text-to-speech instead.")

        response = self._session.post(
            f"{self.BASE_URL}/video/generate",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()
        video_id = data.get("data", {}).get("video_id")

        if not video_id:
            raise ValueError(f"No video_id in response: {data}")

        logger.info(f"Avatar video generation started: {video_id}")
        return video_id

    def get_video_status(self, video_id: str) -> Dict[str, Any]:
        """
        Get status of video generation.

        Args:
            video_id: Video ID from generate_avatar_video

        Returns:
            Status dict with 'status' and optional 'video_url'
        """
        response = self._session.get(
            f"{self.BASE_URL}/video_status.get",
            params={"video_id": video_id},
            timeout=30,
        )
        response.raise_for_status()
        return response.json().get("data", {})

    def wait_for_video(
        self,
        video_id: str,
        poll_interval: int = 10,
        max_wait: int = 600,
    ) -> Dict[str, Any]:
        """
        Wait for video generation to complete.

        Args:
            video_id: Video ID
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait

        Returns:
            Final status dict with video_url
        """
        elapsed = 0

        while elapsed < max_wait:
            status = self.get_video_status(video_id)

            if status.get("status") == "completed":
                return status
            elif status.get("status") == "failed":
                raise ValueError(f"Video generation failed: {status.get('error')}")

            logger.debug(f"Video status: {status.get('status')} ({elapsed}s elapsed)")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise TimeoutError(f"Video generation timed out after {max_wait}s")

    @retry(max_attempts=3, on_retry=print_retry)
    def download_video(
        self,
        video_url: str,
        output_path: Path,
    ) -> Path:
        """
        Download generated video.

        Args:
            video_url: URL from video status
            output_path: Local path to save video

        Returns:
            Path to downloaded video
        """
        response = requests.get(video_url, stream=True, timeout=60)
        response.raise_for_status()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Downloaded avatar video to {output_path}")
        return output_path

    def generate_and_download(
        self,
        text: str,
        config: AvatarConfig,
        output_path: Path,
    ) -> AvatarResult:
        """
        Generate avatar video and download it.

        Args:
            text: Text for avatar to speak
            config: Avatar configuration
            output_path: Path to save video

        Returns:
            AvatarResult with video path
        """
        try:
            # Start generation
            video_id = self.generate_avatar_video(text, config)

            # Wait for completion
            status = self.wait_for_video(video_id)

            # Download
            video_url = status.get("video_url")
            if not video_url:
                return AvatarResult(
                    status="failed",
                    video_id=video_id,
                    error="No video URL in completed status",
                )

            self.download_video(video_url, output_path)

            # Get duration
            duration = self._get_video_duration(output_path)

            return AvatarResult(
                status="success",
                video_path=output_path,
                video_id=video_id,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.exception("Avatar generation failed")
            return AvatarResult(
                status="failed",
                error=str(e),
            )

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration."""
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(str(video_path))
            duration = clip.duration
            clip.close()
            return duration
        except Exception:
            return None


def composite_avatar_overlay(
    demo_video: Path,
    avatar_video: Path,
    output_path: Path,
    config: AvatarConfig,
) -> Path:
    """
    Composite avatar video onto demo recording.

    Args:
        demo_video: Path to main demo video
        avatar_video: Path to avatar video
        output_path: Path for composited output
        config: Avatar configuration (for position/size)

    Returns:
        Path to composited video
    """
    try:
        from moviepy.editor import VideoFileClip, CompositeVideoClip
    except ImportError:
        raise ImportError("moviepy required. Install with: pip install moviepy")

    # Load videos
    demo = VideoFileClip(str(demo_video))
    avatar = VideoFileClip(str(avatar_video))

    # Resize avatar based on size config
    scale_factors = {"small": 0.15, "medium": 0.25, "large": 0.35}
    scale = scale_factors.get(config.size, 0.15)

    avatar_width = int(demo.w * scale)
    avatar = avatar.resize(width=avatar_width)

    # Position avatar based on config
    padding = 20
    positions = {
        "top-left": (padding, padding),
        "top-right": (demo.w - avatar.w - padding, padding),
        "bottom-left": (padding, demo.h - avatar.h - padding),
        "bottom-right": (demo.w - avatar.w - padding, demo.h - avatar.h - padding),
    }
    position = positions.get(config.position, positions["bottom-right"])

    # Set position
    avatar = avatar.set_position(position)

    # Handle duration mismatch
    if avatar.duration < demo.duration:
        # Loop avatar if shorter
        from moviepy.editor import concatenate_videoclips
        loops_needed = int(demo.duration / avatar.duration) + 1
        avatar = concatenate_videoclips([avatar] * loops_needed)
        avatar = avatar.subclip(0, demo.duration)
    elif avatar.duration > demo.duration:
        avatar = avatar.subclip(0, demo.duration)

    # Composite
    final = CompositeVideoClip([demo, avatar])

    # Export
    final.write_videofile(
        str(output_path),
        codec="libx264",
        audio_codec="aac",
        preset="slow",
        ffmpeg_params=["-crf", "18"],
    )

    # Cleanup
    demo.close()
    avatar.close()
    final.close()

    return output_path


def generate_avatar_segments(
    segments: List[AvatarSegment],
    config: AvatarConfig,
    output_dir: Path,
    api_key: Optional[str] = None,
) -> List[AvatarResult]:
    """
    Generate avatar videos for multiple segments.

    Args:
        segments: List of AvatarSegment objects
        config: Avatar configuration
        output_dir: Directory for output files
        api_key: Optional API key

    Returns:
        List of AvatarResult objects
    """
    client = HeyGenClient(api_key)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for i, segment in enumerate(segments):
        output_path = output_dir / f"avatar_segment_{i + 1}.mp4"

        result = client.generate_and_download(
            text=segment.text,
            config=config,
            output_path=output_path,
        )
        results.append(result)

    return results


def check_heygen_available() -> bool:
    """Check if HeyGen API key is configured."""
    return bool(os.getenv("HEYGEN_API_KEY"))


def get_default_avatar_id() -> Optional[str]:
    """Get default avatar ID from environment."""
    return os.getenv("HEYGEN_AVATAR_ID")
