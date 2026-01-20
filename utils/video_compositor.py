"""
Video compositing utilities for merging video and audio.

Handles combining raw screen recordings with generated narration audio.
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False


class VideoCompositor:
    """
    Handles compositing video and audio tracks.

    Supports both moviepy (preferred) and ffmpeg CLI (fallback).
    """

    def __init__(self, use_moviepy: bool = True):
        """
        Initialize compositor.

        Args:
            use_moviepy: Use moviepy if available (default True)
        """
        self.use_moviepy = use_moviepy and MOVIEPY_AVAILABLE

    def composite(
        self,
        video_path: str,
        audio_clips: List[Dict[str, Any]],
        scene_timings: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Composite video with audio narration.

        Args:
            video_path: Path to raw recording video
            audio_clips: List of audio clip metadata
                [{"scene": 1, "path": "audio_scene_1.mp3", "duration": 28}, ...]
            scene_timings: List of scene timing data
                [{"scene": 1, "start": 0, "end": 30}, ...]
            output_path: Path for final video

        Returns:
            Path to final video
        """
        if self.use_moviepy:
            return self._composite_moviepy(
                video_path, audio_clips, scene_timings, output_path
            )
        else:
            return self._composite_ffmpeg(
                video_path, audio_clips, scene_timings, output_path
            )

    def _composite_moviepy(
        self,
        video_path: str,
        audio_clips: List[Dict[str, Any]],
        scene_timings: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Composite using moviepy library.

        Args:
            video_path: Path to video
            audio_clips: Audio clip metadata
            scene_timings: Scene timing data
            output_path: Output path

        Returns:
            Path to final video
        """
        if not MOVIEPY_AVAILABLE:
            raise ImportError("moviepy not available. Install with: pip install moviepy")

        # Load video
        video = VideoFileClip(video_path)

        # Get demo directory from video path
        demo_dir = Path(video_path).parent

        # Load and position audio clips
        audio_elements = []
        for clip_meta in audio_clips:
            scene_id = clip_meta["scene"]

            # Find matching scene timing
            scene_timing = next(
                (s for s in scene_timings if s["scene"] == scene_id),
                None
            )

            if scene_timing is None:
                print(f"Warning: No timing found for scene {scene_id}, skipping audio")
                continue

            # Load audio and set start time
            audio_path = demo_dir / clip_meta["path"]
            if not audio_path.exists():
                print(f"Warning: Audio file not found: {audio_path}, skipping")
                continue

            audio = AudioFileClip(str(audio_path))
            audio = audio.set_start(scene_timing["start"])
            audio_elements.append(audio)

        # Create composite audio
        if audio_elements:
            composite_audio = CompositeAudioClip(audio_elements)

            # Merge video with audio
            final = video.set_audio(composite_audio)
        else:
            print("Warning: No audio tracks to composite")
            final = video

        # Export with high quality settings
        final.write_videofile(
            output_path,
            codec="libx264",
            audio_codec="aac",
            audio_bitrate="192k",
            preset="slow",
            ffmpeg_params=["-crf", "18"],
        )

        # Cleanup
        video.close()
        for elem in audio_elements:
            elem.close()
        if audio_elements:
            composite_audio.close()

        return output_path

    def _composite_ffmpeg(
        self,
        video_path: str,
        audio_clips: List[Dict[str, Any]],
        scene_timings: List[Dict[str, Any]],
        output_path: str,
    ) -> str:
        """
        Composite using ffmpeg CLI (fallback).

        Args:
            video_path: Path to video
            audio_clips: Audio clip metadata
            scene_timings: Scene timing data
            output_path: Output path

        Returns:
            Path to final video
        """
        demo_dir = Path(video_path).parent

        # Build ffmpeg command
        cmd = ["ffmpeg", "-i", video_path]

        # Add audio inputs
        audio_inputs = []
        for clip_meta in audio_clips:
            audio_path = demo_dir / clip_meta["path"]
            if audio_path.exists():
                cmd.extend(["-i", str(audio_path)])
                audio_inputs.append(clip_meta)

        if not audio_inputs:
            # No audio, just copy video
            cmd.extend(["-c", "copy", output_path])
            subprocess.run(cmd, check=True)
            return output_path

        # Build filter_complex for audio delays and mixing
        filter_parts = []
        for i, clip_meta in enumerate(audio_inputs):
            scene_id = clip_meta["scene"]
            scene_timing = next(
                (s for s in scene_timings if s["scene"] == scene_id),
                None
            )

            if scene_timing:
                # Delay in milliseconds
                delay_ms = int(scene_timing["start"] * 1000)
                filter_parts.append(f"[{i+1}:a]adelay={delay_ms}[a{i+1}]")

        # Mix all audio tracks
        audio_refs = "".join(f"[a{i+1}]" for i in range(len(audio_inputs)))
        filter_parts.append(f"{audio_refs}amix={len(audio_inputs)}[a]")

        filter_complex = ";".join(filter_parts)

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "slow",
            "-c:a", "aac",
            "-b:a", "192k",
            output_path,
        ])

        subprocess.run(cmd, check=True)

        return output_path


def composite_demo_video(
    video_path: str,
    audio_clips: List[Dict[str, Any]],
    scene_timings: List[Dict[str, Any]],
    output_path: str,
    use_moviepy: bool = True,
) -> str:
    """
    Convenience function to composite a demo video.

    Args:
        video_path: Path to raw recording
        audio_clips: Audio clip metadata
        scene_timings: Scene timing data
        output_path: Output path
        use_moviepy: Prefer moviepy over ffmpeg

    Returns:
        Path to final video
    """
    compositor = VideoCompositor(use_moviepy=use_moviepy)
    return compositor.composite(video_path, audio_clips, scene_timings, output_path)
