"""
Parallel audio generation for demo-creator.

Generates multiple audio segments concurrently to reduce total generation time.
"""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .cache import DemoCache
from .elevenlabs_client import ElevenLabsClient

logger = logging.getLogger(__name__)


@dataclass
class AudioSegment:
    """An audio segment to generate."""

    scene_id: int
    text: str
    output_path: Path


@dataclass
class AudioResult:
    """Result of audio generation."""

    scene_id: int
    status: str  # success, failed, cached
    path: Optional[Path] = None
    duration: Optional[float] = None
    error: Optional[str] = None
    from_cache: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "status": self.status,
            "path": str(self.path) if self.path else None,
            "duration": self.duration,
            "error": self.error,
            "from_cache": self.from_cache,
        }


class ParallelAudioGenerator:
    """
    Generates multiple audio segments in parallel.

    Uses thread pool for concurrent API calls, with optional caching
    to skip regenerating unchanged segments.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        max_workers: int = 4,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None,
    ):
        """
        Initialize parallel audio generator.

        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID to use
            max_workers: Maximum concurrent generations
            use_cache: Whether to use caching
            cache_dir: Directory for cache (defaults to .demo/.cache)
        """
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.max_workers = max_workers
        self.use_cache = use_cache
        self.cache = DemoCache(cache_dir or Path(".demo/.cache")) if use_cache else None

    def generate_segments(
        self,
        segments: List[AudioSegment],
        progress_callback: Optional[callable] = None,
    ) -> List[AudioResult]:
        """
        Generate multiple audio segments in parallel.

        Args:
            segments: List of AudioSegment objects
            progress_callback: Optional callback(completed, total) for progress updates

        Returns:
            List of AudioResult objects
        """
        results = []
        total = len(segments)
        completed = 0

        # Check cache first
        segments_to_generate = []
        for segment in segments:
            if self.use_cache and self.cache:
                cached = self.cache.get_audio(segment.text, self.voice_id)
                if cached:
                    # Copy cached audio to output path
                    segment.output_path.parent.mkdir(parents=True, exist_ok=True)
                    segment.output_path.write_bytes(cached["data"])

                    results.append(AudioResult(
                        scene_id=segment.scene_id,
                        status="cached",
                        path=segment.output_path,
                        duration=cached.get("duration"),
                        from_cache=True,
                    ))
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)
                    continue

            segments_to_generate.append(segment)

        if not segments_to_generate:
            return results

        # Generate remaining segments in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_segment = {
                executor.submit(self._generate_single, seg): seg
                for seg in segments_to_generate
            }

            for future in as_completed(future_to_segment):
                segment = future_to_segment[future]
                try:
                    result = future.result()
                    results.append(result)

                    # Cache successful results
                    if (
                        result.status == "success"
                        and self.use_cache
                        and self.cache
                        and result.path
                    ):
                        audio_data = result.path.read_bytes()
                        self.cache.cache_audio(
                            segment.text,
                            audio_data,
                            self.voice_id,
                            result.duration,
                        )

                except Exception as e:
                    logger.exception(f"Failed to generate audio for scene {segment.scene_id}")
                    results.append(AudioResult(
                        scene_id=segment.scene_id,
                        status="failed",
                        error=str(e),
                    ))

                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

        # Sort by scene_id
        results.sort(key=lambda r: r.scene_id)
        return results

    def _generate_single(self, segment: AudioSegment) -> AudioResult:
        """Generate a single audio segment."""
        try:
            client = ElevenLabsClient(
                api_key=self.api_key,
                voice_id=self.voice_id,
            )

            segment.output_path.parent.mkdir(parents=True, exist_ok=True)

            result = client.generate_audio(
                text=segment.text,
                output_path=str(segment.output_path),
            )

            return AudioResult(
                scene_id=segment.scene_id,
                status="success",
                path=segment.output_path,
                duration=result.get("duration"),
            )

        except Exception as e:
            logger.exception(f"Audio generation failed for scene {segment.scene_id}")
            return AudioResult(
                scene_id=segment.scene_id,
                status="failed",
                error=str(e),
            )


async def generate_audio_parallel_async(
    segments: List[Dict[str, Any]],
    output_dir: Path,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    max_concurrent: int = 4,
) -> List[AudioResult]:
    """
    Async version of parallel audio generation.

    Args:
        segments: List of segment dicts with 'scene', 'text' keys
        output_dir: Output directory for audio files
        api_key: Optional ElevenLabs API key
        voice_id: Optional voice ID
        max_concurrent: Maximum concurrent generations

    Returns:
        List of AudioResult objects
    """
    output_dir = Path(output_dir)

    audio_segments = [
        AudioSegment(
            scene_id=seg["scene"],
            text=seg["text"],
            output_path=output_dir / f"audio_scene_{seg['scene']}.mp3",
        )
        for seg in segments
    ]

    generator = ParallelAudioGenerator(
        api_key=api_key,
        voice_id=voice_id,
        max_workers=max_concurrent,
    )

    # Run in thread pool since ElevenLabs client is synchronous
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        generator.generate_segments,
        audio_segments,
        None,
    )

    return results


def generate_audio_parallel(
    segments: List[Dict[str, Any]],
    output_dir: Path,
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    max_workers: int = 4,
    use_cache: bool = True,
    progress_callback: Optional[callable] = None,
) -> List[AudioResult]:
    """
    Generate multiple audio segments in parallel.

    Args:
        segments: List of segment dicts with 'scene', 'text' keys
        output_dir: Output directory for audio files
        api_key: Optional ElevenLabs API key
        voice_id: Optional voice ID
        max_workers: Maximum concurrent generations
        use_cache: Whether to use caching
        progress_callback: Optional callback(completed, total)

    Returns:
        List of AudioResult objects
    """
    output_dir = Path(output_dir)

    audio_segments = [
        AudioSegment(
            scene_id=seg["scene"],
            text=seg["text"],
            output_path=output_dir / f"audio_scene_{seg['scene']}.mp3",
        )
        for seg in segments
    ]

    generator = ParallelAudioGenerator(
        api_key=api_key,
        voice_id=voice_id,
        max_workers=max_workers,
        use_cache=use_cache,
        cache_dir=output_dir.parent / ".cache" if use_cache else None,
    )

    return generator.generate_segments(audio_segments, progress_callback)
