"""
Caching utilities for demo-creator.

Provides caching for expensive operations like:
- Selector discovery
- Audio generation
- Page screenshots
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


class DemoCache:
    """
    Caching layer for demo-creator operations.

    Caches are stored in .demo/{demo_id}/.cache/
    """

    def __init__(self, demo_id: str, base_path: str = ".demo"):
        """
        Initialize cache for a specific demo.

        Args:
            demo_id: Demo identifier
            base_path: Base path for demo files
        """
        self.demo_id = demo_id
        self.base_path = Path(base_path)
        self.cache_dir = self.base_path / demo_id / ".cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache metadata file
        self._metadata_path = self.cache_dir / "cache_metadata.json"
        self._metadata: Optional[Dict[str, Any]] = None

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata from disk."""
        if self._metadata is None:
            if self._metadata_path.exists():
                with open(self._metadata_path) as f:
                    self._metadata = json.load(f)
            else:
                self._metadata = {"entries": {}, "created_at": time.time()}
        return self._metadata

    def _save_metadata(self) -> None:
        """Save cache metadata to disk."""
        if self._metadata:
            with open(self._metadata_path, "w") as f:
                json.dump(self._metadata, f, indent=2)

    def _hash_key(self, key: str) -> str:
        """Generate a hash for a cache key."""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _hash_content(self, content: Union[str, bytes]) -> str:
        """Generate a content hash."""
        if isinstance(content, str):
            content = content.encode()
        return hashlib.sha256(content).hexdigest()[:16]

    # =========================================================================
    # Selector Caching
    # =========================================================================

    def get_selectors(self, page_url: str, page_html_hash: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Get cached selectors for a page.

        Args:
            page_url: URL of the page
            page_html_hash: Optional hash of the page HTML to verify freshness

        Returns:
            Dict mapping semantic names to selectors, or None if not cached
        """
        key = f"selectors:{page_url}"
        cache_file = self.cache_dir / f"selectors_{self._hash_key(key)}.json"

        if not cache_file.exists():
            return None

        with open(cache_file) as f:
            cached = json.load(f)

        # Verify HTML hash if provided
        if page_html_hash and cached.get("html_hash") != page_html_hash:
            logger.debug(f"Selector cache stale for {page_url} (HTML changed)")
            return None

        return cached.get("selectors")

    def cache_selectors(
        self,
        page_url: str,
        selectors: Dict[str, str],
        page_html_hash: Optional[str] = None,
    ) -> None:
        """
        Cache selectors for a page.

        Args:
            page_url: URL of the page
            selectors: Dict mapping semantic names to selectors
            page_html_hash: Optional hash of the page HTML
        """
        key = f"selectors:{page_url}"
        cache_file = self.cache_dir / f"selectors_{self._hash_key(key)}.json"

        data = {
            "url": page_url,
            "selectors": selectors,
            "cached_at": time.time(),
            "html_hash": page_html_hash,
        }

        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

        # Update metadata
        metadata = self._load_metadata()
        metadata["entries"][key] = {
            "type": "selectors",
            "file": cache_file.name,
            "cached_at": data["cached_at"],
        }
        self._save_metadata()

        logger.debug(f"Cached {len(selectors)} selectors for {page_url}")

    # =========================================================================
    # Audio Caching
    # =========================================================================

    def get_audio(self, text: str, voice_id: Optional[str] = None) -> Optional[Path]:
        """
        Get cached audio file for text.

        Args:
            text: The narration text
            voice_id: Optional voice ID (for cache differentiation)

        Returns:
            Path to cached audio file, or None if not cached
        """
        key = f"audio:{voice_id or 'default'}:{text}"
        text_hash = self._hash_content(text)
        cache_file = self.cache_dir / f"audio_{text_hash}.mp3"

        if cache_file.exists():
            logger.debug(f"Audio cache hit for text hash {text_hash}")
            return cache_file

        return None

    def cache_audio(
        self,
        text: str,
        audio_data: bytes,
        voice_id: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Path:
        """
        Cache audio file for text.

        Args:
            text: The narration text
            audio_data: Audio file bytes
            voice_id: Optional voice ID
            duration: Optional audio duration in seconds

        Returns:
            Path to cached audio file
        """
        text_hash = self._hash_content(text)
        cache_file = self.cache_dir / f"audio_{text_hash}.mp3"

        with open(cache_file, "wb") as f:
            f.write(audio_data)

        # Update metadata
        key = f"audio:{voice_id or 'default'}:{text}"
        metadata = self._load_metadata()
        metadata["entries"][key] = {
            "type": "audio",
            "file": cache_file.name,
            "text_hash": text_hash,
            "voice_id": voice_id,
            "duration": duration,
            "cached_at": time.time(),
        }
        self._save_metadata()

        logger.debug(f"Cached audio for text hash {text_hash}")
        return cache_file

    # =========================================================================
    # Screenshot Caching
    # =========================================================================

    def get_screenshot(self, page_url: str, action_id: str) -> Optional[Path]:
        """
        Get cached screenshot for a page/action combination.

        Args:
            page_url: URL of the page
            action_id: Unique identifier for the action

        Returns:
            Path to cached screenshot, or None if not cached
        """
        key = f"screenshot:{page_url}:{action_id}"
        key_hash = self._hash_key(key)
        cache_file = self.cache_dir / f"screenshot_{key_hash}.png"

        if cache_file.exists():
            return cache_file

        return None

    def cache_screenshot(
        self,
        page_url: str,
        action_id: str,
        screenshot_data: bytes,
    ) -> Path:
        """
        Cache a screenshot.

        Args:
            page_url: URL of the page
            action_id: Unique identifier for the action
            screenshot_data: Screenshot bytes

        Returns:
            Path to cached screenshot
        """
        key = f"screenshot:{page_url}:{action_id}"
        key_hash = self._hash_key(key)
        cache_file = self.cache_dir / f"screenshot_{key_hash}.png"

        with open(cache_file, "wb") as f:
            f.write(screenshot_data)

        # Update metadata
        metadata = self._load_metadata()
        metadata["entries"][key] = {
            "type": "screenshot",
            "file": cache_file.name,
            "url": page_url,
            "action_id": action_id,
            "cached_at": time.time(),
        }
        self._save_metadata()

        return cache_file

    # =========================================================================
    # Generic Key-Value Cache
    # =========================================================================

    def get(self, key: str) -> Optional[Any]:
        """
        Get a cached JSON value.

        Args:
            key: Cache key

        Returns:
            Cached value or None
        """
        key_hash = self._hash_key(key)
        cache_file = self.cache_dir / f"kv_{key_hash}.json"

        if not cache_file.exists():
            return None

        with open(cache_file) as f:
            data = json.load(f)

        # Check TTL if set
        if "ttl" in data:
            if time.time() > data["cached_at"] + data["ttl"]:
                logger.debug(f"Cache expired for key {key}")
                cache_file.unlink()
                return None

        return data.get("value")

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set a cached JSON value.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Optional time-to-live in seconds
        """
        key_hash = self._hash_key(key)
        cache_file = self.cache_dir / f"kv_{key_hash}.json"

        data = {
            "key": key,
            "value": value,
            "cached_at": time.time(),
        }
        if ttl:
            data["ttl"] = ttl

        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)

        # Update metadata
        metadata = self._load_metadata()
        metadata["entries"][key] = {
            "type": "kv",
            "file": cache_file.name,
            "cached_at": data["cached_at"],
            "ttl": ttl,
        }
        self._save_metadata()

    # =========================================================================
    # Cache Management
    # =========================================================================

    def clear(self, cache_type: Optional[str] = None) -> int:
        """
        Clear cached files.

        Args:
            cache_type: Optional type to clear (selectors, audio, screenshot, kv)
                       If None, clears all cache

        Returns:
            Number of files deleted
        """
        count = 0
        metadata = self._load_metadata()

        keys_to_remove = []
        for key, entry in metadata["entries"].items():
            if cache_type is None or entry.get("type") == cache_type:
                cache_file = self.cache_dir / entry["file"]
                if cache_file.exists():
                    cache_file.unlink()
                    count += 1
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del metadata["entries"][key]

        self._save_metadata()
        logger.info(f"Cleared {count} cache entries")
        return count

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics
        """
        metadata = self._load_metadata()

        stats = {
            "total_entries": len(metadata["entries"]),
            "by_type": {},
            "total_size_bytes": 0,
        }

        for key, entry in metadata["entries"].items():
            entry_type = entry.get("type", "unknown")
            if entry_type not in stats["by_type"]:
                stats["by_type"][entry_type] = {"count": 0, "size_bytes": 0}

            stats["by_type"][entry_type]["count"] += 1

            cache_file = self.cache_dir / entry["file"]
            if cache_file.exists():
                size = cache_file.stat().st_size
                stats["by_type"][entry_type]["size_bytes"] += size
                stats["total_size_bytes"] += size

        return stats

    def prune_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        count = 0
        metadata = self._load_metadata()
        now = time.time()

        keys_to_remove = []
        for key, entry in metadata["entries"].items():
            if entry.get("ttl") is not None and entry.get("cached_at") is not None:
                if now > entry["cached_at"] + entry["ttl"]:
                    cache_file = self.cache_dir / entry["file"]
                    if cache_file.exists():
                        cache_file.unlink()
                    keys_to_remove.append(key)
                    count += 1

        for key in keys_to_remove:
            del metadata["entries"][key]

        self._save_metadata()
        return count


class GlobalCache:
    """
    Global cache for cross-demo shared data.

    Stores data in ~/.cache/demo-creator/
    """

    def __init__(self):
        self.cache_dir = Path.home() / ".cache" / "demo-creator"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_voice_samples(self) -> Optional[Dict[str, Any]]:
        """Get cached ElevenLabs voice samples."""
        cache_file = self.cache_dir / "voices.json"

        if not cache_file.exists():
            return None

        with open(cache_file) as f:
            data = json.load(f)

        # Cache for 24 hours
        if time.time() - data.get("cached_at", 0) > 86400:
            return None

        return data.get("voices")

    def cache_voice_samples(self, voices: Dict[str, Any]) -> None:
        """Cache ElevenLabs voice samples."""
        cache_file = self.cache_dir / "voices.json"

        with open(cache_file, "w") as f:
            json.dump({
                "voices": voices,
                "cached_at": time.time(),
            }, f, indent=2)


# Convenience functions

def get_cache(demo_id: str) -> DemoCache:
    """Get a cache instance for a demo."""
    return DemoCache(demo_id)


def get_global_cache() -> GlobalCache:
    """Get the global cache instance."""
    return GlobalCache()
