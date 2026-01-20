"""
Stage caching for skipping unchanged stages.

Tracks stage inputs and outputs to skip re-running stages
when their inputs haven't changed.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class StageSignature:
    """Signature of a stage's inputs for change detection."""

    stage_name: str
    input_hash: str
    output_files: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage_name": self.stage_name,
            "input_hash": self.input_hash,
            "output_files": self.output_files,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StageSignature":
        return cls(
            stage_name=data["stage_name"],
            input_hash=data["input_hash"],
            output_files=data.get("output_files", []),
            timestamp=data.get("timestamp", ""),
        )


class StageCache:
    """
    Caches stage outputs to skip unchanged stages.

    Tracks the inputs to each stage and compares them
    to determine if a stage needs to be re-run.
    """

    def __init__(self, cache_dir: Path):
        """
        Initialize stage cache.

        Args:
            cache_dir: Directory for cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "stage_signatures.json"
        self._signatures: Dict[str, StageSignature] = {}
        self._load()

    def _load(self) -> None:
        """Load signatures from cache file."""
        if self.cache_file.exists():
            try:
                data = json.loads(self.cache_file.read_text())
                self._signatures = {
                    name: StageSignature.from_dict(sig)
                    for name, sig in data.get("signatures", {}).items()
                }
            except Exception as e:
                logger.warning(f"Failed to load stage cache: {e}")
                self._signatures = {}

    def _save(self) -> None:
        """Save signatures to cache file."""
        try:
            data = {
                "signatures": {
                    name: sig.to_dict()
                    for name, sig in self._signatures.items()
                },
            }
            self.cache_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save stage cache: {e}")

    def compute_hash(self, inputs: Dict[str, Any]) -> str:
        """
        Compute a hash of stage inputs.

        Args:
            inputs: Dict of input values

        Returns:
            Hash string
        """
        # Serialize inputs deterministically
        serialized = json.dumps(inputs, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def should_skip(
        self,
        stage_name: str,
        inputs: Dict[str, Any],
        output_files: Optional[List[Path]] = None,
    ) -> bool:
        """
        Check if a stage can be skipped.

        Args:
            stage_name: Name of the stage
            inputs: Current input values
            output_files: Expected output files

        Returns:
            True if stage can be skipped
        """
        input_hash = self.compute_hash(inputs)

        # Check if we have a cached signature
        if stage_name not in self._signatures:
            logger.debug(f"Stage {stage_name}: No cached signature, must run")
            return False

        cached = self._signatures[stage_name]

        # Check if inputs changed
        if cached.input_hash != input_hash:
            logger.debug(f"Stage {stage_name}: Input hash changed, must run")
            return False

        # Check if output files exist
        if output_files:
            for output_file in output_files:
                if not Path(output_file).exists():
                    logger.debug(f"Stage {stage_name}: Output file missing: {output_file}")
                    return False

        logger.info(f"Stage {stage_name}: Inputs unchanged, skipping")
        return True

    def record_completion(
        self,
        stage_name: str,
        inputs: Dict[str, Any],
        output_files: Optional[List[Path]] = None,
    ) -> None:
        """
        Record a stage completion.

        Args:
            stage_name: Name of the stage
            inputs: Input values used
            output_files: Output files created
        """
        input_hash = self.compute_hash(inputs)
        output_list = [str(f) for f in (output_files or [])]

        self._signatures[stage_name] = StageSignature(
            stage_name=stage_name,
            input_hash=input_hash,
            output_files=output_list,
        )
        self._save()

    def invalidate(self, stage_name: str) -> None:
        """
        Invalidate a stage's cache.

        Args:
            stage_name: Name of the stage
        """
        if stage_name in self._signatures:
            del self._signatures[stage_name]
            self._save()

    def invalidate_downstream(
        self,
        stage_name: str,
        stage_order: List[str],
    ) -> None:
        """
        Invalidate a stage and all downstream stages.

        Args:
            stage_name: Name of the stage to invalidate
            stage_order: Ordered list of all stage names
        """
        if stage_name not in stage_order:
            return

        start_idx = stage_order.index(stage_name)
        for stage in stage_order[start_idx:]:
            self.invalidate(stage)

    def clear(self) -> None:
        """Clear all cached signatures."""
        self._signatures = {}
        self._save()

    def get_cached_stages(self) -> Set[str]:
        """Get set of cached stage names."""
        return set(self._signatures.keys())


class CachedStageRunner:
    """
    Runs stages with caching support.

    Automatically skips stages when inputs haven't changed.
    """

    # Standard stage order for demo pipeline
    STAGE_ORDER = [
        "outline",
        "discover_selectors",
        "script",
        "validate",
        "record",
        "narration",
        "preview",
        "adjust",
        "audio",
        "avatar",
        "composite",
        "upload",
    ]

    def __init__(self, demo_dir: Path):
        """
        Initialize cached stage runner.

        Args:
            demo_dir: Demo output directory
        """
        self.demo_dir = Path(demo_dir)
        self.cache = StageCache(self.demo_dir / ".cache")

    def run_stage(
        self,
        stage_name: str,
        inputs: Dict[str, Any],
        runner: callable,
        output_files: Optional[List[Path]] = None,
        force: bool = False,
    ) -> Any:
        """
        Run a stage with caching.

        Args:
            stage_name: Name of the stage
            inputs: Input values for the stage
            runner: Callable to run the stage
            output_files: Expected output files
            force: Force re-run even if cached

        Returns:
            Result of the runner
        """
        # Check cache
        if not force and self.cache.should_skip(stage_name, inputs, output_files):
            logger.info(f"Skipping {stage_name} (cached)")
            return {"status": "skipped", "cached": True}

        # Run the stage
        try:
            result = runner()

            # Record completion
            self.cache.record_completion(stage_name, inputs, output_files)

            return result

        except Exception as e:
            # Invalidate downstream stages on failure
            self.cache.invalidate_downstream(stage_name, self.STAGE_ORDER)
            raise

    def should_run(
        self,
        stage_name: str,
        inputs: Dict[str, Any],
        output_files: Optional[List[Path]] = None,
    ) -> bool:
        """
        Check if a stage needs to run.

        Args:
            stage_name: Name of the stage
            inputs: Input values
            output_files: Expected output files

        Returns:
            True if stage should run
        """
        return not self.cache.should_skip(stage_name, inputs, output_files)

    def mark_complete(
        self,
        stage_name: str,
        inputs: Dict[str, Any],
        output_files: Optional[List[Path]] = None,
    ) -> None:
        """
        Mark a stage as complete.

        Args:
            stage_name: Name of the stage
            inputs: Input values used
            output_files: Output files created
        """
        self.cache.record_completion(stage_name, inputs, output_files)

    def reset(self) -> None:
        """Reset all stage caches."""
        self.cache.clear()


def get_stage_inputs(demo_dir: Path, stage_name: str) -> Dict[str, Any]:
    """
    Get standard inputs for a stage from manifest.

    Args:
        demo_dir: Demo directory
        stage_name: Stage name

    Returns:
        Dict of input values for the stage
    """
    demo_dir = Path(demo_dir)
    manifest_path = demo_dir / "manifest.json"

    if not manifest_path.exists():
        return {}

    manifest = json.loads(manifest_path.read_text())
    inputs = {}

    # Stage-specific input extraction
    if stage_name == "script":
        # Script depends on outline
        outline_path = demo_dir / "outline.md"
        if outline_path.exists():
            inputs["outline_hash"] = hashlib.sha256(
                outline_path.read_bytes()
            ).hexdigest()[:16]

        selectors_path = demo_dir / "selectors.json"
        if selectors_path.exists():
            inputs["selectors_hash"] = hashlib.sha256(
                selectors_path.read_bytes()
            ).hexdigest()[:16]

    elif stage_name == "audio":
        # Audio depends on narration
        narration_path = demo_dir / "narration.json"
        if narration_path.exists():
            inputs["narration_hash"] = hashlib.sha256(
                narration_path.read_bytes()
            ).hexdigest()[:16]

    elif stage_name == "composite":
        # Composite depends on video and audio
        for f in ["demo_recording.webm", "demo_recording.mp4"]:
            video_path = demo_dir / f
            if video_path.exists():
                inputs["video_hash"] = hashlib.sha256(
                    video_path.read_bytes()
                ).hexdigest()[:16]
                break

        audio_dir = demo_dir / "audio"
        if audio_dir.exists():
            audio_files = sorted(audio_dir.glob("*.mp3"))
            inputs["audio_count"] = len(audio_files)

    return inputs
