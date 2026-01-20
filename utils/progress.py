"""
Progress visualization utilities for demo-creator.

Provides real-time progress display with time estimates.
"""

import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class StageStatus(Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageProgress:
    """Progress information for a single stage."""

    name: str
    status: StageStatus = StageStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    estimated_duration: Optional[float] = None
    substeps: List[str] = field(default_factory=list)
    current_substep: int = 0
    error: Optional[str] = None

    @property
    def elapsed(self) -> Optional[float]:
        """Get elapsed time in seconds."""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def elapsed_str(self) -> str:
        """Get elapsed time as formatted string."""
        elapsed = self.elapsed
        if elapsed is None:
            return ""
        if elapsed < 60:
            return f"{elapsed:.0f}s"
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        return f"{minutes}m {seconds}s"


@dataclass
class PipelineProgress:
    """Progress tracking for the entire demo pipeline."""

    stages: List[StageProgress] = field(default_factory=list)
    current_stage: int = 0
    start_time: Optional[float] = None

    def add_stage(
        self,
        name: str,
        estimated_duration: Optional[float] = None,
        substeps: Optional[List[str]] = None,
    ) -> None:
        """Add a stage to the pipeline."""
        self.stages.append(StageProgress(
            name=name,
            estimated_duration=estimated_duration,
            substeps=substeps or [],
        ))

    def start_stage(self, stage_index: int) -> None:
        """Mark a stage as started."""
        if stage_index < len(self.stages):
            self.stages[stage_index].status = StageStatus.IN_PROGRESS
            self.stages[stage_index].start_time = time.time()
            self.current_stage = stage_index

    def complete_stage(self, stage_index: int) -> None:
        """Mark a stage as completed."""
        if stage_index < len(self.stages):
            self.stages[stage_index].status = StageStatus.COMPLETED
            self.stages[stage_index].end_time = time.time()

    def fail_stage(self, stage_index: int, error: str) -> None:
        """Mark a stage as failed."""
        if stage_index < len(self.stages):
            self.stages[stage_index].status = StageStatus.FAILED
            self.stages[stage_index].end_time = time.time()
            self.stages[stage_index].error = error

    def skip_stage(self, stage_index: int) -> None:
        """Mark a stage as skipped."""
        if stage_index < len(self.stages):
            self.stages[stage_index].status = StageStatus.SKIPPED

    def update_substep(self, stage_index: int, substep_index: int) -> None:
        """Update the current substep of a stage."""
        if stage_index < len(self.stages):
            self.stages[stage_index].current_substep = substep_index

    @property
    def estimated_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        remaining = 0.0
        for i, stage in enumerate(self.stages):
            if i < self.current_stage:
                continue
            if stage.status == StageStatus.IN_PROGRESS:
                # Estimate remaining based on progress
                if stage.estimated_duration:
                    elapsed = stage.elapsed or 0
                    remaining += max(0, stage.estimated_duration - elapsed)
            elif stage.status == StageStatus.PENDING:
                if stage.estimated_duration:
                    remaining += stage.estimated_duration
        return remaining if remaining > 0 else None


class ProgressDisplay:
    """
    Displays progress information to the terminal.

    Supports both simple text output and rich terminal updates.
    """

    # Status symbols
    SYMBOLS = {
        StageStatus.PENDING: "○",
        StageStatus.IN_PROGRESS: "◐",
        StageStatus.COMPLETED: "✓",
        StageStatus.FAILED: "✗",
        StageStatus.SKIPPED: "⊘",
    }

    def __init__(
        self,
        pipeline: PipelineProgress,
        use_rich: bool = True,
        output_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize progress display.

        Args:
            pipeline: Pipeline progress tracker
            use_rich: Use rich terminal output (ANSI colors)
            output_callback: Optional callback for output (default: print)
        """
        self.pipeline = pipeline
        self.use_rich = use_rich
        self.output = output_callback or print

    def render(self) -> str:
        """Render the current progress state as a string."""
        lines = ["", "Demo Creation Progress", "=" * 22, ""]

        for i, stage in enumerate(self.pipeline.stages):
            symbol = self.SYMBOLS[stage.status]
            elapsed = stage.elapsed_str

            # Format stage line
            if stage.status == StageStatus.IN_PROGRESS:
                if stage.estimated_duration:
                    est = self._format_duration(stage.estimated_duration)
                    line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} ({elapsed} / ~{est})"
                else:
                    line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} ({elapsed})"
            elif stage.status == StageStatus.COMPLETED:
                line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} ({elapsed})"
            elif stage.status == StageStatus.FAILED:
                line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} FAILED"
            elif stage.status == StageStatus.SKIPPED:
                line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} (skipped)"
            else:
                if stage.estimated_duration:
                    est = self._format_duration(stage.estimated_duration)
                    line = f"[{symbol}] Stage {i + 1}: {stage.name:<24} (~{est})"
                else:
                    line = f"[{symbol}] Stage {i + 1}: {stage.name:<24}"

            lines.append(line)

            # Show substeps for in-progress stage
            if stage.status == StageStatus.IN_PROGRESS and stage.substeps:
                for j, substep in enumerate(stage.substeps):
                    if j < stage.current_substep:
                        lines.append(f"    ├─ {substep:<20} ✓")
                    elif j == stage.current_substep:
                        lines.append(f"    ├─ {substep:<20} ◐  Processing...")
                    else:
                        lines.append(f"    └─ {substep:<20} ○")

            # Show error for failed stage
            if stage.status == StageStatus.FAILED and stage.error:
                lines.append(f"    └─ Error: {stage.error[:50]}")

        # Estimated remaining time
        remaining = self.pipeline.estimated_remaining
        if remaining:
            lines.append("")
            lines.append(f"Estimated remaining: {self._format_duration(remaining)}")

        return "\n".join(lines)

    def display(self) -> None:
        """Display current progress."""
        self.output(self.render())

    def update(self) -> None:
        """Update the display (for terminal refresh)."""
        if self.use_rich:
            # Move cursor up and clear lines
            num_lines = 4 + len(self.pipeline.stages) * 2  # Approximate
            self.output(f"\033[{num_lines}A\033[J")
        self.display()

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"


def create_demo_pipeline() -> PipelineProgress:
    """
    Create a progress tracker for the demo pipeline.

    Returns:
        PipelineProgress with all stages configured
    """
    pipeline = PipelineProgress()

    # Add stages with estimated durations
    pipeline.add_stage("Outline", estimated_duration=30)
    pipeline.add_stage("Discover Selectors", estimated_duration=60)
    pipeline.add_stage("Script", estimated_duration=120)
    pipeline.add_stage("Validate", estimated_duration=60)
    pipeline.add_stage("Record", estimated_duration=180, substeps=[
        "Scene 1", "Scene 2", "Scene 3", "Scene 4",
    ])
    pipeline.add_stage("Narration", estimated_duration=60)
    pipeline.add_stage("Preview", estimated_duration=30)
    pipeline.add_stage("Adjust", estimated_duration=60)
    pipeline.add_stage("Audio", estimated_duration=180)
    pipeline.add_stage("Avatar", estimated_duration=300)
    pipeline.add_stage("Composite", estimated_duration=120)
    pipeline.add_stage("Upload", estimated_duration=30)

    return pipeline


class ProgressContext:
    """
    Context manager for stage progress tracking.

    Usage:
        with ProgressContext(pipeline, stage_index) as progress:
            # Do work
            progress.update_substep(0)
            # More work
            progress.update_substep(1)
    """

    def __init__(
        self,
        pipeline: PipelineProgress,
        stage_index: int,
        display: Optional[ProgressDisplay] = None,
    ):
        self.pipeline = pipeline
        self.stage_index = stage_index
        self.display = display

    def __enter__(self):
        self.pipeline.start_stage(self.stage_index)
        if self.display:
            self.display.update()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.pipeline.fail_stage(self.stage_index, str(exc_val))
        else:
            self.pipeline.complete_stage(self.stage_index)

        if self.display:
            self.display.update()

        return False  # Don't suppress exceptions

    def update_substep(self, substep_index: int) -> None:
        """Update current substep."""
        self.pipeline.update_substep(self.stage_index, substep_index)
        if self.display:
            self.display.update()
