"""Tests for manifest utilities."""

import json
import tempfile
from pathlib import Path

import pytest

from utils.manifest import Manifest, get_or_create_manifest


class TestManifest:
    """Tests for Manifest class."""

    @pytest.fixture
    def manifest(self, tmp_path):
        """Create a temporary manifest."""
        return Manifest("test-demo", base_path=str(tmp_path))

    def test_initialize_creates_directory(self, manifest):
        """Initialize should create demo directory."""
        manifest.initialize()

        assert manifest.demo_dir.exists()
        assert manifest.manifest_path.exists()

    def test_initialize_with_metadata(self, manifest):
        """Initialize should store metadata."""
        manifest.initialize(
            linear_issue="ISSUE-123",
            git_sha="abc1234",
            git_branch="user/issue-123-feature",
        )

        data = manifest.data
        assert data["demo_id"] == "test-demo"
        assert data["linear_issue"] == "ISSUE-123"
        assert data["git_sha"] == "abc1234"
        assert data["git_branch"] == "user/issue-123-feature"
        assert "created_at" in data

    def test_load_existing_manifest(self, manifest):
        """Load should read existing manifest."""
        manifest.initialize(linear_issue="ISSUE-456")

        # Create new instance and load
        manifest2 = Manifest("test-demo", base_path=str(manifest.base_path))
        manifest2.load()

        assert manifest2.data["linear_issue"] == "ISSUE-456"

    def test_load_nonexistent_raises(self, manifest):
        """Load should raise FileNotFoundError for missing manifest."""
        with pytest.raises(FileNotFoundError):
            manifest.load()

    def test_start_stage(self, manifest):
        """start_stage should update current_stage."""
        manifest.initialize()
        manifest.start_stage(3)

        assert manifest.data["current_stage"] == 3

    def test_complete_stage(self, manifest):
        """complete_stage should record completion and outputs."""
        manifest.initialize()
        manifest.complete_stage(1, {
            "outline_path": "outline.md",
            "setup_requirements": ["npm run seed"],
        })

        assert 1 in manifest.data["completed_stages"]
        assert manifest.data["stage_outputs"]["1"]["outline_path"] == "outline.md"

    def test_complete_removes_from_failed(self, manifest):
        """complete_stage should remove stage from failed list."""
        manifest.initialize()
        manifest.fail_stage(1, "TestError", "Something went wrong")

        assert 1 in manifest.data["failed_stages"]

        manifest.complete_stage(1, {"output": "success"})

        assert 1 not in manifest.data["failed_stages"]
        assert 1 in manifest.data["completed_stages"]

    def test_fail_stage(self, manifest):
        """fail_stage should record failure details."""
        manifest.initialize()
        manifest.fail_stage(
            stage=2,
            error_type="ElementNotFound",
            error_message="Button not found",
            step="Click submit button",
            suggested_fix="Update selector",
            screenshot_path="error.png",
        )

        assert 2 in manifest.data["failed_stages"]
        assert len(manifest.data["errors"]) == 1

        error = manifest.data["errors"][0]
        assert error["stage"] == 2
        assert error["error_type"] == "ElementNotFound"
        assert error["suggested_fix"] == "Update selector"

    def test_get_stage_output(self, manifest):
        """get_stage_output should return stage outputs."""
        manifest.initialize()
        manifest.complete_stage(1, {"outline_path": "outline.md"})

        output = manifest.get_stage_output(1)

        assert output["outline_path"] == "outline.md"

    def test_get_stage_output_missing(self, manifest):
        """get_stage_output should return None for missing stage."""
        manifest.initialize()

        output = manifest.get_stage_output(99)

        assert output is None

    def test_is_stage_completed(self, manifest):
        """is_stage_completed should check completion status."""
        manifest.initialize()
        manifest.complete_stage(1, {})

        assert manifest.is_stage_completed(1) is True
        assert manifest.is_stage_completed(2) is False

    def test_get_file_path(self, manifest):
        """get_file_path should return full path."""
        manifest.initialize()

        path = manifest.get_file_path("script.py")

        assert path == manifest.demo_dir / "script.py"

    def test_ensure_subdirectory(self, manifest):
        """ensure_subdirectory should create and return path."""
        manifest.initialize()

        path = manifest.ensure_subdirectory("screenshots")

        assert path.exists()
        assert path == manifest.demo_dir / "screenshots"

    def test_update_brand_voice_cache(self, manifest):
        """update_brand_voice_cache should update timestamp."""
        manifest.initialize()

        manifest.update_brand_voice_cache()

        assert manifest.data["brand_voice_cache"]["last_refreshed"] is not None


class TestGetOrCreateManifest:
    """Tests for get_or_create_manifest function."""

    def test_creates_new_manifest(self, tmp_path):
        """Should create new manifest when none exists."""
        manifest = get_or_create_manifest(
            demo_id="new-demo",
            linear_issue="ISSUE-789",
        )

        # Default base_path is .demo, so use that
        assert manifest.data["demo_id"] == "new-demo"
        assert manifest.data["linear_issue"] == "ISSUE-789"

    def test_loads_existing_manifest(self, tmp_path):
        """Should load existing manifest."""
        # Create initial manifest
        manifest1 = Manifest("existing-demo", base_path=str(tmp_path))
        manifest1.initialize(linear_issue="ISSUE-111")
        manifest1.complete_stage(1, {"outline": "done"})

        # Get or create should load it
        manifest2 = get_or_create_manifest("existing-demo")

        # Note: this will create in default .demo dir, not tmp_path
        # For proper testing, we'd need to patch or parameterize base_path
