"""Tests for credentials utilities."""

import tempfile
from pathlib import Path

import pytest
import yaml


class TestCredentials:
    """Tests for credentials module."""

    @pytest.fixture
    def temp_home(self, tmp_path, monkeypatch):
        """Create a temporary home directory."""
        monkeypatch.setenv("HOME", str(tmp_path))
        return tmp_path

    def test_load_empty_credentials(self, temp_home):
        """Should return empty credentials when file doesn't exist."""
        from utils.credentials import load_credentials

        creds = load_credentials()

        # All should be invalid (not configured)
        assert not creds.elevenlabs.is_valid
        assert not creds.heygen.is_valid

    def test_load_credentials_from_file(self, temp_home):
        """Should load credentials from file."""
        from utils.credentials import load_credentials, get_credentials_path

        # Create credentials file
        creds_path = get_credentials_path()
        creds_path.parent.mkdir(parents=True)

        creds_data = {
            "version": 1,
            "elevenlabs": {
                "api_key": "test_key_123",
                "default_voice_id": "voice_id_456",
            },
            "heygen": {
                "api_key": "heygen_key",
            },
        }

        with open(creds_path, "w") as f:
            yaml.dump(creds_data, f)

        creds = load_credentials()

        assert creds.elevenlabs.api_key == "test_key_123"
        assert creds.elevenlabs.default_voice_id == "voice_id_456"
        assert creds.heygen.api_key == "heygen_key"
        assert creds.elevenlabs.is_valid
        assert creds.heygen.is_valid

    def test_env_vars_override_file(self, temp_home, monkeypatch):
        """Environment variables should override file values."""
        from utils.credentials import load_credentials, get_credentials_path

        # Create credentials file
        creds_path = get_credentials_path()
        creds_path.parent.mkdir(parents=True)

        creds_data = {
            "version": 1,
            "elevenlabs": {
                "api_key": "file_key",
            },
        }

        with open(creds_path, "w") as f:
            yaml.dump(creds_data, f)

        # Set env var
        monkeypatch.setenv("ELEVENLABS_API_KEY", "env_key")

        creds = load_credentials()

        # Env var should take precedence
        assert creds.elevenlabs.api_key == "env_key"

    def test_get_status(self, temp_home, monkeypatch):
        """Should return status of all credentials."""
        from utils.credentials import load_credentials

        monkeypatch.setenv("ELEVENLABS_API_KEY", "key")

        creds = load_credentials()
        status = creds.get_status()

        assert status["elevenlabs"] is True
        assert status["heygen"] is False
        assert status["gcs"] is False

    def test_get_missing_required(self, temp_home):
        """Should list missing required credentials."""
        from utils.credentials import load_credentials

        creds = load_credentials()
        missing = creds.get_missing()

        assert "ElevenLabs" in str(missing)
        assert "GCS" in str(missing)

    def test_save_credentials(self, temp_home):
        """Should save credentials to file."""
        from utils.credentials import (
            Credentials,
            ElevenLabsCredentials,
            save_credentials,
            load_credentials,
        )

        creds = Credentials(
            elevenlabs=ElevenLabsCredentials(
                api_key="saved_key",
                default_voice_id="saved_voice",
            )
        )

        save_credentials(creds)

        # Load and verify
        loaded = load_credentials()
        assert loaded.elevenlabs.api_key == "saved_key"

    def test_credentials_template(self):
        """Should generate valid YAML template."""
        from utils.credentials import get_credentials_template

        template = get_credentials_template()

        # Should be valid YAML
        parsed = yaml.safe_load(template)
        assert "elevenlabs" in parsed
        assert "gcs" in parsed
        assert "version" in parsed
