"""
ElevenLabs API client for generating narration audio.

Handles text-to-speech conversion using ElevenLabs API with retry logic
for transient failures (rate limits, timeouts, network issues).
"""

import os
import time
import requests
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from moviepy.editor import AudioFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


def _is_retryable_error(response: requests.Response) -> bool:
    """
    Check if an HTTP error is retryable.

    Args:
        response: HTTP response object

    Returns:
        True if the error is transient and can be retried
    """
    # Rate limit errors (429) and server errors (5xx) are retryable
    if response.status_code == 429:  # Too Many Requests
        return True
    if 500 <= response.status_code < 600:  # Server errors
        return True
    return False


class ElevenLabsClient:
    """
    Client for ElevenLabs text-to-speech API.

    Generates audio clips for demo narration.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model_id: str = "eleven_multilingual_v2",
    ):
        """
        Initialize ElevenLabs client.

        Args:
            api_key: ElevenLabs API key (defaults to env var ELEVENLABS_API_KEY)
            voice_id: Voice ID to use (defaults to env var ELEVENLABS_VOICE_ID)
            model_id: Model ID (default: eleven_multilingual_v2)
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key required. Set ELEVENLABS_API_KEY env var "
                "or pass api_key parameter."
            )

        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        if not self.voice_id:
            raise ValueError(
                "Voice ID required. Set ELEVENLABS_VOICE_ID env var "
                "or pass voice_id parameter."
            )

        self.model_id = model_id
        self.base_url = "https://api.elevenlabs.io/v1"

    def generate_audio(
        self,
        text: str,
        output_path: str,
        stability: float = 0.5,
        similarity_boost: float = 0.75,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate audio from text and save to file with retry logic.

        Handles transient failures (rate limits, timeouts, network issues) with
        exponential backoff: 1s, 2s, 4s between retries.

        Args:
            text: Text to convert to speech
            output_path: Path to save the audio file
            stability: Voice stability (0-1, default 0.5)
            similarity_boost: Voice similarity boost (0-1, default 0.75)
            max_retries: Maximum number of retry attempts (default 3)

        Returns:
            Dict with 'path' and 'duration' (in seconds)

        Raises:
            requests.HTTPError: If API request fails after all retries
        """
        url = f"{self.base_url}/text-to-speech/{self.voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        data = {
            "text": text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
            },
        }

        # Make API request with retry logic
        last_exception = None
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=data, headers=headers, timeout=30)
                response.raise_for_status()
                break  # Success - exit retry loop

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                    print(f"  ⚠️ Request timeout, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise

            except requests.exceptions.HTTPError as e:
                last_exception = e
                if _is_retryable_error(response):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
                        print(f"  ⚠️ API error {response.status_code}, retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                        time.sleep(wait_time)
                    else:
                        raise
                else:
                    # Non-retryable error (e.g., 400 Bad Request)
                    raise

        # Save audio file
        output_path_obj = Path(output_path)
        output_path_obj.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "wb") as f:
            f.write(response.content)

        # Get duration
        duration = self._get_audio_duration(output_path)

        return {
            "path": output_path,
            "duration": duration,
        }

    def _get_audio_duration(self, audio_path: str) -> float:
        """
        Get the duration of an audio file in seconds.

        Args:
            audio_path: Path to audio file

        Returns:
            Duration in seconds
        """
        if not MOVIEPY_AVAILABLE:
            # Fallback: estimate from file size (very rough)
            # MP3 typically ~16KB per second at 128kbps
            file_size = Path(audio_path).stat().st_size
            return file_size / 16000

        # Use moviepy for accurate duration
        clip = AudioFileClip(audio_path)
        duration = clip.duration
        clip.close()

        return duration


def generate_scene_audio(
    text: str,
    scene_id: int,
    demo_id: str,
    output_dir: str = ".demo",
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to generate audio for a scene.

    Args:
        text: Narration text
        scene_id: Scene number
        demo_id: Demo identifier
        output_dir: Base output directory
        api_key: Optional ElevenLabs API key
        voice_id: Optional voice ID

    Returns:
        Dict with 'scene', 'path', and 'duration'
    """
    client = ElevenLabsClient(api_key=api_key, voice_id=voice_id)

    output_path = f"{output_dir}/{demo_id}/audio_scene_{scene_id}.mp3"

    result = client.generate_audio(text, output_path)

    return {
        "scene": scene_id,
        "path": f"audio_scene_{scene_id}.mp3",
        "duration": result["duration"],
    }


def check_api_key() -> bool:
    """
    Check if ElevenLabs API key is available.

    Returns:
        True if API key is set
    """
    return bool(os.getenv("ELEVENLABS_API_KEY"))


def get_voice_id() -> Optional[str]:
    """
    Get the configured ElevenLabs voice ID.

    Returns:
        Voice ID or None
    """
    return os.getenv("ELEVENLABS_VOICE_ID")
