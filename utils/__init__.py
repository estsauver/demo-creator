"""Demo Creator utility modules."""

from .cache import DemoCache, GlobalCache, get_cache, get_global_cache
from .manifest import Manifest, get_or_create_manifest
from .retry import RetryContext, RetryError, retry, retry_async

# Re-export for convenience
__all__ = [
    # Cache
    "DemoCache",
    "GlobalCache",
    "get_cache",
    "get_global_cache",
    # Manifest
    "Manifest",
    "get_or_create_manifest",
    # Retry
    "RetryContext",
    "RetryError",
    "retry",
    "retry_async",
]

# Lazy imports for heavier modules
def __getattr__(name):
    """Lazy import for heavier modules."""
    if name == "VisualValidator":
        from .visual_validation import VisualValidator
        return VisualValidator
    elif name == "ParallelAudioGenerator":
        from .parallel_audio import ParallelAudioGenerator
        return ParallelAudioGenerator
    elif name == "HybridCompositor":
        from .hybrid_compositor import HybridCompositor
        return HybridCompositor
    elif name == "ProgressDisplay":
        from .progress import ProgressDisplay
        return ProgressDisplay
    elif name == "ContextMonitor":
        from .context_monitor import ContextMonitor
        return ContextMonitor
    elif name == "ErrorHandler":
        from .errors import ErrorHandler
        return ErrorHandler
    elif name == "StageCache":
        from .stage_cache import StageCache
        return StageCache
    elif name == "DemoPublisher":
        from .integrations import DemoPublisher
        return DemoPublisher
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
