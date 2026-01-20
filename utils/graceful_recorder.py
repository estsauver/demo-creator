"""
Graceful recording with automatic fallback.

Attempts recording in preferred environment and falls back
to alternatives if the primary fails.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .local_recorder import LocalRecorder, RecordingConfig, RecordingResult

logger = logging.getLogger(__name__)


@dataclass
class RecordingStrategy:
    """Configuration for recording strategy."""

    prefer_kubernetes: bool = False
    fallback_to_local: bool = True
    kubernetes_namespace: str = "infra"
    kubernetes_timeout: int = 600


class GracefulRecorder:
    """
    Records demos with automatic fallback between environments.

    Attempts Kubernetes recording first (if configured), then falls
    back to local Playwright recording.
    """

    def __init__(
        self,
        strategy: Optional[RecordingStrategy] = None,
        local_config: Optional[RecordingConfig] = None,
    ):
        """
        Initialize graceful recorder.

        Args:
            strategy: Recording strategy configuration
            local_config: Configuration for local recording
        """
        self.strategy = strategy or RecordingStrategy()
        self.local_config = local_config
        self._local_recorder = None

    def record(
        self,
        script_path: Path,
        output_dir: Path,
        base_url: Optional[str] = None,
    ) -> RecordingResult:
        """
        Record a demo with automatic fallback.

        Args:
            script_path: Path to Playwright script
            output_dir: Output directory
            base_url: Optional base URL override

        Returns:
            RecordingResult
        """
        if self.strategy.prefer_kubernetes:
            result = self._try_kubernetes_recording(script_path, output_dir, base_url)
            if result.status == "success":
                return result

            if self.strategy.fallback_to_local:
                logger.warning(
                    f"Kubernetes recording failed: {result.error}, "
                    "falling back to local recording"
                )
            else:
                return result

        return self._local_recording(script_path, output_dir, base_url)

    def _try_kubernetes_recording(
        self,
        script_path: Path,
        output_dir: Path,
        base_url: Optional[str],
    ) -> RecordingResult:
        """Attempt recording in Kubernetes."""
        try:
            from .screenenv_job import run_screenenv_job

            result = run_screenenv_job(
                script_path=script_path,
                output_dir=output_dir,
                namespace=self.strategy.kubernetes_namespace,
                timeout=self.strategy.kubernetes_timeout,
            )

            return RecordingResult(
                status="success" if result.get("success") else "failed",
                video_path=Path(result["video_path"]) if result.get("video_path") else None,
                duration_seconds=result.get("duration"),
                error=result.get("error"),
            )

        except ImportError:
            return RecordingResult(
                status="failed",
                error="screenenv_job module not available",
            )
        except Exception as e:
            logger.exception("Kubernetes recording failed")
            return RecordingResult(
                status="failed",
                error=str(e),
            )

    def _local_recording(
        self,
        script_path: Path,
        output_dir: Path,
        base_url: Optional[str],
    ) -> RecordingResult:
        """Record using local Playwright."""
        if self._local_recorder is None:
            self._local_recorder = LocalRecorder(self.local_config)

        return self._local_recorder.record_script(
            script_path=script_path,
            output_dir=output_dir,
            base_url=base_url,
        )

    def validate(
        self,
        script_path: Path,
        base_url: str,
    ) -> RecordingResult:
        """
        Validate a script without recording.

        Always uses local validation for speed.

        Args:
            script_path: Path to Playwright script
            base_url: Base URL of application

        Returns:
            RecordingResult
        """
        if self._local_recorder is None:
            self._local_recorder = LocalRecorder(self.local_config)

        return self._local_recorder.validate_script(script_path, base_url)


def record_demo(
    script_path: Path,
    output_dir: Path,
    prefer_kubernetes: bool = False,
    fallback_to_local: bool = True,
    base_url: Optional[str] = None,
) -> RecordingResult:
    """
    Record a demo with graceful fallback.

    Convenience function that handles the common case of recording
    with automatic fallback.

    Args:
        script_path: Path to Playwright script
        output_dir: Output directory
        prefer_kubernetes: Try Kubernetes first
        fallback_to_local: Fall back to local on K8s failure
        base_url: Optional base URL override

    Returns:
        RecordingResult
    """
    strategy = RecordingStrategy(
        prefer_kubernetes=prefer_kubernetes,
        fallback_to_local=fallback_to_local,
    )

    recorder = GracefulRecorder(strategy)
    return recorder.record(script_path, output_dir, base_url)


def check_kubernetes_available() -> bool:
    """
    Check if Kubernetes recording is available.

    Returns:
        True if K8s is configured and accessible
    """
    try:
        import subprocess

        result = subprocess.run(
            ["kubectl", "cluster-info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_recommended_strategy() -> RecordingStrategy:
    """
    Get recommended recording strategy based on environment.

    Returns:
        RecordingStrategy configured for current environment
    """
    k8s_available = check_kubernetes_available()

    return RecordingStrategy(
        prefer_kubernetes=k8s_available,
        fallback_to_local=True,
    )
