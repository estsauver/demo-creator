#!/usr/bin/env python3
"""
terminal_demo.py - YAML-based terminal demo recorder for asciinema .cast output

Creates reproducible terminal demos from declarative YAML scripts.

Usage:
    python3 terminal_demo.py demo.yaml -o demo.cast
    python3 terminal_demo.py demo.yaml -o demo.cast --dry-run
    python3 terminal_demo.py demo.yaml -o demo.cast --preview
    python3 terminal_demo.py demo.yaml -o demo.cast --export-gif demo.gif
    python3 terminal_demo.py demo.yaml --assert-only
    python3 terminal_demo.py demo.yaml -o demo.cast --narration-srt narration.srt
    python3 terminal_demo.py demo.yaml --parallel  # CI mode with parallel execution

Features:
    - Declarative YAML scripts with type, execute, run, pause actions
    - Asciinema .cast v2 output format
    - Dry-run mode for validation
    - Smart error detection with context awareness
    - Variable interpolation and templating
    - Section markers for chapters
    - Working directory support (global and per-step)
    - Foreach loops for iterating over items
    - Preview playback after recording
    - GIF export via asciinema-agg
    - Narration timing export (SRT/VTT)
    - Progress tracking during recording
    - Parallel execution for CI validation
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import pty
import re
import select
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

# Constants
CAST_VERSION = 2
DEFAULT_SHELL = os.environ.get("SHELL", "/bin/bash")
DEFAULT_TERM = "xterm-256color"
DEFAULT_COLS = 120
DEFAULT_ROWS = 30
DEFAULT_TYPING_SPEED = 50  # ms per character
DEFAULT_POST_EXECUTE_PAUSE = 500  # ms after command execution


@dataclass
class ErrorDetectionConfig:
    """Configuration for smart error detection."""

    mode: str = "smart"  # "smart", "strict", or "off"
    patterns: list[str] = field(
        default_factory=lambda: [
            r"(?i)^error:",
            r"(?i)^fatal:",
            r"(?i)^exception:",
            r"(?i)traceback \(most recent call last\)",
            r"(?i)^failed:",
            r"(?i)command not found",
            r"(?i)no such file or directory",
            r"(?i)permission denied",
        ]
    )
    safe_contexts: list[str] = field(
        default_factory=lambda: [
            r"PASSED",
            r"test_\w*error",  # Test names containing "error"
            r"test_\w*fail",  # Test names containing "fail"
            r"^\s*#",  # Comments
            r"error_handler",  # Variable/function names
            r"ErrorHandler",
            r"on_error",
            r"handle_error",
        ]
    )
    ignore_patterns: list[str] = field(default_factory=list)

    # Pre-compiled regex patterns for performance
    _compiled_patterns: list[re.Pattern] = field(default_factory=list, repr=False)
    _compiled_safe_contexts: list[re.Pattern] = field(default_factory=list, repr=False)
    _compiled_ignore_patterns: list[re.Pattern] = field(default_factory=list, repr=False)

    def __post_init__(self):
        """Pre-compile regex patterns for performance."""
        self.compile_patterns()

    def compile_patterns(self):
        """Compile all regex patterns. Call after modifying pattern lists."""
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.patterns
        ]
        self._compiled_safe_contexts = [
            re.compile(p, re.IGNORECASE) for p in self.safe_contexts
        ]
        self._compiled_ignore_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.ignore_patterns
        ]


@dataclass
class Settings:
    """Global settings for the demo."""

    shell: str = DEFAULT_SHELL
    cwd: Optional[str] = None
    env: dict[str, str] = field(default_factory=dict)
    typing_speed: int = DEFAULT_TYPING_SPEED
    post_execute_pause: int = DEFAULT_POST_EXECUTE_PAUSE
    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS
    title: Optional[str] = None
    error_detection: ErrorDetectionConfig = field(default_factory=ErrorDetectionConfig)


@dataclass
class Step:
    """A single step in the demo."""

    action: str
    content: Optional[str] = None
    duration: Optional[int] = None
    cwd: Optional[str] = None
    typing_speed: Optional[int] = None
    ignore_error_patterns: list[str] = field(default_factory=list)
    expect_error: bool = False
    narration: Optional[dict[str, str]] = None
    name: Optional[str] = None  # For sections
    items: Optional[list[str]] = None  # For foreach
    template: Optional[list[dict]] = None  # For foreach


@dataclass
class CastEvent:
    """An event in the asciinema cast file."""

    timestamp: float
    event_type: str  # "o" for output, "i" for input
    data: str


@dataclass
class Section:
    """A section/chapter marker in the demo."""

    name: str
    timestamp: float


@dataclass
class NarrationEntry:
    """A narration entry with timing information."""

    start_time: float
    end_time: float
    text: str
    step_index: int
    position: str  # "before" or "after"


@dataclass
class Metadata:
    """Demo metadata for tracking and validation."""

    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    source_checksum: Optional[str] = None
    recorded_at: Optional[str] = None


class ProgressTracker:
    """Track progress during recording."""

    def __init__(self, total_steps: int, estimated_duration: float = 0):
        self.total_steps = total_steps
        self.current_step = 0
        self.estimated_duration = estimated_duration
        self.start_time = time.time()
        self.enabled = sys.stdout.isatty()

    def update(self, step_index: int, step_name: str = ""):
        """Update progress display."""
        self.current_step = step_index + 1
        if not self.enabled:
            return

        pct = (self.current_step / self.total_steps) * 100
        elapsed = time.time() - self.start_time
        bar_len = 30
        filled = int(bar_len * self.current_step // self.total_steps)
        bar = "█" * filled + "░" * (bar_len - filled)

        # Estimate remaining time
        if self.current_step > 0 and self.estimated_duration > 0:
            remaining = max(0, self.estimated_duration - elapsed)
            time_str = f" ~{remaining:.0f}s left"
        else:
            time_str = ""

        step_info = f" [{step_name}]" if step_name else ""
        print(
            f"\r  [{bar}] {pct:5.1f}% ({self.current_step}/{self.total_steps}){step_info}{time_str}",
            end="",
            flush=True,
        )

    def finish(self):
        """Complete the progress bar."""
        if self.enabled:
            elapsed = time.time() - self.start_time
            print(f"\r  Recording completed in {elapsed:.1f}s" + " " * 40)


class TerminalRecorder:
    """Records terminal sessions to asciinema cast format."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.events: list[CastEvent] = []
        self.sections: list[Section] = []
        self.narrations: list[NarrationEntry] = []
        self.start_time: float = 0
        self.current_cwd = settings.cwd or os.getcwd()
        self.detected_errors: list[dict[str, Any]] = []
        self.variables: dict[str, str] = {}
        self.metadata: Metadata = Metadata()
        self.dry_run = False
        self.assert_only = False
        self.progress: Optional[ProgressTracker] = None
        self._step_start_time: float = 0

    def interpolate(self, text: str) -> str:
        """Interpolate variables in text using {{ var }} syntax."""
        if not text:
            return text

        def replace_var(match):
            var_name = match.group(1).strip()
            if var_name in self.variables:
                return self.variables[var_name]
            # Check environment variables as fallback
            if var_name in os.environ:
                return os.environ[var_name]
            return match.group(0)  # Leave unchanged if not found

        return re.sub(r"\{\{\s*(\w+)\s*\}\}", replace_var, text)

    def validate_path(self, path: str, base_dir: Optional[str] = None) -> str:
        """
        Validate and resolve a path, checking for path traversal attempts.

        Args:
            path: The path to validate (may be relative or absolute)
            base_dir: Optional base directory to resolve relative paths against.
                      Defaults to current_cwd.

        Returns:
            Resolved absolute path

        Raises:
            ValueError: If path traversal is detected (path escapes base_dir)
        """
        base = base_dir or self.current_cwd
        resolved_base = os.path.abspath(base)

        if os.path.isabs(path):
            resolved_path = os.path.abspath(path)
        else:
            resolved_path = os.path.abspath(os.path.join(resolved_base, path))

        # Check for path traversal: resolved path must be under base or be absolute
        # For absolute paths in demo scripts, we allow them but log a warning
        if not os.path.isabs(path):
            # Relative path - must stay within base_dir
            try:
                # Use os.path.commonpath to check containment
                common = os.path.commonpath([resolved_base, resolved_path])
                if common != resolved_base:
                    raise ValueError(
                        f"Path traversal detected: '{path}' resolves to '{resolved_path}' "
                        f"which is outside base directory '{resolved_base}'"
                    )
            except ValueError as e:
                # commonpath raises ValueError if paths are on different drives (Windows)
                if "different drives" not in str(e).lower():
                    raise

        return resolved_path

    def get_timestamp(self) -> float:
        """Get current timestamp relative to start."""
        return time.time() - self.start_time

    def add_output(self, data: str):
        """Add output event."""
        self.events.append(CastEvent(self.get_timestamp(), "o", data))

    def add_input(self, data: str):
        """Add input event."""
        self.events.append(CastEvent(self.get_timestamp(), "i", data))

    def add_narration(
        self, text: str, step_index: int, position: str, duration: float = 3.0
    ):
        """Add narration entry with timing."""
        start = self.get_timestamp()
        self.narrations.append(
            NarrationEntry(
                start_time=start,
                end_time=start + duration,
                text=text,
                step_index=step_index,
                position=position,
            )
        )

    def check_for_errors(
        self, output: str, step: Step, step_index: int
    ) -> list[dict[str, Any]]:
        """Check output for errors using smart detection with pre-compiled regexes."""
        if self.settings.error_detection.mode == "off":
            return []

        if step.expect_error:
            return []

        errors = []
        lines = output.split("\n")
        error_cfg = self.settings.error_detection

        # Use pre-compiled global ignore patterns + compile step-specific ones
        step_ignore_compiled = [
            re.compile(p, re.IGNORECASE) for p in step.ignore_error_patterns
        ]
        all_ignore_patterns = error_cfg._compiled_ignore_patterns + step_ignore_compiled

        for line_num, line in enumerate(lines):
            # Skip empty lines
            if not line.strip():
                continue

            # Check if line matches any ignore pattern (using compiled patterns)
            if any(pat.search(line) for pat in all_ignore_patterns):
                continue

            # Check for error patterns (using pre-compiled patterns)
            for i, compiled_pattern in enumerate(error_cfg._compiled_patterns):
                if compiled_pattern.search(line):
                    # In smart mode, check safe contexts (using pre-compiled patterns)
                    if error_cfg.mode == "smart":
                        is_safe = any(
                            ctx.search(line)
                            for ctx in error_cfg._compiled_safe_contexts
                        )
                        if is_safe:
                            continue

                    errors.append(
                        {
                            "step": step_index,
                            "line": line_num + 1,
                            "pattern": error_cfg.patterns[i],  # Store original pattern string
                            "content": line.strip()[:200],
                        }
                    )
                    break

        return errors

    def type_text(self, text: str, speed: Optional[int] = None):
        """Simulate typing text character by character."""
        speed = speed or self.settings.typing_speed
        delay = speed / 1000.0

        for char in text:
            self.add_output(char)
            if not self.dry_run:
                time.sleep(delay)

    def execute_command(
        self, command: str, cwd: Optional[str] = None
    ) -> tuple[str, int]:
        """Execute a command and capture output."""
        work_dir = cwd or self.current_cwd

        if self.dry_run or self.assert_only:
            # In dry-run/assert mode, just execute without recording
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=work_dir,
                env={**os.environ, **self.settings.env},
            )
            return result.stdout + result.stderr, result.returncode

        # Create pseudo-terminal for proper output capture
        master_fd, slave_fd = pty.openpty()
        slave_closed = False

        try:
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    cwd=work_dir,
                    env={**os.environ, **self.settings.env, "TERM": DEFAULT_TERM},
                )
            finally:
                # Always close slave_fd after Popen, whether successful or not
                os.close(slave_fd)
                slave_closed = True

            output = ""
            while True:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        data = os.read(master_fd, 1024).decode("utf-8", errors="replace")
                        if data:
                            output += data
                            self.add_output(data)
                    except OSError:
                        break

                if process.poll() is not None:
                    # Process finished, read remaining output
                    while True:
                        ready, _, _ = select.select([master_fd], [], [], 0.1)
                        if not ready:
                            break
                        try:
                            data = os.read(master_fd, 1024).decode(
                                "utf-8", errors="replace"
                            )
                            if data:
                                output += data
                                self.add_output(data)
                            else:
                                break
                        except OSError:
                            break
                    break

            return output, process.returncode

        finally:
            os.close(master_fd)
            # Ensure slave_fd is closed if we failed before the inner finally
            if not slave_closed:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass  # Already closed or invalid

    def run_step(self, step: Step, step_index: int) -> bool:
        """Execute a single step. Returns True if successful."""
        action = step.action
        self._step_start_time = self.get_timestamp()

        # Update progress
        if self.progress:
            step_name = step.name or action
            self.progress.update(step_index, step_name)

        # Handle "before" narration
        if step.narration and "before" in step.narration:
            self.add_narration(step.narration["before"], step_index, "before")

        # Resolve and validate working directory
        step_cwd = None
        if step.cwd:
            step_cwd = self.interpolate(step.cwd)
            try:
                step_cwd = self.validate_path(step_cwd)
            except ValueError as e:
                print(f"Warning at step {step_index}: {e}")
                # Fall back to current_cwd on path traversal
                step_cwd = self.current_cwd

        if action == "type":
            content = self.interpolate(step.content or "")
            self.type_text(content, step.typing_speed)
            return True

        elif action == "execute":
            self.add_output("\n")
            if not self.dry_run:
                time.sleep(0.1)
            return True

        elif action == "run":
            # Combined type + execute
            content = self.interpolate(step.content or "")
            self.type_text(content, step.typing_speed)
            self.add_output("\n")

            if not self.dry_run:
                time.sleep(0.1)

            output, returncode = self.execute_command(content, step_cwd)

            # Check for errors
            errors = self.check_for_errors(output, step, step_index)
            self.detected_errors.extend(errors)

            # Handle "after" narration (timed to appear after command completes)
            if step.narration and "after" in step.narration:
                self.add_narration(step.narration["after"], step_index, "after")

            # Post-execute pause
            pause_ms = step.duration or self.settings.post_execute_pause
            if not self.dry_run:
                time.sleep(pause_ms / 1000.0)

            # Show prompt again
            self.add_output("\n$ ")

            return returncode == 0 or step.expect_error

        elif action == "pause":
            duration_ms = step.duration or 1000
            if not self.dry_run:
                time.sleep(duration_ms / 1000.0)
            return True

        elif action == "clear":
            # Send ANSI clear sequence
            self.add_output("\033[2J\033[H")
            return True

        elif action == "section":
            # Add section marker
            self.sections.append(Section(step.name or "Untitled", self.get_timestamp()))
            # Optionally output section header
            if step.content:
                content = self.interpolate(step.content)
                self.add_output(f"\n# {content}\n")
            return True

        elif action == "screenshot":
            # Add screenshot marker in output (for narration sync)
            marker = step.name or f"screenshot_{step_index}"
            self.add_output(f"\n[SCREENSHOT: {marker}]\n")
            return True

        elif action == "comment":
            # Add visible comment in terminal
            content = self.interpolate(step.content or "")
            self.add_output(f"\n# {content}\n")
            return True

        elif action == "foreach":
            # Iterate over items
            items = step.items or []
            template = step.template or []

            for item in items:
                # Set item variable
                self.variables["item"] = item

                # Execute template steps
                for tmpl_step_data in template:
                    tmpl_step = parse_step(tmpl_step_data)
                    if not self.run_step(tmpl_step, step_index):
                        return False

            return True

        elif action == "set":
            # Set a variable
            if step.name and step.content:
                self.variables[step.name] = self.interpolate(step.content)
            return True

        elif action == "cd":
            # Change working directory with validation
            new_dir = self.interpolate(step.content or "")
            try:
                validated_dir = self.validate_path(new_dir)
                self.current_cwd = validated_dir
            except ValueError as e:
                print(f"Warning at step {step_index}: {e}")
                # Don't change directory on path traversal attempt

            # Show cd command in terminal
            self.type_text(f"cd {step.content}")
            self.add_output("\n$ ")
            return True

        else:
            print(f"Warning: Unknown action '{action}' at step {step_index}")
            return True

    def record(self, steps: list[Step]) -> bool:
        """Record all steps. Returns True if no errors detected."""
        self.start_time = time.time()

        # Initial prompt
        if not self.dry_run:
            self.add_output("$ ")

        success = True
        for i, step in enumerate(steps):
            if not self.run_step(step, i):
                success = False
                if self.assert_only:
                    break

        return success and len(self.detected_errors) == 0

    def to_cast(self) -> dict:
        """Generate asciinema cast v2 format."""
        header = {
            "version": CAST_VERSION,
            "width": self.settings.cols,
            "height": self.settings.rows,
            "timestamp": int(time.time()),
            "env": {"SHELL": self.settings.shell, "TERM": DEFAULT_TERM},
        }

        if self.settings.title:
            header["title"] = self.settings.title

        # Add section markers to metadata
        if self.sections:
            header["markers"] = [
                {"time": s.timestamp, "label": s.name} for s in self.sections
            ]

        # Add extended metadata
        if any(
            [
                self.metadata.name,
                self.metadata.version,
                self.metadata.description,
                self.metadata.author,
                self.metadata.source_checksum,
            ]
        ):
            header["metadata"] = {}
            if self.metadata.name:
                header["metadata"]["name"] = self.metadata.name
            if self.metadata.version:
                header["metadata"]["version"] = self.metadata.version
            if self.metadata.description:
                header["metadata"]["description"] = self.metadata.description
            if self.metadata.author:
                header["metadata"]["author"] = self.metadata.author
            if self.metadata.source_checksum:
                header["metadata"]["source_checksum"] = self.metadata.source_checksum
            if self.metadata.recorded_at:
                header["metadata"]["recorded_at"] = self.metadata.recorded_at

        # Format events
        events = [[e.timestamp, e.event_type, e.data] for e in self.events]

        return {"header": header, "events": events}

    def write_cast(self, output_path: Path):
        """Write cast file in asciinema v2 format."""
        cast_data = self.to_cast()

        with open(output_path, "w") as f:
            # Write header as first line
            f.write(json.dumps(cast_data["header"]) + "\n")
            # Write events
            for event in cast_data["events"]:
                f.write(json.dumps(event) + "\n")

    def write_narration_srt(self, output_path: Path):
        """Write narration timing as SRT subtitle file."""
        with open(output_path, "w") as f:
            for i, entry in enumerate(self.narrations, 1):
                start = self._format_srt_time(entry.start_time)
                end = self._format_srt_time(entry.end_time)
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{entry.text}\n\n")

    def write_narration_vtt(self, output_path: Path):
        """Write narration timing as WebVTT subtitle file."""
        with open(output_path, "w") as f:
            f.write("WEBVTT\n\n")
            for i, entry in enumerate(self.narrations, 1):
                start = self._format_vtt_time(entry.start_time)
                end = self._format_vtt_time(entry.end_time)
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{entry.text}\n\n")

    @staticmethod
    def _format_srt_time(seconds: float) -> str:
        """Format time for SRT (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    @staticmethod
    def _format_vtt_time(seconds: float) -> str:
        """Format time for VTT (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def parse_step(data: dict) -> Step:
    """Parse a step from YAML data."""
    return Step(
        action=data.get("action", ""),
        content=data.get("content"),
        duration=data.get("duration"),
        cwd=data.get("cwd"),
        typing_speed=data.get("typing_speed"),
        ignore_error_patterns=data.get("ignore_error_patterns", []),
        expect_error=data.get("expect_error", False),
        narration=data.get("narration"),
        name=data.get("name"),
        items=data.get("items"),
        template=data.get("template"),
    )


def parse_error_detection(data: dict) -> ErrorDetectionConfig:
    """Parse error detection configuration."""
    config = ErrorDetectionConfig()

    if "mode" in data:
        config.mode = data["mode"]
    if "patterns" in data:
        config.patterns = data["patterns"]
    if "safe_contexts" in data:
        config.safe_contexts = data["safe_contexts"]
    if "ignore_patterns" in data:
        config.ignore_patterns = data["ignore_patterns"]

    # Re-compile patterns after loading from YAML
    config.compile_patterns()

    return config


def parse_settings(data: dict) -> Settings:
    """Parse settings from YAML data."""
    settings = Settings()

    if "shell" in data:
        settings.shell = data["shell"]
    if "cwd" in data:
        settings.cwd = data["cwd"]
    if "env" in data:
        settings.env = data["env"]
    if "typing_speed" in data:
        settings.typing_speed = data["typing_speed"]
    if "post_execute_pause" in data:
        settings.post_execute_pause = data["post_execute_pause"]
    if "cols" in data:
        settings.cols = data["cols"]
    if "rows" in data:
        settings.rows = data["rows"]
    if "title" in data:
        settings.title = data["title"]
    if "error_detection" in data:
        settings.error_detection = parse_error_detection(data["error_detection"])

    return settings


def parse_metadata(data: dict) -> Metadata:
    """Parse metadata from YAML data."""
    return Metadata(
        name=data.get("name"),
        version=data.get("version"),
        description=data.get("description"),
        author=data.get("author"),
    )


def compute_checksum(path: Path) -> str:
    """Compute SHA256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()[:16]


def load_demo_script(
    path: Path,
) -> tuple[Settings, dict[str, str], list[Step], Metadata]:
    """Load and parse a demo script YAML file."""
    with open(path) as f:
        data = yaml.safe_load(f)

    settings = parse_settings(data.get("settings", {}))
    variables = data.get("variables", {})
    steps = [parse_step(s) for s in data.get("steps", [])]
    metadata = parse_metadata(data.get("metadata", {}))

    # Compute source checksum
    metadata.source_checksum = compute_checksum(path)
    metadata.recorded_at = datetime.now().isoformat()

    return settings, variables, steps, metadata


def preview_cast(cast_path: Path):
    """Play back the cast file using asciinema."""
    try:
        subprocess.run(["asciinema", "play", str(cast_path)], check=True)
    except FileNotFoundError:
        print("Error: asciinema not found. Install with: pip install asciinema")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error playing cast: {e}")
        sys.exit(1)


def export_gif(cast_path: Path, gif_path: Path, theme: str = "monokai"):
    """Export cast file to GIF using agg."""
    try:
        subprocess.run(
            [
                "agg",
                "--theme",
                theme,
                str(cast_path),
                str(gif_path),
            ],
            check=True,
        )
        print(f"GIF exported to: {gif_path}")
    except FileNotFoundError:
        print("Error: agg (asciinema-agg) not found.")
        print("Install with: cargo install --git https://github.com/asciinema/agg")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error exporting GIF: {e}")
        sys.exit(1)


def print_validation_report(recorder: TerminalRecorder, success: bool):
    """Print a validation report."""
    print("\n" + "=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)

    if recorder.metadata.source_checksum:
        print(f"\nSource checksum: {recorder.metadata.source_checksum}")

    if recorder.sections:
        print(f"\nSections ({len(recorder.sections)}):")
        for section in recorder.sections:
            print(f"  - {section.name} @ {section.timestamp:.2f}s")

    if recorder.narrations:
        print(f"\nNarration entries ({len(recorder.narrations)}):")
        for entry in recorder.narrations[:5]:  # Show first 5
            print(f"  - [{entry.start_time:.1f}s] {entry.text[:50]}...")
        if len(recorder.narrations) > 5:
            print(f"  ... and {len(recorder.narrations) - 5} more")

    if recorder.detected_errors:
        print(f"\nDetected Errors ({len(recorder.detected_errors)}):")
        for error in recorder.detected_errors:
            print(f"  Step {error['step']}, Line {error['line']}:")
            print(f"    Pattern: {error['pattern']}")
            print(f"    Content: {error['content'][:80]}...")
    else:
        print("\nNo errors detected.")

    print("\n" + "-" * 60)
    if success:
        print("STATUS: PASSED")
    else:
        print("STATUS: FAILED")
    print("=" * 60)


def run_parallel_validation(
    scripts: list[Path], max_workers: int = 4
) -> tuple[bool, dict[str, Any]]:
    """Run validation on multiple scripts in parallel for CI."""
    results = {}

    def validate_script(script_path: Path) -> tuple[Path, bool, list[dict]]:
        """Validate a single script."""
        try:
            settings, variables, steps, metadata = load_demo_script(script_path)
            recorder = TerminalRecorder(settings)
            recorder.variables = variables
            recorder.metadata = metadata
            recorder.dry_run = True
            recorder.assert_only = True

            success = recorder.record(steps)
            return script_path, success, recorder.detected_errors
        except yaml.YAMLError as e:
            return script_path, False, [{"error": f"YAML parse error: {e}"}]
        except (FileNotFoundError, PermissionError, OSError) as e:
            return script_path, False, [{"error": f"File error: {e}"}]
        except (KeyError, TypeError, ValueError) as e:
            return script_path, False, [{"error": f"Script structure error: {e}"}]
        except RuntimeError as e:
            return script_path, False, [{"error": f"Runtime error: {e}"}]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(validate_script, s): s for s in scripts}

        for future in concurrent.futures.as_completed(futures):
            script_path, success, errors = future.result()
            results[str(script_path)] = {
                "success": success,
                "errors": errors,
            }

    all_success = all(r["success"] for r in results.values())
    return all_success, results


def main():
    parser = argparse.ArgumentParser(
        description="YAML-based terminal demo recorder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "script", type=Path, nargs="+", help="YAML demo script file(s)"
    )
    parser.add_argument("-o", "--output", type=Path, help="Output .cast file path")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate script without recording (runs commands but doesn't record timing)",
    )
    parser.add_argument(
        "--assert-only",
        action="store_true",
        help="Run commands and check for errors, exit with failure if errors found",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run validation on multiple scripts in parallel (CI mode)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Play back recording after creation",
    )
    parser.add_argument(
        "--export-gif",
        type=Path,
        help="Export to GIF file (requires agg)",
    )
    parser.add_argument(
        "--gif-theme",
        default="monokai",
        help="Theme for GIF export (default: monokai)",
    )
    parser.add_argument(
        "--narration-srt",
        type=Path,
        help="Export narration timing as SRT subtitle file",
    )
    parser.add_argument(
        "--narration-vtt",
        type=Path,
        help="Export narration timing as WebVTT subtitle file",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        help="Show progress bar during recording",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Handle parallel validation mode
    if args.parallel:
        scripts = []
        for script in args.script:
            if script.is_dir():
                scripts.extend(script.glob("*.yaml"))
                scripts.extend(script.glob("*.yml"))
            else:
                scripts.append(script)

        if not scripts:
            print("Error: No YAML scripts found")
            sys.exit(1)

        print(f"Validating {len(scripts)} scripts in parallel...")
        success, results = run_parallel_validation(scripts, args.workers)

        # Print results
        print("\n" + "=" * 60)
        print("PARALLEL VALIDATION RESULTS")
        print("=" * 60)
        for script_path, result in results.items():
            status = "PASS" if result["success"] else "FAIL"
            print(f"\n  {status}: {script_path}")
            if result["errors"]:
                for err in result["errors"][:3]:
                    if "error" in err:
                        print(f"       Error: {err['error']}")
                    else:
                        print(f"       Step {err.get('step', '?')}: {err.get('content', '')[:50]}")

        print("\n" + "-" * 60)
        passed = sum(1 for r in results.values() if r["success"])
        print(f"TOTAL: {passed}/{len(results)} passed")
        print("=" * 60)

        sys.exit(0 if success else 1)

    # Single script mode
    if len(args.script) > 1:
        print("Error: Multiple scripts require --parallel flag")
        sys.exit(1)

    script_path = args.script[0]

    # Validate arguments
    if not script_path.exists():
        print(f"Error: Script file not found: {script_path}")
        sys.exit(1)

    if not args.dry_run and not args.assert_only and not args.output:
        print(
            "Error: Output file required (use -o) unless using --dry-run or --assert-only"
        )
        sys.exit(1)

    # Load script
    try:
        settings, variables, steps, metadata = load_demo_script(script_path)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: Script file not found: {e.filename}")
        sys.exit(1)
    except PermissionError as e:
        print(f"Error: Permission denied reading script: {e.filename}")
        sys.exit(1)
    except OSError as e:
        print(f"Error loading script (I/O error): {e}")
        sys.exit(1)
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error in script structure: {e}")
        sys.exit(1)

    if args.verbose:
        print(f"Loaded {len(steps)} steps from {script_path}")
        if variables:
            print(f"Variables: {', '.join(variables.keys())}")
        if metadata.source_checksum:
            print(f"Source checksum: {metadata.source_checksum}")

    # Create recorder
    recorder = TerminalRecorder(settings)
    recorder.variables = variables
    recorder.metadata = metadata
    recorder.dry_run = args.dry_run
    recorder.assert_only = args.assert_only

    # Enable progress tracking
    if args.progress and not args.dry_run and not args.assert_only:
        recorder.progress = ProgressTracker(len(steps))

    # Record
    mode = "Validating" if args.dry_run else "Recording"
    print(f"{mode} demo...")
    success = recorder.record(steps)

    # Finish progress
    if recorder.progress:
        recorder.progress.finish()

    # Print report
    if args.dry_run or args.assert_only or args.verbose:
        print_validation_report(recorder, success)

    # Write output
    if args.output and not args.assert_only:
        recorder.write_cast(args.output)
        print(f"\nCast file written to: {args.output}")

    # Write narration files
    if args.narration_srt and recorder.narrations:
        recorder.write_narration_srt(args.narration_srt)
        print(f"Narration SRT written to: {args.narration_srt}")

    if args.narration_vtt and recorder.narrations:
        recorder.write_narration_vtt(args.narration_vtt)
        print(f"Narration VTT written to: {args.narration_vtt}")

    # Preview
    if args.preview and args.output and args.output.exists():
        print("\nPlaying back recording...")
        preview_cast(args.output)

    # Export GIF
    if args.export_gif and args.output and args.output.exists():
        print(f"\nExporting GIF to {args.export_gif}...")
        export_gif(args.output, args.export_gif, args.gif_theme)

    # Exit code
    if args.assert_only and not success:
        sys.exit(1)
    elif recorder.detected_errors and not args.dry_run:
        print(f"\nWarning: {len(recorder.detected_errors)} potential error(s) detected")
        sys.exit(0)  # Don't fail on warnings in normal mode

    sys.exit(0)


if __name__ == "__main__":
    main()
