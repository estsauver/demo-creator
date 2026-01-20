"""
Global credentials management for demo-creator.

Handles loading and validation of credentials from ~/.claude/demo-credentials.yaml
and environment variables.
"""

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ElevenLabsCredentials:
    """ElevenLabs API credentials."""

    api_key: Optional[str] = None
    default_voice_id: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.api_key)


@dataclass
class HeyGenCredentials:
    """HeyGen API credentials."""

    api_key: Optional[str] = None
    default_avatar_id: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.api_key)


@dataclass
class GCSCredentials:
    """Google Cloud Storage credentials."""

    credentials_path: Optional[str] = None
    default_bucket: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if credentials are configured."""
        if self.credentials_path:
            return Path(self.credentials_path).exists()
        # Check for application default credentials
        return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))


@dataclass
class SlackCredentials:
    """Slack integration credentials."""

    default_webhook_url: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.default_webhook_url)


@dataclass
class LinearCredentials:
    """Linear integration credentials."""

    api_key: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        """Check if credentials are configured."""
        return bool(self.api_key)


@dataclass
class Credentials:
    """Container for all credentials."""

    elevenlabs: ElevenLabsCredentials = field(default_factory=ElevenLabsCredentials)
    heygen: HeyGenCredentials = field(default_factory=HeyGenCredentials)
    gcs: GCSCredentials = field(default_factory=GCSCredentials)
    slack: SlackCredentials = field(default_factory=SlackCredentials)
    linear: LinearCredentials = field(default_factory=LinearCredentials)

    def get_status(self) -> Dict[str, bool]:
        """Get status of all credentials."""
        return {
            "elevenlabs": self.elevenlabs.is_valid,
            "heygen": self.heygen.is_valid,
            "gcs": self.gcs.is_valid,
            "slack": self.slack.is_valid,
            "linear": self.linear.is_valid,
        }

    def get_missing(self) -> list:
        """Get list of missing required credentials."""
        missing = []
        if not self.elevenlabs.is_valid:
            missing.append("ElevenLabs API key (for voice narration)")
        if not self.gcs.is_valid:
            missing.append("GCS credentials (for video upload)")
        return missing

    def get_optional_missing(self) -> list:
        """Get list of missing optional credentials."""
        missing = []
        if not self.heygen.is_valid:
            missing.append("HeyGen API key (for avatar generation)")
        if not self.slack.is_valid:
            missing.append("Slack webhook (for notifications)")
        if not self.linear.is_valid:
            missing.append("Linear API key (for issue updates)")
        return missing


def get_credentials_path() -> Path:
    """Get path to credentials file."""
    return Path.home() / ".claude" / "demo-credentials.yaml"


def load_credentials() -> Credentials:
    """
    Load credentials from file and environment variables.

    Priority: Environment variables > Credentials file

    Returns:
        Credentials object with loaded values
    """
    creds = Credentials()

    # Load from file first
    creds_path = get_credentials_path()
    if creds_path.exists():
        try:
            import yaml

            with open(creds_path) as f:
                data = yaml.safe_load(f) or {}

            # ElevenLabs
            if "elevenlabs" in data:
                creds.elevenlabs = ElevenLabsCredentials(
                    api_key=data["elevenlabs"].get("api_key"),
                    default_voice_id=data["elevenlabs"].get("default_voice_id"),
                )

            # HeyGen
            if "heygen" in data:
                creds.heygen = HeyGenCredentials(
                    api_key=data["heygen"].get("api_key"),
                    default_avatar_id=data["heygen"].get("default_avatar_id"),
                )

            # GCS
            if "gcs" in data:
                creds.gcs = GCSCredentials(
                    credentials_path=data["gcs"].get("credentials_path"),
                    default_bucket=data["gcs"].get("default_bucket"),
                )

            # Slack
            if "slack" in data:
                creds.slack = SlackCredentials(
                    default_webhook_url=data["slack"].get("default_webhook_url"),
                )

            # Linear
            if "linear" in data:
                creds.linear = LinearCredentials(
                    api_key=data["linear"].get("api_key"),
                )

        except Exception as e:
            logger.warning(f"Failed to load credentials from {creds_path}: {e}")

    # Override with environment variables
    if os.getenv("ELEVENLABS_API_KEY"):
        creds.elevenlabs.api_key = os.getenv("ELEVENLABS_API_KEY")
    if os.getenv("ELEVENLABS_VOICE_ID"):
        creds.elevenlabs.default_voice_id = os.getenv("ELEVENLABS_VOICE_ID")

    if os.getenv("HEYGEN_API_KEY"):
        creds.heygen.api_key = os.getenv("HEYGEN_API_KEY")
    if os.getenv("HEYGEN_AVATAR_ID"):
        creds.heygen.default_avatar_id = os.getenv("HEYGEN_AVATAR_ID")

    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        creds.gcs.credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if os.getenv("GCS_BUCKET_NAME"):
        creds.gcs.default_bucket = os.getenv("GCS_BUCKET_NAME")

    if os.getenv("SLACK_WEBHOOK_URL"):
        creds.slack.default_webhook_url = os.getenv("SLACK_WEBHOOK_URL")

    if os.getenv("LINEAR_API_KEY"):
        creds.linear.api_key = os.getenv("LINEAR_API_KEY")

    return creds


def save_credentials(creds: Credentials) -> None:
    """
    Save credentials to file.

    Note: Does not save values that came from environment variables.

    Args:
        creds: Credentials to save
    """
    import yaml

    creds_path = get_credentials_path()
    creds_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"version": 1}

    if creds.elevenlabs.api_key:
        data["elevenlabs"] = {
            "api_key": creds.elevenlabs.api_key,
        }
        if creds.elevenlabs.default_voice_id:
            data["elevenlabs"]["default_voice_id"] = creds.elevenlabs.default_voice_id

    if creds.heygen.api_key:
        data["heygen"] = {
            "api_key": creds.heygen.api_key,
        }
        if creds.heygen.default_avatar_id:
            data["heygen"]["default_avatar_id"] = creds.heygen.default_avatar_id

    if creds.gcs.credentials_path:
        data["gcs"] = {
            "credentials_path": creds.gcs.credentials_path,
        }
        if creds.gcs.default_bucket:
            data["gcs"]["default_bucket"] = creds.gcs.default_bucket

    if creds.slack.default_webhook_url:
        data["slack"] = {
            "default_webhook_url": creds.slack.default_webhook_url,
        }

    if creds.linear.api_key:
        data["linear"] = {
            "api_key": creds.linear.api_key,
        }

    with open(creds_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    # Set restrictive permissions
    creds_path.chmod(0o600)

    logger.info(f"Credentials saved to {creds_path}")


def validate_elevenlabs_key(api_key: Optional[str] = None) -> bool:
    """
    Validate ElevenLabs API key by making a test request.

    Args:
        api_key: API key to validate (uses loaded creds if not provided)

    Returns:
        True if key is valid
    """
    import requests

    if not api_key:
        creds = load_credentials()
        api_key = creds.elevenlabs.api_key

    if not api_key:
        return False

    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def validate_heygen_key(api_key: Optional[str] = None) -> bool:
    """
    Validate HeyGen API key by making a test request.

    Args:
        api_key: API key to validate (uses loaded creds if not provided)

    Returns:
        True if key is valid
    """
    import requests

    if not api_key:
        creds = load_credentials()
        api_key = creds.heygen.api_key

    if not api_key:
        return False

    try:
        response = requests.get(
            "https://api.heygen.com/v2/avatars",
            headers={"X-Api-Key": api_key},
            timeout=10,
        )
        return response.status_code == 200
    except Exception:
        return False


def validate_gcs_credentials(credentials_path: Optional[str] = None) -> bool:
    """
    Validate GCS credentials.

    Args:
        credentials_path: Path to credentials (uses env/loaded if not provided)

    Returns:
        True if credentials are valid
    """
    try:
        from google.cloud import storage

        if credentials_path:
            client = storage.Client.from_service_account_json(credentials_path)
        else:
            client = storage.Client()

        # Try to list buckets as a validation
        list(client.list_buckets(max_results=1))
        return True
    except Exception:
        return False


def print_credentials_status() -> None:
    """Print formatted credentials status to console."""
    creds = load_credentials()
    status = creds.get_status()

    print("\nCredentials Status:")
    print("-" * 40)

    for name, valid in status.items():
        status_str = "Found" if valid else "Not found"
        symbol = "+" if valid else "-"
        print(f"  [{symbol}] {name}: {status_str}")

    missing = creds.get_missing()
    if missing:
        print("\nRequired (missing):")
        for m in missing:
            print(f"  - {m}")

    optional = creds.get_optional_missing()
    if optional:
        print("\nOptional (not configured):")
        for o in optional:
            print(f"  - {o}")

    print()


def get_credentials_template() -> str:
    """Get template for credentials file."""
    return """# Demo Creator Credentials
# Store sensitive API keys and credentials here
# This file should NOT be committed to version control

version: 1

# Required for voice narration
elevenlabs:
  api_key: "sk_..."
  default_voice_id: "ErXwobaYiN019PkySvjV"

# Required for video upload
gcs:
  credentials_path: "/path/to/gcs-service-account.json"
  default_bucket: "your-demos-bucket"

# Optional: AI presenter avatar
heygen:
  api_key: "..."
  default_avatar_id: "..."

# Optional: Slack notifications
slack:
  default_webhook_url: "https://hooks.slack.com/..."

# Optional: Linear issue updates
linear:
  api_key: "lin_..."
"""
