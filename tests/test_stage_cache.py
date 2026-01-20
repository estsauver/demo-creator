"""Tests for stage caching utilities."""

import json
from pathlib import Path

import pytest

from utils.stage_cache import (
    CachedStageRunner,
    StageCache,
    StageSignature,
    get_stage_inputs,
)


class TestStageSignature:
    """Tests for StageSignature dataclass."""

    def test_basic_signature(self):
        """Should represent a stage signature."""
        sig = StageSignature(
            stage_name="test",
            input_hash="abc123",
        )

        assert sig.stage_name == "test"
        assert sig.input_hash == "abc123"

    def test_signature_with_outputs(self):
        """Should track output files."""
        sig = StageSignature(
            stage_name="test",
            input_hash="abc123",
            output_files=["file1.json", "file2.mp4"],
        )

        assert len(sig.output_files) == 2

    def test_to_dict(self):
        """Should convert to dictionary."""
        sig = StageSignature(
            stage_name="test",
            input_hash="abc123",
        )

        d = sig.to_dict()

        assert d["stage_name"] == "test"
        assert d["input_hash"] == "abc123"

    def test_from_dict(self):
        """Should construct from dictionary."""
        d = {
            "stage_name": "test",
            "input_hash": "abc123",
            "output_files": ["file.json"],
            "timestamp": "2024-01-01T00:00:00",
        }

        sig = StageSignature.from_dict(d)

        assert sig.stage_name == "test"
        assert sig.input_hash == "abc123"


class TestStageCache:
    """Tests for StageCache class."""

    def test_init_creates_directory(self, tmp_path):
        """Should create cache directory."""
        cache_dir = tmp_path / "cache"
        cache = StageCache(cache_dir)

        assert cache_dir.exists()

    def test_compute_hash(self, tmp_path):
        """Should compute deterministic hash."""
        cache = StageCache(tmp_path)

        hash1 = cache.compute_hash({"key": "value"})
        hash2 = cache.compute_hash({"key": "value"})

        assert hash1 == hash2
        assert len(hash1) == 16

    def test_compute_hash_different_inputs(self, tmp_path):
        """Should produce different hashes for different inputs."""
        cache = StageCache(tmp_path)

        hash1 = cache.compute_hash({"key": "value1"})
        hash2 = cache.compute_hash({"key": "value2"})

        assert hash1 != hash2

    def test_should_skip_no_cache(self, tmp_path):
        """Should not skip when no cache exists."""
        cache = StageCache(tmp_path)

        result = cache.should_skip("test", {"key": "value"})

        assert result is False

    def test_should_skip_with_cache(self, tmp_path):
        """Should skip when cache matches."""
        cache = StageCache(tmp_path)
        inputs = {"key": "value"}

        # Record completion
        cache.record_completion("test", inputs)

        # Should skip now
        result = cache.should_skip("test", inputs)

        assert result is True

    def test_should_skip_changed_inputs(self, tmp_path):
        """Should not skip when inputs changed."""
        cache = StageCache(tmp_path)

        # Record with original inputs
        cache.record_completion("test", {"key": "value1"})

        # Should not skip with different inputs
        result = cache.should_skip("test", {"key": "value2"})

        assert result is False

    def test_should_skip_missing_output(self, tmp_path):
        """Should not skip when output files are missing."""
        cache = StageCache(tmp_path)
        inputs = {"key": "value"}
        output_file = tmp_path / "output.json"

        # Record with output file
        cache.record_completion("test", inputs, [output_file])

        # Should not skip (file doesn't exist)
        result = cache.should_skip("test", inputs, [output_file])

        assert result is False

    def test_should_skip_existing_output(self, tmp_path):
        """Should skip when output files exist."""
        cache = StageCache(tmp_path)
        inputs = {"key": "value"}
        output_file = tmp_path / "output.json"
        output_file.write_text("{}")

        # Record with output file
        cache.record_completion("test", inputs, [output_file])

        # Should skip (file exists)
        result = cache.should_skip("test", inputs, [output_file])

        assert result is True

    def test_invalidate(self, tmp_path):
        """Should invalidate stage cache."""
        cache = StageCache(tmp_path)

        cache.record_completion("test", {"key": "value"})
        assert cache.should_skip("test", {"key": "value"}) is True

        cache.invalidate("test")
        assert cache.should_skip("test", {"key": "value"}) is False

    def test_invalidate_downstream(self, tmp_path):
        """Should invalidate downstream stages."""
        cache = StageCache(tmp_path)
        stages = ["stage1", "stage2", "stage3"]

        for stage in stages:
            cache.record_completion(stage, {"key": "value"})

        cache.invalidate_downstream("stage2", stages)

        assert cache.should_skip("stage1", {"key": "value"}) is True
        assert cache.should_skip("stage2", {"key": "value"}) is False
        assert cache.should_skip("stage3", {"key": "value"}) is False

    def test_clear(self, tmp_path):
        """Should clear all cached signatures."""
        cache = StageCache(tmp_path)

        cache.record_completion("test1", {"key": "value"})
        cache.record_completion("test2", {"key": "value"})

        cache.clear()

        assert len(cache.get_cached_stages()) == 0

    def test_persistence(self, tmp_path):
        """Should persist cache across instances."""
        cache1 = StageCache(tmp_path)
        cache1.record_completion("test", {"key": "value"})

        # Create new instance
        cache2 = StageCache(tmp_path)

        assert cache2.should_skip("test", {"key": "value"}) is True


class TestCachedStageRunner:
    """Tests for CachedStageRunner class."""

    def test_run_stage_no_cache(self, tmp_path):
        """Should run stage when not cached."""
        runner = CachedStageRunner(tmp_path)
        call_count = [0]

        def stage_fn():
            call_count[0] += 1
            return {"status": "success"}

        result = runner.run_stage("test", {"key": "value"}, stage_fn)

        assert call_count[0] == 1
        assert result["status"] == "success"

    def test_run_stage_cached(self, tmp_path):
        """Should skip stage when cached."""
        runner = CachedStageRunner(tmp_path)
        call_count = [0]

        def stage_fn():
            call_count[0] += 1
            return {"status": "success"}

        # First run
        runner.run_stage("test", {"key": "value"}, stage_fn)
        assert call_count[0] == 1

        # Second run - should skip
        result = runner.run_stage("test", {"key": "value"}, stage_fn)
        assert call_count[0] == 1
        assert result["cached"] is True

    def test_run_stage_force(self, tmp_path):
        """Should run stage when forced."""
        runner = CachedStageRunner(tmp_path)
        call_count = [0]

        def stage_fn():
            call_count[0] += 1
            return {"status": "success"}

        # First run
        runner.run_stage("test", {"key": "value"}, stage_fn)

        # Force run
        runner.run_stage("test", {"key": "value"}, stage_fn, force=True)
        assert call_count[0] == 2

    def test_should_run(self, tmp_path):
        """Should check if stage needs to run."""
        runner = CachedStageRunner(tmp_path)

        assert runner.should_run("test", {"key": "value"}) is True

        runner.mark_complete("test", {"key": "value"})

        assert runner.should_run("test", {"key": "value"}) is False

    def test_reset(self, tmp_path):
        """Should reset all stage caches."""
        runner = CachedStageRunner(tmp_path)

        runner.mark_complete("test", {"key": "value"})
        runner.reset()

        assert runner.should_run("test", {"key": "value"}) is True


class TestGetStageInputs:
    """Tests for get_stage_inputs function."""

    def test_no_manifest(self, tmp_path):
        """Should return empty dict when no manifest."""
        result = get_stage_inputs(tmp_path, "test")

        assert result == {}

    def test_script_stage(self, tmp_path):
        """Should extract inputs for script stage."""
        # Create manifest and files
        manifest = {"stages": []}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        (tmp_path / "outline.md").write_text("# Outline")
        (tmp_path / "selectors.json").write_text("{}")

        result = get_stage_inputs(tmp_path, "script")

        assert "outline_hash" in result
        assert "selectors_hash" in result

    def test_audio_stage(self, tmp_path):
        """Should extract inputs for audio stage."""
        manifest = {"stages": []}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))
        (tmp_path / "narration.json").write_text('{"segments": []}')

        result = get_stage_inputs(tmp_path, "audio")

        assert "narration_hash" in result
