"""Tests for terminal recorder utilities."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from utils.terminal_recorder import (
    AsciicastWriter,
    TerminalAction,
    TerminalConfig,
    TerminalRecorder,
    TerminalRecordingResult,
    TerminalScene,
    parse_terminal_script,
)


class TestTerminalConfig:
    """Tests for TerminalConfig dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        config = TerminalConfig()

        assert config.cols == 120
        assert config.rows == 40
        assert config.shell == "/bin/zsh"
        assert config.typing_speed_min == 0.03
        assert config.typing_speed_max == 0.12
        assert config.mistake_probability == 0.02

    def test_custom_values(self):
        """Should accept custom values."""
        config = TerminalConfig(
            cols=80,
            rows=24,
            shell="/bin/bash",
            mistake_probability=0.0,  # No typos
        )

        assert config.cols == 80
        assert config.rows == 24
        assert config.shell == "/bin/bash"
        assert config.mistake_probability == 0.0


class TestTerminalAction:
    """Tests for TerminalAction dataclass."""

    def test_command_action(self):
        """Should represent a command action."""
        action = TerminalAction(
            action_type="command",
            text="npm install",
            delay_after=2000,
        )

        assert action.action_type == "command"
        assert action.text == "npm install"
        assert action.delay_after == 2000

    def test_wait_for_action(self):
        """Should represent a wait_for action."""
        action = TerminalAction(
            action_type="wait_for",
            pattern="Success",
            delay_after=5000,
        )

        assert action.action_type == "wait_for"
        assert action.pattern == "Success"


class TestTerminalScene:
    """Tests for TerminalScene dataclass."""

    def test_scene_with_actions(self):
        """Should contain actions."""
        scene = TerminalScene(
            name="Install package",
            actions=[
                TerminalAction(action_type="command", text="npm install"),
                TerminalAction(action_type="wait", delay_after=1000),
            ],
            narration_notes="Install the dependencies",
        )

        assert scene.name == "Install package"
        assert len(scene.actions) == 2
        assert scene.narration_notes == "Install the dependencies"


class TestTerminalRecordingResult:
    """Tests for TerminalRecordingResult dataclass."""

    def test_success_result(self):
        """Should represent successful recording."""
        result = TerminalRecordingResult(
            status="success",
            cast_path=Path("/tmp/demo.cast"),
            duration_seconds=45.0,
        )

        assert result.status == "success"
        assert result.cast_path == Path("/tmp/demo.cast")
        assert result.duration_seconds == 45.0

    def test_failed_result(self):
        """Should represent failed recording."""
        result = TerminalRecordingResult(
            status="failed",
            error="Shell not found",
        )

        assert result.status == "failed"
        assert result.error == "Shell not found"

    def test_to_dict(self):
        """Should convert to dictionary."""
        result = TerminalRecordingResult(
            status="success",
            cast_path=Path("/tmp/demo.cast"),
            duration_seconds=30.0,
        )

        d = result.to_dict()

        assert d["status"] == "success"
        assert d["cast_path"] == "/tmp/demo.cast"
        assert d["duration_seconds"] == 30.0


class TestAsciicastWriter:
    """Tests for AsciicastWriter class."""

    def test_writes_header(self, tmp_path):
        """Should write asciicast v2 header."""
        cast_path = tmp_path / "test.cast"

        with AsciicastWriter(cast_path, width=80, height=24) as writer:
            pass  # Just test header writing

        # Read and parse header
        with open(cast_path) as f:
            header_line = f.readline()
            header = json.loads(header_line)

        assert header["version"] == 2
        assert header["width"] == 80
        assert header["height"] == 24
        assert "timestamp" in header

    def test_writes_output_events(self, tmp_path):
        """Should write output events."""
        cast_path = tmp_path / "test.cast"

        with AsciicastWriter(cast_path, width=80, height=24) as writer:
            writer.write_output("hello")
            writer.write_output("world")

        # Read events
        with open(cast_path) as f:
            lines = f.readlines()

        # Header + 2 events
        assert len(lines) == 3

        # Parse second event
        event = json.loads(lines[1])
        assert event[1] == "o"  # output event
        assert event[2] == "hello"

    def test_tracks_elapsed_time(self, tmp_path):
        """Should track elapsed time for events."""
        import time

        cast_path = tmp_path / "test.cast"

        with AsciicastWriter(cast_path, width=80, height=24) as writer:
            writer.write_output("first")
            time.sleep(0.1)
            writer.write_output("second")

        with open(cast_path) as f:
            lines = f.readlines()

        event1 = json.loads(lines[1])
        event2 = json.loads(lines[2])

        # Second event should have later timestamp
        assert event2[0] > event1[0]


class TestParseTerminalScript:
    """Tests for parse_terminal_script function."""

    def test_parses_simple_script(self):
        """Should parse YAML script into scenes."""
        yaml_content = """
scenes:
  - name: "Install package"
    actions:
      - command: "npm install"
        delay_after: 2000
  - name: "Run tests"
    actions:
      - command: "npm test"
        delay_after: 3000
"""

        scenes = parse_terminal_script(yaml_content)

        assert len(scenes) == 2
        assert scenes[0].name == "Install package"
        assert scenes[0].actions[0].action_type == "command"
        assert scenes[0].actions[0].text == "npm install"
        assert scenes[0].actions[0].delay_after == 2000

    def test_parses_wait_for_action(self):
        """Should parse wait_for actions."""
        yaml_content = """
scenes:
  - name: "Wait for output"
    actions:
      - wait_for: "Success"
        timeout: 10000
"""

        scenes = parse_terminal_script(yaml_content)

        assert len(scenes[0].actions) == 1
        action = scenes[0].actions[0]
        assert action.action_type == "wait_for"
        assert action.pattern == "Success"

    def test_parses_complex_script(self):
        """Should parse complex script with multiple action types."""
        yaml_content = """
scenes:
  - name: "Setup"
    narration_notes: "Setting up the environment"
    actions:
      - command: "mkdir project"
        delay_after: 500
      - type: command
        text: "cd project"
        delay_after: 300
      - wait_for: "$"
        timeout: 5000
"""

        scenes = parse_terminal_script(yaml_content)

        assert scenes[0].name == "Setup"
        assert scenes[0].narration_notes == "Setting up the environment"
        assert len(scenes[0].actions) == 3


class TestTerminalRecorder:
    """Tests for TerminalRecorder class."""

    @pytest.fixture
    def recorder(self):
        """Create a recorder instance."""
        return TerminalRecorder()

    @pytest.fixture
    def recorder_with_config(self):
        """Create a recorder with custom config."""
        config = TerminalConfig(
            cols=80,
            rows=24,
            mistake_probability=0.0,  # No typos for testing
        )
        return TerminalRecorder(config)

    def test_init_with_default_config(self, recorder):
        """Should initialize with default config."""
        assert recorder.config.cols == 120
        assert recorder.config.rows == 40

    def test_init_with_custom_config(self, recorder_with_config):
        """Should accept custom config."""
        assert recorder_with_config.config.cols == 80
        assert recorder_with_config.config.mistake_probability == 0.0
