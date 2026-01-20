"""Tests for progress visualization utilities."""

import time

import pytest

from utils.progress import (
    PipelineProgress,
    ProgressContext,
    ProgressDisplay,
    StageProgress,
    StageStatus,
    create_demo_pipeline,
)


class TestStageProgress:
    """Tests for StageProgress dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        stage = StageProgress(name="test")

        assert stage.name == "test"
        assert stage.status == StageStatus.PENDING
        assert stage.start_time is None
        assert stage.elapsed is None

    def test_elapsed_time(self):
        """Should calculate elapsed time."""
        stage = StageProgress(name="test")
        stage.start_time = time.time() - 10  # Started 10 seconds ago

        assert stage.elapsed is not None
        assert 9 < stage.elapsed < 11

    def test_elapsed_str_formatting(self):
        """Should format elapsed time as string."""
        stage = StageProgress(name="test")

        # Not started
        assert stage.elapsed_str == ""

        # 30 seconds
        stage.start_time = time.time() - 30
        assert "30s" in stage.elapsed_str or "29s" in stage.elapsed_str

        # 2 minutes
        stage.start_time = time.time() - 125
        assert "2m" in stage.elapsed_str


class TestPipelineProgress:
    """Tests for PipelineProgress class."""

    def test_add_stages(self):
        """Should add stages to pipeline."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1", estimated_duration=60)
        pipeline.add_stage("Stage 2", estimated_duration=120)

        assert len(pipeline.stages) == 2
        assert pipeline.stages[0].name == "Stage 1"
        assert pipeline.stages[0].estimated_duration == 60

    def test_start_stage(self):
        """Should mark stage as started."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        pipeline.start_stage(0)

        assert pipeline.stages[0].status == StageStatus.IN_PROGRESS
        assert pipeline.stages[0].start_time is not None
        assert pipeline.current_stage == 0

    def test_complete_stage(self):
        """Should mark stage as completed."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")
        pipeline.start_stage(0)

        pipeline.complete_stage(0)

        assert pipeline.stages[0].status == StageStatus.COMPLETED
        assert pipeline.stages[0].end_time is not None

    def test_fail_stage(self):
        """Should mark stage as failed with error."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")
        pipeline.start_stage(0)

        pipeline.fail_stage(0, "Something went wrong")

        assert pipeline.stages[0].status == StageStatus.FAILED
        assert pipeline.stages[0].error == "Something went wrong"

    def test_skip_stage(self):
        """Should mark stage as skipped."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        pipeline.skip_stage(0)

        assert pipeline.stages[0].status == StageStatus.SKIPPED

    def test_estimated_remaining(self):
        """Should estimate remaining time."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1", estimated_duration=60)
        pipeline.add_stage("Stage 2", estimated_duration=120)

        # All pending
        remaining = pipeline.estimated_remaining
        assert remaining is not None
        assert remaining > 0

        # First stage in progress
        pipeline.start_stage(0)
        remaining = pipeline.estimated_remaining
        assert remaining is not None


class TestProgressDisplay:
    """Tests for ProgressDisplay class."""

    def test_render_pending(self):
        """Should render pending stages."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        display = ProgressDisplay(pipeline, use_rich=False)
        output = display.render()

        assert "Stage 1" in output
        assert "○" in output  # Pending symbol

    def test_render_in_progress(self):
        """Should render in-progress stages."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")
        pipeline.start_stage(0)

        display = ProgressDisplay(pipeline, use_rich=False)
        output = display.render()

        assert "Stage 1" in output
        assert "◐" in output  # In-progress symbol

    def test_render_completed(self):
        """Should render completed stages."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")
        pipeline.start_stage(0)
        pipeline.complete_stage(0)

        display = ProgressDisplay(pipeline, use_rich=False)
        output = display.render()

        assert "Stage 1" in output
        assert "✓" in output  # Completed symbol

    def test_render_failed(self):
        """Should render failed stages with error."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")
        pipeline.start_stage(0)
        pipeline.fail_stage(0, "Error message")

        display = ProgressDisplay(pipeline, use_rich=False)
        output = display.render()

        assert "✗" in output  # Failed symbol
        assert "FAILED" in output

    def test_output_callback(self):
        """Should use custom output callback."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        outputs = []
        display = ProgressDisplay(
            pipeline,
            use_rich=False,
            output_callback=outputs.append,
        )
        display.display()

        assert len(outputs) == 1
        assert "Stage 1" in outputs[0]


class TestProgressContext:
    """Tests for ProgressContext manager."""

    def test_context_success(self):
        """Should mark stage complete on success."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        with ProgressContext(pipeline, 0):
            pass  # Simulate work

        assert pipeline.stages[0].status == StageStatus.COMPLETED

    def test_context_failure(self):
        """Should mark stage failed on exception."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1")

        with pytest.raises(ValueError):
            with ProgressContext(pipeline, 0):
                raise ValueError("Test error")

        assert pipeline.stages[0].status == StageStatus.FAILED

    def test_context_update_substep(self):
        """Should allow updating substeps."""
        pipeline = PipelineProgress()
        pipeline.add_stage("Stage 1", substeps=["Step A", "Step B"])

        with ProgressContext(pipeline, 0) as ctx:
            ctx.update_substep(0)
            assert pipeline.stages[0].current_substep == 0
            ctx.update_substep(1)
            assert pipeline.stages[0].current_substep == 1


class TestCreateDemoPipeline:
    """Tests for create_demo_pipeline function."""

    def test_creates_all_stages(self):
        """Should create pipeline with all demo stages."""
        pipeline = create_demo_pipeline()

        assert len(pipeline.stages) > 0
        # Check for key stages
        stage_names = [s.name for s in pipeline.stages]
        assert "Outline" in stage_names
        assert "Script" in stage_names
        assert "Record" in stage_names
        assert "Audio" in stage_names
        assert "Upload" in stage_names

    def test_stages_have_estimates(self):
        """Should have duration estimates."""
        pipeline = create_demo_pipeline()

        for stage in pipeline.stages:
            assert stage.estimated_duration is not None
            assert stage.estimated_duration > 0
