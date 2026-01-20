"""
Terminal recording utilities for demo-creator.

Records CLI/terminal sessions using asciinema-style recordings.
Supports realistic typing simulation and intelligent command waiting.
"""

import json
import logging
import os
import pty
import select
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class TerminalConfig:
    """Configuration for terminal recording."""

    cols: int = 120
    rows: int = 40
    shell: str = "/bin/zsh"
    env: Dict[str, str] = field(default_factory=dict)
    typing_speed_min: float = 0.03  # Min delay between keystrokes (seconds)
    typing_speed_max: float = 0.12  # Max delay between keystrokes
    mistake_probability: float = 0.02  # Probability of making a typo
    theme: str = "monokai"


@dataclass
class TerminalAction:
    """Represents a terminal action."""

    action_type: str  # command, type, wait, wait_for, clear
    text: Optional[str] = None
    pattern: Optional[str] = None
    delay_after: int = 1000  # ms
    typing_delay: Optional[int] = None  # Override typing speed


@dataclass
class TerminalScene:
    """Represents a terminal demo scene."""

    name: str
    actions: List[TerminalAction] = field(default_factory=list)
    narration_notes: Optional[str] = None


@dataclass
class TerminalRecordingResult:
    """Result of terminal recording."""

    status: str  # success, failed
    cast_path: Optional[Path] = None
    video_path: Optional[Path] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "cast_path": str(self.cast_path) if self.cast_path else None,
            "video_path": str(self.video_path) if self.video_path else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }


class AsciicastWriter:
    """
    Writes recordings in asciicast v2 format.

    Format spec: https://github.com/asciinema/asciinema/blob/develop/doc/asciicast-v2.md
    """

    def __init__(self, path: Path, width: int = 120, height: int = 40):
        self.path = path
        self.width = width
        self.height = height
        self.start_time = None
        self._file = None

    def __enter__(self):
        self._file = open(self.path, "w")

        # Write header
        header = {
            "version": 2,
            "width": self.width,
            "height": self.height,
            "timestamp": int(time.time()),
            "env": {
                "SHELL": os.environ.get("SHELL", "/bin/bash"),
                "TERM": os.environ.get("TERM", "xterm-256color"),
            },
        }
        self._file.write(json.dumps(header) + "\n")
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()

    def write_output(self, text: str) -> None:
        """Write output event."""
        if self._file and self.start_time:
            elapsed = time.time() - self.start_time
            event = [elapsed, "o", text]
            self._file.write(json.dumps(event) + "\n")

    def write_input(self, text: str) -> None:
        """Write input event (optional, for replay accuracy)."""
        if self._file and self.start_time:
            elapsed = time.time() - self.start_time
            event = [elapsed, "i", text]
            self._file.write(json.dumps(event) + "\n")


class TerminalRecorder:
    """
    Records terminal sessions with realistic typing simulation.

    Creates asciicast v2 format recordings that can be:
    1. Embedded using asciinema-player
    2. Converted to video using agg or similar tools
    """

    def __init__(self, config: Optional[TerminalConfig] = None):
        self.config = config or TerminalConfig()
        self._master_fd = None
        self._slave_fd = None
        self._child_pid = None

    def record_script(
        self,
        scenes: List[TerminalScene],
        output_path: Path,
    ) -> TerminalRecordingResult:
        """
        Record a terminal demo from a list of scenes.

        Args:
            scenes: List of TerminalScene objects
            output_path: Path for the .cast file

        Returns:
            TerminalRecordingResult
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with AsciicastWriter(output_path, self.config.cols, self.config.rows) as writer:
                # Start shell
                self._start_shell()

                # Wait for shell to be ready
                time.sleep(0.5)
                initial_output = self._read_output(timeout=1.0)
                if initial_output:
                    writer.write_output(initial_output)

                # Execute scenes
                for scene in scenes:
                    logger.info(f"Recording scene: {scene.name}")

                    for action in scene.actions:
                        self._execute_action(action, writer)

                # Clean exit
                self._send_input("exit\n")
                time.sleep(0.5)
                final_output = self._read_output(timeout=1.0)
                if final_output:
                    writer.write_output(final_output)

                self._stop_shell()

            # Calculate duration from cast file
            duration = self._get_cast_duration(output_path)

            return TerminalRecordingResult(
                status="success",
                cast_path=output_path,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.exception("Terminal recording failed")
            self._stop_shell()
            return TerminalRecordingResult(
                status="failed",
                error=str(e),
            )

    def _start_shell(self) -> None:
        """Start a PTY shell session."""
        self._master_fd, self._slave_fd = pty.openpty()

        # Set terminal size
        import struct
        import fcntl
        import termios

        winsize = struct.pack("HHHH", self.config.rows, self.config.cols, 0, 0)
        fcntl.ioctl(self._slave_fd, termios.TIOCSWINSZ, winsize)

        # Fork child process
        self._child_pid = os.fork()

        if self._child_pid == 0:
            # Child process
            os.close(self._master_fd)
            os.setsid()
            os.dup2(self._slave_fd, 0)
            os.dup2(self._slave_fd, 1)
            os.dup2(self._slave_fd, 2)

            if self._slave_fd > 2:
                os.close(self._slave_fd)

            # Set environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            env["COLUMNS"] = str(self.config.cols)
            env["LINES"] = str(self.config.rows)
            env.update(self.config.env)

            os.execve(self.config.shell, [self.config.shell, "-l"], env)
        else:
            # Parent process
            os.close(self._slave_fd)

    def _stop_shell(self) -> None:
        """Stop the shell session."""
        if self._child_pid:
            try:
                os.kill(self._child_pid, 9)
                os.waitpid(self._child_pid, 0)
            except Exception:
                pass
            self._child_pid = None

        if self._master_fd:
            try:
                os.close(self._master_fd)
            except Exception:
                pass
            self._master_fd = None

    def _send_input(self, text: str) -> None:
        """Send input to the shell."""
        if self._master_fd:
            os.write(self._master_fd, text.encode())

    def _read_output(self, timeout: float = 0.1) -> str:
        """Read output from the shell."""
        if not self._master_fd:
            return ""

        output = []
        while True:
            ready, _, _ = select.select([self._master_fd], [], [], timeout)
            if not ready:
                break

            try:
                data = os.read(self._master_fd, 4096)
                if data:
                    output.append(data.decode("utf-8", errors="replace"))
                else:
                    break
            except OSError:
                break

        return "".join(output)

    def _execute_action(self, action: TerminalAction, writer: AsciicastWriter) -> None:
        """Execute a terminal action."""
        if action.action_type == "command":
            # Type command with realistic speed
            self._type_with_simulation(action.text, writer)

            # Press enter
            self._send_input("\n")
            writer.write_output("\n")

            # Wait for output
            time.sleep(0.1)
            output = self._read_output(timeout=2.0)
            if output:
                writer.write_output(output)

            # Additional delay
            if action.delay_after:
                time.sleep(action.delay_after / 1000)
                output = self._read_output(timeout=0.5)
                if output:
                    writer.write_output(output)

        elif action.action_type == "type":
            # Just type without executing
            self._type_with_simulation(action.text, writer)

            if action.delay_after:
                time.sleep(action.delay_after / 1000)

        elif action.action_type == "wait":
            # Simple wait
            time.sleep(action.delay_after / 1000)

            # Capture any output during wait
            output = self._read_output(timeout=0.5)
            if output:
                writer.write_output(output)

        elif action.action_type == "wait_for":
            # Wait for specific output pattern
            import re

            pattern = re.compile(action.pattern)
            timeout = action.delay_after / 1000 if action.delay_after else 30
            start = time.time()

            accumulated = ""
            while time.time() - start < timeout:
                output = self._read_output(timeout=0.5)
                if output:
                    writer.write_output(output)
                    accumulated += output

                    if pattern.search(accumulated):
                        break

        elif action.action_type == "clear":
            # Clear screen
            self._send_input("\x0c")  # Ctrl+L
            time.sleep(0.1)
            output = self._read_output(timeout=0.5)
            if output:
                writer.write_output(output)

    def _type_with_simulation(self, text: str, writer: AsciicastWriter) -> None:
        """Type text with realistic human-like simulation."""
        import random

        for i, char in enumerate(text):
            # Occasionally make a typo and correct it
            if (
                random.random() < self.config.mistake_probability
                and char.isalpha()
                and i < len(text) - 1
            ):
                # Type wrong character
                wrong_char = random.choice("qwertyuiopasdfghjklzxcvbnm")
                self._send_input(wrong_char)
                writer.write_output(wrong_char)

                time.sleep(random.uniform(0.1, 0.3))

                # Backspace
                self._send_input("\x7f")
                writer.write_output("\b \b")

                time.sleep(random.uniform(0.05, 0.15))

            # Type actual character
            self._send_input(char)
            writer.write_output(char)

            # Variable delay between keystrokes
            delay = random.uniform(
                self.config.typing_speed_min,
                self.config.typing_speed_max,
            )

            # Longer pause after punctuation
            if char in ".!?":
                delay *= 3
            elif char in ",;:":
                delay *= 2
            elif char == " ":
                delay *= 1.5

            time.sleep(delay)

    def _get_cast_duration(self, cast_path: Path) -> float:
        """Get duration from cast file."""
        try:
            with open(cast_path) as f:
                lines = f.readlines()

            if len(lines) < 2:
                return 0

            # Last line has final timestamp
            last_event = json.loads(lines[-1])
            return last_event[0]

        except Exception:
            return 0


def convert_cast_to_video(
    cast_path: Path,
    output_path: Path,
    theme: str = "monokai",
    font_size: int = 14,
) -> Path:
    """
    Convert asciicast to video using agg (asciinema gif generator).

    Note: Requires agg to be installed (cargo install agg)

    Args:
        cast_path: Path to .cast file
        output_path: Path for output video
        theme: Color theme
        font_size: Font size

    Returns:
        Path to generated video
    """
    # First convert to GIF
    gif_path = output_path.with_suffix(".gif")

    try:
        subprocess.run(
            [
                "agg",
                str(cast_path),
                str(gif_path),
                "--theme", theme,
                "--font-size", str(font_size),
            ],
            check=True,
            capture_output=True,
        )

        # Convert GIF to MP4 if requested
        if output_path.suffix == ".mp4":
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(gif_path),
                    "-movflags", "faststart",
                    "-pix_fmt", "yuv420p",
                    "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
            )
            gif_path.unlink()  # Remove intermediate GIF
            return output_path

        return gif_path

    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to convert cast to video: {e.stderr.decode()}")
        raise


def record_terminal_demo(
    scenes: List[Dict[str, Any]],
    output_dir: Path,
    config: Optional[TerminalConfig] = None,
) -> TerminalRecordingResult:
    """
    Convenience function to record a terminal demo.

    Args:
        scenes: List of scene dictionaries
        output_dir: Output directory
        config: Optional terminal configuration

    Returns:
        TerminalRecordingResult
    """
    # Convert dict scenes to TerminalScene objects
    terminal_scenes = []
    for scene_dict in scenes:
        actions = []
        for action_dict in scene_dict.get("actions", []):
            actions.append(TerminalAction(
                action_type=action_dict.get("type", "command"),
                text=action_dict.get("text"),
                pattern=action_dict.get("pattern"),
                delay_after=action_dict.get("delay_after", 1000),
            ))

        terminal_scenes.append(TerminalScene(
            name=scene_dict.get("name", ""),
            actions=actions,
            narration_notes=scene_dict.get("narration_notes"),
        ))

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    recorder = TerminalRecorder(config)
    return recorder.record_script(
        terminal_scenes,
        output_dir / "terminal_recording.cast",
    )


def parse_terminal_script(script_yaml: str) -> List[TerminalScene]:
    """
    Parse a YAML terminal script into scenes.

    Args:
        script_yaml: YAML content

    Returns:
        List of TerminalScene objects
    """
    import yaml

    data = yaml.safe_load(script_yaml)
    scenes = []

    for scene_data in data.get("scenes", []):
        actions = []
        for action_data in scene_data.get("actions", []):
            # Handle different action formats
            if "command" in action_data:
                actions.append(TerminalAction(
                    action_type="command",
                    text=action_data["command"],
                    delay_after=action_data.get("delay_after", 1000),
                ))
            elif "type" in action_data and "text" in action_data:
                actions.append(TerminalAction(
                    action_type=action_data["type"],
                    text=action_data.get("text"),
                    pattern=action_data.get("pattern"),
                    delay_after=action_data.get("delay_after", 1000),
                ))
            elif "wait_for" in action_data:
                actions.append(TerminalAction(
                    action_type="wait_for",
                    pattern=action_data["wait_for"],
                    delay_after=action_data.get("timeout", 30000),
                ))

        scenes.append(TerminalScene(
            name=scene_data.get("name", ""),
            actions=actions,
            narration_notes=scene_data.get("narration_notes"),
        ))

    return scenes
