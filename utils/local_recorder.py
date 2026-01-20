"""
Local Playwright recording utilities for demo-creator.

Provides local recording capability without requiring Kubernetes,
using Playwright's built-in video recording.
"""

import json
import logging
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .retry import retry, RetryError

logger = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    """Configuration for local recording."""

    viewport_width: int = 1920
    viewport_height: int = 1080
    frame_rate: int = 30
    headless: bool = True
    slow_mo: int = 0  # Slow down actions by this many ms
    timeout: int = 30000  # Default timeout in ms
    video_dir: str = "./recordings"


@dataclass
class RecordingResult:
    """Result of a recording session."""

    status: str  # "success", "failed", "timeout"
    video_path: Optional[Path] = None
    duration_seconds: Optional[float] = None
    screenshots: List[Path] = None
    error: Optional[str] = None
    logs: Optional[str] = None

    def __post_init__(self):
        if self.screenshots is None:
            self.screenshots = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "video_path": str(self.video_path) if self.video_path else None,
            "duration_seconds": self.duration_seconds,
            "screenshots": [str(p) for p in self.screenshots],
            "error": self.error,
        }


class LocalRecorder:
    """
    Records demos using local Playwright installation.

    This is an alternative to the Kubernetes-based screenenv recording
    that's faster and simpler for local development.
    """

    def __init__(self, config: Optional[RecordingConfig] = None):
        """
        Initialize local recorder.

        Args:
            config: Recording configuration
        """
        self.config = config or RecordingConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    def _ensure_playwright_installed(self) -> bool:
        """Check if Playwright is installed and install if needed."""
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            logger.info("Installing Playwright...")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "playwright"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=True,
                capture_output=True,
            )
            return True

    def record_script(
        self,
        script_path: Path,
        output_dir: Path,
        base_url: Optional[str] = None,
    ) -> RecordingResult:
        """
        Execute a Playwright script and record the session.

        Args:
            script_path: Path to the Python Playwright script
            output_dir: Directory to save recordings
            base_url: Optional base URL override

        Returns:
            RecordingResult with status and paths
        """
        self._ensure_playwright_installed()

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        recordings_dir = output_dir / "recordings"
        recordings_dir.mkdir(exist_ok=True)

        # Execute the script
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout
                cwd=str(output_dir),
                env={
                    **subprocess.os.environ,
                    "PLAYWRIGHT_VIDEO_DIR": str(recordings_dir),
                },
            )

            if result.returncode != 0:
                return RecordingResult(
                    status="failed",
                    error=result.stderr,
                    logs=result.stdout,
                )

            # Find the video file
            video_files = list(recordings_dir.glob("*.webm"))
            if not video_files:
                return RecordingResult(
                    status="failed",
                    error="No video file generated",
                    logs=result.stdout,
                )

            video_path = video_files[0]

            # Get video duration
            duration = self._get_video_duration(video_path)

            # Move video to standard name
            final_video_path = output_dir / "demo_recording.webm"
            video_path.rename(final_video_path)

            # Find screenshots
            screenshots = list(output_dir.glob("scene_*.png"))

            return RecordingResult(
                status="success",
                video_path=final_video_path,
                duration_seconds=duration,
                screenshots=screenshots,
                logs=result.stdout,
            )

        except subprocess.TimeoutExpired:
            return RecordingResult(
                status="timeout",
                error="Recording timed out after 10 minutes",
            )
        except Exception as e:
            return RecordingResult(
                status="failed",
                error=str(e),
            )

    def record_actions(
        self,
        actions: List[Dict[str, Any]],
        output_dir: Path,
        base_url: str,
    ) -> RecordingResult:
        """
        Record a series of actions directly (without a script file).

        Args:
            actions: List of action dictionaries
            output_dir: Directory to save recordings
            base_url: Base URL of the application

        Returns:
            RecordingResult with status and paths
        """
        self._ensure_playwright_installed()
        from playwright.sync_api import sync_playwright

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        recordings_dir = output_dir / "recordings"
        recordings_dir.mkdir(exist_ok=True)

        screenshots = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.config.headless,
                    slow_mo=self.config.slow_mo,
                )
                context = browser.new_context(
                    viewport={
                        "width": self.config.viewport_width,
                        "height": self.config.viewport_height,
                    },
                    record_video_dir=str(recordings_dir),
                    record_video_size={
                        "width": self.config.viewport_width,
                        "height": self.config.viewport_height,
                    },
                )
                page = context.new_page()

                # Execute actions
                for i, action in enumerate(actions):
                    self._execute_action(page, action)

                    # Take screenshot if requested
                    if action.get("screenshot"):
                        screenshot_path = output_dir / f"scene_{i + 1}.png"
                        page.screenshot(path=str(screenshot_path))
                        screenshots.append(screenshot_path)

                # Close context to finalize video
                video_path = page.video.path()
                context.close()
                browser.close()

                # Move video to standard location
                final_video_path = output_dir / "demo_recording.webm"
                Path(video_path).rename(final_video_path)

                duration = self._get_video_duration(final_video_path)

                return RecordingResult(
                    status="success",
                    video_path=final_video_path,
                    duration_seconds=duration,
                    screenshots=screenshots,
                )

        except Exception as e:
            logger.exception("Recording failed")
            return RecordingResult(
                status="failed",
                error=str(e),
                screenshots=screenshots,
            )

    def _execute_action(self, page, action: Dict[str, Any]) -> None:
        """Execute a single action on the page."""
        action_type = action.get("type", action.get("action"))

        if action_type == "goto":
            url = action.get("url")
            page.goto(url)
            page.wait_for_load_state("networkidle")

        elif action_type == "click":
            selector = action.get("selector")
            page.click(selector)

        elif action_type == "fill" or action_type == "type":
            selector = action.get("selector")
            text = action.get("text", action.get("value", ""))
            if action.get("human_like"):
                page.type(selector, text, delay=100)
            else:
                page.fill(selector, text)

        elif action_type == "wait":
            duration = action.get("duration", action.get("ms", 1000))
            page.wait_for_timeout(duration)

        elif action_type == "wait_for_selector":
            selector = action.get("selector")
            page.wait_for_selector(selector, timeout=self.config.timeout)

        elif action_type == "wait_for_idle":
            page.wait_for_load_state("networkidle")

        elif action_type == "hover":
            selector = action.get("selector")
            page.hover(selector)

        elif action_type == "select":
            selector = action.get("selector")
            value = action.get("value")
            page.select_option(selector, value)

        elif action_type == "scroll":
            selector = action.get("selector")
            if selector:
                page.locator(selector).scroll_into_view_if_needed()
            else:
                direction = action.get("direction", "down")
                amount = action.get("amount", 300)
                if direction == "down":
                    page.mouse.wheel(0, amount)
                elif direction == "up":
                    page.mouse.wheel(0, -amount)

        elif action_type == "assert_visible":
            selector = action.get("selector")
            assert page.locator(selector).is_visible()

        elif action_type == "highlight":
            selector = action.get("selector")
            duration = action.get("duration", 1500)
            page.evaluate(
                f"""
                (selector) => {{
                    const el = document.querySelector(selector);
                    if (el) {{
                        el.style.outline = '3px solid #ff6b6b';
                        el.style.outlineOffset = '2px';
                        setTimeout(() => {{
                            el.style.outline = '';
                            el.style.outlineOffset = '';
                        }}, {duration});
                    }}
                }}
                """,
                selector,
            )
            page.wait_for_timeout(duration)

    def _get_video_duration(self, video_path: Path) -> Optional[float]:
        """Get video duration in seconds."""
        try:
            from moviepy.editor import VideoFileClip
            clip = VideoFileClip(str(video_path))
            duration = clip.duration
            clip.close()
            return duration
        except ImportError:
            # Fallback: use ffprobe
            try:
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
        except Exception:
            return None

    def validate_script(
        self,
        script_path: Path,
        base_url: str,
        take_screenshots: bool = True,
    ) -> RecordingResult:
        """
        Validate a script without recording (dry run).

        Args:
            script_path: Path to the Playwright script
            base_url: Base URL of the application
            take_screenshots: Whether to capture screenshots

        Returns:
            RecordingResult indicating validation status
        """
        self._ensure_playwright_installed()

        output_dir = script_path.parent
        screenshots = []

        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for validation
                cwd=str(output_dir),
            )

            if result.returncode != 0:
                return RecordingResult(
                    status="failed",
                    error=result.stderr,
                    logs=result.stdout,
                )

            # Find screenshots
            screenshots = list(output_dir.glob("scene_*.png"))

            return RecordingResult(
                status="success",
                screenshots=screenshots,
                logs=result.stdout,
            )

        except subprocess.TimeoutExpired:
            return RecordingResult(
                status="timeout",
                error="Validation timed out after 5 minutes",
            )
        except Exception as e:
            return RecordingResult(
                status="failed",
                error=str(e),
            )


def record_demo_locally(
    script_path: Path,
    output_dir: Path,
    config: Optional[RecordingConfig] = None,
) -> RecordingResult:
    """
    Convenience function to record a demo locally.

    Args:
        script_path: Path to Playwright script
        output_dir: Output directory
        config: Optional recording configuration

    Returns:
        RecordingResult
    """
    recorder = LocalRecorder(config)
    return recorder.record_script(script_path, output_dir)


def validate_demo_script(
    script_path: Path,
    base_url: str,
) -> RecordingResult:
    """
    Convenience function to validate a demo script.

    Args:
        script_path: Path to Playwright script
        base_url: Base URL of the application

    Returns:
        RecordingResult indicating validation status
    """
    recorder = LocalRecorder()
    return recorder.validate_script(script_path, base_url)


def convert_webm_to_mp4(
    webm_path: Path,
    mp4_path: Optional[Path] = None,
    quality: int = 18,
) -> Path:
    """
    Convert WebM recording to MP4 for better compatibility.

    Args:
        webm_path: Path to WebM file
        mp4_path: Optional output path (defaults to same name with .mp4)
        quality: CRF quality (lower = better, 18-28 recommended)

    Returns:
        Path to MP4 file
    """
    if mp4_path is None:
        mp4_path = webm_path.with_suffix(".mp4")

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(webm_path),
            "-c:v", "libx264",
            "-crf", str(quality),
            "-preset", "slow",
            "-c:a", "aac",
            "-b:a", "192k",
            str(mp4_path),
        ],
        check=True,
        capture_output=True,
    )

    return mp4_path
