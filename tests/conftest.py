"""Pytest configuration and fixtures for demo-creator tests."""

import os
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def tmp_demo_dir(tmp_path):
    """Create a temporary demo directory structure."""
    demo_dir = tmp_path / ".demo" / "test-demo"
    demo_dir.mkdir(parents=True)
    return demo_dir


@pytest.fixture
def mock_playwright_page():
    """Create a mock Playwright page object."""
    from unittest.mock import MagicMock

    page = MagicMock()
    page.url = "http://localhost:3000"

    # Setup common page methods
    page.goto.return_value = None
    page.wait_for_load_state.return_value = None
    page.screenshot.return_value = None
    page.click.return_value = None
    page.fill.return_value = None

    return page


@pytest.fixture
def sample_manifest_data():
    """Sample manifest data for testing."""
    return {
        "demo_id": "ISSUE-123-test-feature",
        "linear_issue": "ISSUE-123",
        "git_sha": "abc1234",
        "git_branch": "user/issue-123-test-feature",
        "created_at": "2025-01-08T10:00:00Z",
        "current_stage": 3,
        "completed_stages": [1, 2],
        "failed_stages": [],
        "stage_outputs": {
            "1": {"outline_path": "outline.md"},
            "2": {"script_path": "script.py"},
        },
        "errors": [],
        "brand_voice_cache": {
            "path": ".demo/templates/narration-voice.md",
            "last_refreshed": None,
        },
    }


@pytest.fixture
def sample_selectors():
    """Sample selector map for testing."""
    return {
        "search_input": "[data-testid='search-input']",
        "submit_button": "button:has-text('Search')",
        "results_list": ".results-container",
        "filter_dropdown": "[aria-label='Filter options']",
    }


@pytest.fixture
def sample_narration_segments():
    """Sample narration segments for testing."""
    return [
        {
            "scene": 1,
            "text": "Welcome to our drug search feature.",
            "start_time": 0,
            "duration": 3.5,
        },
        {
            "scene": 2,
            "text": "Let me show you how to filter results.",
            "start_time": 5,
            "duration": 4.0,
        },
        {
            "scene": 3,
            "text": "And that's our powerful search in action!",
            "start_time": 12,
            "duration": 3.0,
        },
    ]


@pytest.fixture
def sample_terminal_scenes():
    """Sample terminal demo scenes for testing."""
    return [
        {
            "name": "Install the CLI",
            "actions": [
                {"type": "command", "text": "npm install -g @example/my-cli", "delay_after": 2000},
            ],
        },
        {
            "name": "Initialize project",
            "actions": [
                {"type": "command", "text": "fib init my-project", "delay_after": 3000},
                {"type": "wait_for", "pattern": "Project initialized"},
            ],
        },
    ]


@pytest.fixture(autouse=True)
def cleanup_env(monkeypatch):
    """Clean up environment variables that might affect tests."""
    # Remove any API keys that might cause real API calls
    for key in ["ELEVENLABS_API_KEY", "HEYGEN_API_KEY", "GOOGLE_APPLICATION_CREDENTIALS"]:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def mock_config():
    """Sample project configuration."""
    return {
        "version": 1,
        "project": {
            "name": "test-project",
            "tech_stack": "nextjs",
        },
        "app": {
            "base_url": "http://localhost:3000",
            "health_check": "/api/health",
        },
        "auth": {
            "strategy": "none",
        },
        "recording": {
            "mode": "local",
            "viewport": {
                "width": 1920,
                "height": 1080,
            },
        },
        "voice": {
            "provider": "elevenlabs",
        },
        "avatar": {
            "enabled": False,
        },
        "output": {
            "upload_to": "gcs",
        },
    }
