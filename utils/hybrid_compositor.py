"""
Hybrid demo compositing for combining terminal and browser recordings.

Supports split-screen, picture-in-picture, and sequential layouts.
"""

import logging
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LayoutType(Enum):
    """Layout types for hybrid demos."""
    SPLIT = "split"           # Side-by-side split screen
    SEQUENTIAL = "sequential"  # One after the other
    PIP = "pip"               # Picture-in-picture


@dataclass
class HybridConfig:
    """Configuration for hybrid demo compositing."""

    layout: LayoutType = LayoutType.SPLIT
    terminal_position: str = "left"  # left, right, top, bottom
    terminal_width_percent: int = 40  # For split layout
    pip_position: str = "bottom-right"  # For PiP layout
    pip_scale: float = 0.3  # For PiP layout
    output_width: int = 1920
    output_height: int = 1080
    background_color: str = "#1e1e1e"


@dataclass
class HybridResult:
    """Result of hybrid compositing."""

    status: str  # success, failed
    video_path: Optional[Path] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "video_path": str(self.video_path) if self.video_path else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class HybridCompositor:
    """
    Composites terminal and browser recordings into hybrid demos.

    Supports multiple layout options for combining different
    recording types.
    """

    def __init__(self, config: Optional[HybridConfig] = None):
        """
        Initialize hybrid compositor.

        Args:
            config: Compositing configuration
        """
        self.config = config or HybridConfig()

    def composite(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path] = None,
    ) -> HybridResult:
        """
        Composite terminal and browser videos.

        Args:
            terminal_video: Path to terminal recording
            browser_video: Path to browser recording
            output_path: Path for output video
            audio_path: Optional audio track to add

        Returns:
            HybridResult
        """
        try:
            if self.config.layout == LayoutType.SPLIT:
                return self._composite_split(
                    terminal_video, browser_video, output_path, audio_path
                )
            elif self.config.layout == LayoutType.PIP:
                return self._composite_pip(
                    terminal_video, browser_video, output_path, audio_path
                )
            elif self.config.layout == LayoutType.SEQUENTIAL:
                return self._composite_sequential(
                    terminal_video, browser_video, output_path, audio_path
                )
            else:
                return HybridResult(
                    status="failed",
                    error=f"Unknown layout type: {self.config.layout}",
                )
        except Exception as e:
            logger.exception("Hybrid compositing failed")
            return HybridResult(
                status="failed",
                error=str(e),
            )

    def _composite_split(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path],
    ) -> HybridResult:
        """Composite with split-screen layout."""
        try:
            from moviepy.editor import (
                VideoFileClip,
                CompositeVideoClip,
                ColorClip,
                concatenate_audioclips,
                AudioFileClip,
            )
        except ImportError:
            return self._composite_split_ffmpeg(
                terminal_video, browser_video, output_path, audio_path
            )

        # Load videos
        terminal = VideoFileClip(str(terminal_video))
        browser = VideoFileClip(str(browser_video))

        # Calculate dimensions
        width = self.config.output_width
        height = self.config.output_height

        if self.config.terminal_position in ("left", "right"):
            terminal_width = int(width * self.config.terminal_width_percent / 100)
            browser_width = width - terminal_width

            # Resize videos
            terminal_resized = terminal.resize(height=height)
            if terminal_resized.w > terminal_width:
                terminal_resized = terminal_resized.resize(width=terminal_width)

            browser_resized = browser.resize(height=height)
            if browser_resized.w > browser_width:
                browser_resized = browser_resized.resize(width=browser_width)

            # Position
            if self.config.terminal_position == "left":
                terminal_pos = (0, (height - terminal_resized.h) // 2)
                browser_pos = (terminal_width, (height - browser_resized.h) // 2)
            else:
                browser_pos = (0, (height - browser_resized.h) // 2)
                terminal_pos = (browser_width, (height - terminal_resized.h) // 2)
        else:
            # Top/bottom split
            terminal_height = int(height * self.config.terminal_width_percent / 100)
            browser_height = height - terminal_height

            terminal_resized = terminal.resize(width=width)
            if terminal_resized.h > terminal_height:
                terminal_resized = terminal_resized.resize(height=terminal_height)

            browser_resized = browser.resize(width=width)
            if browser_resized.h > browser_height:
                browser_resized = browser_resized.resize(height=browser_height)

            if self.config.terminal_position == "top":
                terminal_pos = ((width - terminal_resized.w) // 2, 0)
                browser_pos = ((width - browser_resized.w) // 2, terminal_height)
            else:
                browser_pos = ((width - browser_resized.w) // 2, 0)
                terminal_pos = ((width - terminal_resized.w) // 2, browser_height)

        # Match durations
        max_duration = max(terminal.duration, browser.duration)
        terminal_resized = terminal_resized.set_position(terminal_pos)
        browser_resized = browser_resized.set_position(browser_pos)

        # Create background
        background = ColorClip(
            size=(width, height),
            color=self._hex_to_rgb(self.config.background_color),
        ).set_duration(max_duration)

        # Composite
        final = CompositeVideoClip(
            [background, terminal_resized, browser_resized],
            size=(width, height),
        )

        # Add audio if provided
        if audio_path and audio_path.exists():
            audio = AudioFileClip(str(audio_path))
            final = final.set_audio(audio)

        # Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            preset="slow",
            ffmpeg_params=["-crf", "18"],
        )

        duration = final.duration

        # Cleanup
        terminal.close()
        browser.close()
        final.close()

        return HybridResult(
            status="success",
            video_path=output_path,
            duration_seconds=duration,
        )

    def _composite_split_ffmpeg(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path],
    ) -> HybridResult:
        """Composite split-screen using ffmpeg (fallback)."""
        width = self.config.output_width
        height = self.config.output_height
        terminal_width = int(width * self.config.terminal_width_percent / 100)
        browser_width = width - terminal_width

        # Build ffmpeg filter
        if self.config.terminal_position == "left":
            filter_complex = (
                f"[0:v]scale={terminal_width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={terminal_width}:{height}:(ow-iw)/2:(oh-ih)/2:color={self.config.background_color}[t];"
                f"[1:v]scale={browser_width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={browser_width}:{height}:(ow-iw)/2:(oh-ih)/2:color={self.config.background_color}[b];"
                f"[t][b]hstack=inputs=2[v]"
            )
        else:
            filter_complex = (
                f"[1:v]scale={browser_width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={browser_width}:{height}:(ow-iw)/2:(oh-ih)/2:color={self.config.background_color}[b];"
                f"[0:v]scale={terminal_width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={terminal_width}:{height}:(ow-iw)/2:(oh-ih)/2:color={self.config.background_color}[t];"
                f"[b][t]hstack=inputs=2[v]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(terminal_video),
            "-i", str(browser_video),
        ]

        if audio_path and audio_path.exists():
            cmd.extend(["-i", str(audio_path)])
            filter_complex += ";[2:a]anull[a]"
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[v]",
                "-map", "[a]",
            ])
        else:
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[v]",
            ])

        cmd.extend([
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "slow",
            "-c:a", "aac",
            str(output_path),
        ])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True, capture_output=True)

        duration = self._get_video_duration(output_path)

        return HybridResult(
            status="success",
            video_path=output_path,
            duration_seconds=duration,
        )

    def _composite_pip(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path],
    ) -> HybridResult:
        """Composite with picture-in-picture layout."""
        try:
            from moviepy.editor import VideoFileClip, CompositeVideoClip, AudioFileClip
        except ImportError:
            return HybridResult(
                status="failed",
                error="moviepy required for PiP layout",
            )

        # Load videos
        main = VideoFileClip(str(browser_video))
        pip = VideoFileClip(str(terminal_video))

        # Scale PiP
        pip_width = int(main.w * self.config.pip_scale)
        pip_resized = pip.resize(width=pip_width)

        # Position PiP
        padding = 20
        positions = {
            "top-left": (padding, padding),
            "top-right": (main.w - pip_resized.w - padding, padding),
            "bottom-left": (padding, main.h - pip_resized.h - padding),
            "bottom-right": (main.w - pip_resized.w - padding, main.h - pip_resized.h - padding),
        }
        pos = positions.get(self.config.pip_position, positions["bottom-right"])
        pip_resized = pip_resized.set_position(pos)

        # Match durations
        if pip_resized.duration < main.duration:
            from moviepy.editor import concatenate_videoclips
            loops = int(main.duration / pip_resized.duration) + 1
            pip_resized = concatenate_videoclips([pip_resized] * loops)
            pip_resized = pip_resized.subclip(0, main.duration)
        elif pip_resized.duration > main.duration:
            pip_resized = pip_resized.subclip(0, main.duration)

        pip_resized = pip_resized.set_position(pos)

        # Composite
        final = CompositeVideoClip([main, pip_resized])

        # Add audio
        if audio_path and audio_path.exists():
            audio = AudioFileClip(str(audio_path))
            final = final.set_audio(audio)

        # Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            preset="slow",
            ffmpeg_params=["-crf", "18"],
        )

        duration = final.duration

        # Cleanup
        main.close()
        pip.close()
        final.close()

        return HybridResult(
            status="success",
            video_path=output_path,
            duration_seconds=duration,
        )

    def _composite_sequential(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path],
    ) -> HybridResult:
        """Composite with sequential layout (one after another)."""
        try:
            from moviepy.editor import (
                VideoFileClip,
                concatenate_videoclips,
                AudioFileClip,
            )
        except ImportError:
            return self._composite_sequential_ffmpeg(
                terminal_video, browser_video, output_path, audio_path
            )

        # Load and resize videos to same dimensions
        terminal = VideoFileClip(str(terminal_video))
        browser = VideoFileClip(str(browser_video))

        width = self.config.output_width
        height = self.config.output_height

        terminal_resized = terminal.resize(newsize=(width, height))
        browser_resized = browser.resize(newsize=(width, height))

        # Concatenate
        final = concatenate_videoclips([terminal_resized, browser_resized])

        # Add audio
        if audio_path and audio_path.exists():
            audio = AudioFileClip(str(audio_path))
            final = final.set_audio(audio)

        # Export
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final.write_videofile(
            str(output_path),
            codec="libx264",
            audio_codec="aac",
            preset="slow",
            ffmpeg_params=["-crf", "18"],
        )

        duration = final.duration

        # Cleanup
        terminal.close()
        browser.close()
        final.close()

        return HybridResult(
            status="success",
            video_path=output_path,
            duration_seconds=duration,
        )

    def _composite_sequential_ffmpeg(
        self,
        terminal_video: Path,
        browser_video: Path,
        output_path: Path,
        audio_path: Optional[Path],
    ) -> HybridResult:
        """Sequential composite using ffmpeg."""
        width = self.config.output_width
        height = self.config.output_height

        # Create file list
        list_file = output_path.parent / "concat_list.txt"
        list_file.write_text(
            f"file '{terminal_video.absolute()}'\nfile '{browser_video.absolute()}'"
        )

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        ]

        if audio_path and audio_path.exists():
            cmd.extend(["-i", str(audio_path), "-map", "0:v", "-map", "1:a"])

        cmd.extend([
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "slow",
            "-c:a", "aac",
            str(output_path),
        ])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(cmd, check=True, capture_output=True)

        list_file.unlink()  # Cleanup

        duration = self._get_video_duration(output_path)

        return HybridResult(
            status="success",
            video_path=output_path,
            duration_seconds=duration,
        )

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration using ffprobe."""
        try:
            import json
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
            )
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception:
            return None


def composite_hybrid_demo(
    terminal_video: Path,
    browser_video: Path,
    output_path: Path,
    layout: str = "split",
    terminal_position: str = "left",
    terminal_width_percent: int = 40,
    audio_path: Optional[Path] = None,
) -> HybridResult:
    """
    Convenience function to composite a hybrid demo.

    Args:
        terminal_video: Path to terminal recording
        browser_video: Path to browser recording
        output_path: Path for output video
        layout: Layout type (split, pip, sequential)
        terminal_position: Position of terminal (left, right, top, bottom)
        terminal_width_percent: Width percentage for split layout
        audio_path: Optional audio track

    Returns:
        HybridResult
    """
    config = HybridConfig(
        layout=LayoutType(layout),
        terminal_position=terminal_position,
        terminal_width_percent=terminal_width_percent,
    )

    compositor = HybridCompositor(config)
    return compositor.composite(
        terminal_video=Path(terminal_video),
        browser_video=Path(browser_video),
        output_path=Path(output_path),
        audio_path=Path(audio_path) if audio_path else None,
    )
