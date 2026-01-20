"""
Context monitoring utilities for demo-creator.

Tracks context usage and warns when approaching limits.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ContextUsage:
    """Tracks context usage for a stage."""

    stage_name: str
    input_tokens: int = 0
    output_tokens: int = 0
    files_read: List[str] = field(default_factory=list)
    files_written: List[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class ContextMonitor:
    """
    Monitors context usage across the demo pipeline.

    Helps prevent context exhaustion by tracking usage
    and warning when approaching limits.
    """

    # Approximate context limits (tokens)
    MAX_CONTEXT = 200_000
    WARNING_THRESHOLD = 0.7  # Warn at 70% usage
    CRITICAL_THRESHOLD = 0.9  # Critical at 90% usage

    # Approximate token counts for common operations
    ESTIMATED_TOKENS = {
        "screenshot_base64": 500_000,  # ~500KB image
        "screenshot_path": 100,  # Just the path reference
        "dom_dump": 50_000,  # Full DOM
        "selector_map": 2_000,  # Compact selectors
        "error_traceback": 5_000,  # Full traceback
        "error_summary": 500,  # Structured summary
        "script_file": 10_000,  # Playwright script
        "narration_json": 2_000,  # Narration segments
        "manifest_json": 1_000,  # Manifest state
    }

    def __init__(self, max_context: Optional[int] = None):
        """
        Initialize context monitor.

        Args:
            max_context: Override max context size
        """
        self.max_context = max_context or self.MAX_CONTEXT
        self.stages: Dict[str, ContextUsage] = {}
        self.total_input: int = 0
        self.total_output: int = 0

    def start_stage(self, stage_name: str) -> None:
        """Start tracking a new stage."""
        self.stages[stage_name] = ContextUsage(stage_name=stage_name)

    def add_input(
        self,
        stage_name: str,
        tokens: int,
        description: Optional[str] = None,
    ) -> bool:
        """
        Add input tokens for a stage.

        Args:
            stage_name: Name of the stage
            tokens: Number of tokens
            description: Optional description

        Returns:
            True if within limits, False if approaching limit
        """
        if stage_name not in self.stages:
            self.start_stage(stage_name)

        self.stages[stage_name].input_tokens += tokens
        self.total_input += tokens

        return self.check_budget(stage_name)

    def add_output(
        self,
        stage_name: str,
        tokens: int,
        description: Optional[str] = None,
    ) -> bool:
        """
        Add output tokens for a stage.

        Args:
            stage_name: Name of the stage
            tokens: Number of tokens
            description: Optional description

        Returns:
            True if within limits, False if approaching limit
        """
        if stage_name not in self.stages:
            self.start_stage(stage_name)

        self.stages[stage_name].output_tokens += tokens
        self.total_output += tokens

        return self.check_budget(stage_name)

    def add_file_read(
        self,
        stage_name: str,
        file_path: str,
        estimated_tokens: Optional[int] = None,
    ) -> bool:
        """
        Track a file read operation.

        Args:
            stage_name: Name of the stage
            file_path: Path to file read
            estimated_tokens: Estimated token count

        Returns:
            True if within limits
        """
        if stage_name not in self.stages:
            self.start_stage(stage_name)

        self.stages[stage_name].files_read.append(file_path)

        if estimated_tokens:
            return self.add_input(stage_name, estimated_tokens, f"Read: {file_path}")

        return self.check_budget(stage_name)

    def add_file_write(
        self,
        stage_name: str,
        file_path: str,
        estimated_tokens: Optional[int] = None,
    ) -> bool:
        """
        Track a file write operation.

        Args:
            stage_name: Name of the stage
            file_path: Path to file written
            estimated_tokens: Estimated token count

        Returns:
            True if within limits
        """
        if stage_name not in self.stages:
            self.start_stage(stage_name)

        self.stages[stage_name].files_written.append(file_path)

        if estimated_tokens:
            return self.add_output(stage_name, estimated_tokens, f"Write: {file_path}")

        return self.check_budget(stage_name)

    def check_budget(self, stage_name: str) -> bool:
        """
        Check if we're within context budget.

        Args:
            stage_name: Current stage name

        Returns:
            True if within acceptable limits
        """
        usage = self.total_input + self.total_output
        ratio = usage / self.max_context

        if ratio > self.CRITICAL_THRESHOLD:
            logger.error(
                f"{stage_name}: Context at {ratio:.0%} - CRITICAL! "
                f"Consider resuming in new context."
            )
            return False
        elif ratio > self.WARNING_THRESHOLD:
            logger.warning(
                f"{stage_name}: Context at {ratio:.0%} - approaching limit"
            )
            return True

        return True

    def estimate_operation(self, operation: str) -> int:
        """
        Estimate tokens for a common operation.

        Args:
            operation: Operation name from ESTIMATED_TOKENS

        Returns:
            Estimated token count
        """
        return self.ESTIMATED_TOKENS.get(operation, 1000)

    def can_fit(self, estimated_tokens: int) -> bool:
        """
        Check if an operation will fit in remaining context.

        Args:
            estimated_tokens: Estimated tokens for operation

        Returns:
            True if operation will fit
        """
        current = self.total_input + self.total_output
        projected = current + estimated_tokens
        return projected < self.max_context * self.CRITICAL_THRESHOLD

    def get_remaining(self) -> int:
        """Get estimated remaining tokens."""
        current = self.total_input + self.total_output
        return max(0, self.max_context - current)

    def get_usage_report(self) -> Dict[str, Any]:
        """
        Get a usage report for all stages.

        Returns:
            Dict with usage statistics
        """
        total = self.total_input + self.total_output
        return {
            "total_tokens": total,
            "max_context": self.max_context,
            "usage_percent": (total / self.max_context) * 100,
            "remaining_tokens": self.get_remaining(),
            "stages": {
                name: {
                    "input_tokens": stage.input_tokens,
                    "output_tokens": stage.output_tokens,
                    "total_tokens": stage.total_tokens,
                    "files_read": len(stage.files_read),
                    "files_written": len(stage.files_written),
                }
                for name, stage in self.stages.items()
            },
        }

    def get_recommendations(self) -> List[str]:
        """
        Get recommendations for reducing context usage.

        Returns:
            List of recommendation strings
        """
        recommendations = []
        total = self.total_input + self.total_output
        ratio = total / self.max_context

        if ratio > self.WARNING_THRESHOLD:
            recommendations.append(
                "Context usage is high. Consider using file paths instead of inline content."
            )

        # Check for large stages
        for name, stage in self.stages.items():
            if stage.total_tokens > 50000:
                recommendations.append(
                    f"Stage '{name}' used {stage.total_tokens:,} tokens. "
                    f"Consider splitting into smaller substages."
                )

        # Check for many file reads
        total_reads = sum(len(s.files_read) for s in self.stages.values())
        if total_reads > 20:
            recommendations.append(
                f"Read {total_reads} files. Consider using more targeted searches."
            )

        return recommendations


# Global monitor instance
_global_monitor: Optional[ContextMonitor] = None


def get_monitor() -> ContextMonitor:
    """Get the global context monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = ContextMonitor()
    return _global_monitor


def reset_monitor() -> None:
    """Reset the global context monitor."""
    global _global_monitor
    _global_monitor = None


def track_context(stage_name: str, operation: str, tokens: Optional[int] = None) -> bool:
    """
    Convenience function to track context usage.

    Args:
        stage_name: Current stage
        operation: Operation type
        tokens: Optional token count (estimated if not provided)

    Returns:
        True if within limits
    """
    monitor = get_monitor()

    if tokens is None:
        tokens = monitor.estimate_operation(operation)

    return monitor.add_input(stage_name, tokens, operation)
