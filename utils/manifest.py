"""
Manifest utilities for demo-creator pipeline.

The manifest.json file tracks pipeline state and stage outputs, enabling
recovery from context exhaustion and systematic error handling.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class Manifest:
    """
    Manages the demo pipeline manifest file (.demo/{demo-id}/manifest.json).

    The manifest tracks:
    - Pipeline metadata (demo_id, linear_issue, git_sha, etc.)
    - Stage status (current_stage, completed_stages, failed_stages)
    - Stage outputs (file paths, metadata)
    - Error information for failed stages
    - Brand voice cache
    """

    def __init__(self, demo_id: str, base_path: str = ".demo"):
        self.demo_id = demo_id
        self.base_path = Path(base_path)
        self.demo_dir = self.base_path / demo_id
        self.manifest_path = self.demo_dir / "manifest.json"
        self._data: Optional[Dict[str, Any]] = None

    def initialize(
        self,
        linear_issue: Optional[str] = None,
        git_sha: Optional[str] = None,
        git_branch: Optional[str] = None,
    ) -> None:
        """
        Initialize a new manifest file.

        Args:
            linear_issue: Linear issue ID (e.g., "ISSUE-123")
            git_sha: Git commit SHA
            git_branch: Git branch name
        """
        # Create demo directory
        self.demo_dir.mkdir(parents=True, exist_ok=True)

        # Initialize manifest data
        self._data = {
            "demo_id": self.demo_id,
            "linear_issue": linear_issue,
            "git_sha": git_sha,
            "git_branch": git_branch,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "current_stage": 0,
            "completed_stages": [],
            "failed_stages": [],
            "stage_outputs": {},
            "errors": [],
            "brand_voice_cache": {
                "path": ".demo/templates/narration-voice.md",
                "last_refreshed": None,
            },
        }

        self._save()

    def load(self) -> Dict[str, Any]:
        """
        Load the manifest from disk.

        Returns:
            The manifest data dictionary

        Raises:
            FileNotFoundError: If manifest doesn't exist
        """
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        with open(self.manifest_path, "r") as f:
            self._data = json.load(f)

        return self._data

    def _save(self) -> None:
        """Save the manifest to disk."""
        if self._data is None:
            raise RuntimeError("Manifest not initialized. Call initialize() or load() first.")

        with open(self.manifest_path, "w") as f:
            json.dump(self._data, f, indent=2)

    @property
    def data(self) -> Dict[str, Any]:
        """Get the manifest data, loading if necessary."""
        if self._data is None:
            self.load()
        return self._data

    def start_stage(self, stage: int) -> None:
        """
        Mark a stage as started (update current_stage).

        Args:
            stage: Stage number (1-9)
        """
        data = self.data
        data["current_stage"] = stage
        self._save()

    def complete_stage(self, stage: int, outputs: Dict[str, Any]) -> None:
        """
        Mark a stage as completed and record its outputs.

        Args:
            stage: Stage number (1-9)
            outputs: Stage outputs to record
        """
        data = self.data

        if stage not in data["completed_stages"]:
            data["completed_stages"].append(stage)

        # Remove from failed if it was there
        if stage in data["failed_stages"]:
            data["failed_stages"].remove(stage)

        # Record outputs
        data["stage_outputs"][str(stage)] = outputs

        self._save()

    def fail_stage(
        self,
        stage: int,
        error_type: str,
        error_message: str,
        step: Optional[str] = None,
        suggested_fix: Optional[str] = None,
        partial_results: Optional[Dict[str, Any]] = None,
        screenshot_path: Optional[str] = None,
        dom_snapshot_path: Optional[str] = None,
    ) -> None:
        """
        Mark a stage as failed and record error details.

        Args:
            stage: Stage number (1-9)
            error_type: Type of error (e.g., "ElementNotFound", "TimeoutError")
            error_message: Detailed error message
            step: Optional step description where error occurred
            suggested_fix: Optional suggestion for fixing the error
            partial_results: Optional partial results before failure
            screenshot_path: Optional path to error screenshot
            dom_snapshot_path: Optional path to DOM snapshot
        """
        data = self.data

        if stage not in data["failed_stages"]:
            data["failed_stages"].append(stage)

        error_record = {
            "stage": stage,
            "step": step,
            "error_type": error_type,
            "error_message": error_message,
            "suggested_fix": suggested_fix,
            "partial_results": partial_results,
            "screenshot_path": screenshot_path,
            "dom_snapshot_path": dom_snapshot_path,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        data["errors"].append(error_record)
        self._save()

    def get_stage_output(self, stage: int) -> Optional[Dict[str, Any]]:
        """
        Get the outputs from a specific stage.

        Args:
            stage: Stage number (1-9)

        Returns:
            Stage outputs or None if not found
        """
        data = self.data
        return data["stage_outputs"].get(str(stage))

    def is_stage_completed(self, stage: int) -> bool:
        """
        Check if a stage has been completed.

        Args:
            stage: Stage number (1-9)

        Returns:
            True if stage is completed
        """
        data = self.data
        return stage in data["completed_stages"]

    def update_brand_voice_cache(self, refresh_time: Optional[str] = None) -> None:
        """
        Update the brand voice cache timestamp.

        Args:
            refresh_time: ISO timestamp (defaults to now)
        """
        data = self.data
        if refresh_time is None:
            refresh_time = datetime.utcnow().isoformat() + "Z"

        data["brand_voice_cache"]["last_refreshed"] = refresh_time
        self._save()

    def get_file_path(self, filename: str) -> Path:
        """
        Get the full path for a file in the demo directory.

        Args:
            filename: Relative filename (e.g., "script.yaml")

        Returns:
            Full path to the file
        """
        return self.demo_dir / filename

    def ensure_subdirectory(self, subdir: str) -> Path:
        """
        Ensure a subdirectory exists within the demo directory.

        Args:
            subdir: Subdirectory name (e.g., "validation_screenshots")

        Returns:
            Path to the subdirectory
        """
        subdir_path = self.demo_dir / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)
        return subdir_path


def get_or_create_manifest(
    demo_id: str,
    linear_issue: Optional[str] = None,
    git_sha: Optional[str] = None,
    git_branch: Optional[str] = None,
) -> Manifest:
    """
    Get an existing manifest or create a new one.

    Args:
        demo_id: Demo identifier
        linear_issue: Linear issue ID (for new manifests)
        git_sha: Git SHA (for new manifests)
        git_branch: Git branch (for new manifests)

    Returns:
        Manifest instance
    """
    manifest = Manifest(demo_id)

    if manifest.manifest_path.exists():
        manifest.load()
    else:
        manifest.initialize(
            linear_issue=linear_issue,
            git_sha=git_sha,
            git_branch=git_branch,
        )

    return manifest
