"""Byte-cache for rendered board PNGs.

``MapCache`` is a disk-backed (``/tmp/diplomacy_map_cache``) + in-memory LRU cache
keyed by a hash of the render inputs (svg path, units, phase info, orders, moves).
``render_board_png``/``render_board_png_orders``/``render_board_png_resolution``
(``rendering.board``/``rendering.overlays``) all read and write through the single
module-level ``_map_cache`` instance here.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("diplomacy.rendering.map")


class MapCache:
    """Comprehensive map caching system for performance optimization."""

    # nosec B108 -- documented cache location (CLAUDE.md: "cached ... at
    # /tmp/diplomacy_map_cache"); the app runs on a single-tenant EC2 host with no
    # other local users, so there is no multi-user /tmp collision/symlink risk here.
    def __init__(self, max_size: int = 100, cache_dir: str = "/tmp/diplomacy_map_cache") -> None:  # nosec B108
        self.max_size = max_size
        self.cache_dir = cache_dir
        self.cache: dict[str, tuple[bytes, float]] = {}  # key -> (image_bytes, timestamp)
        self.access_times: dict[str, float] = {}  # key -> last_access_time
        self.logger = logging.getLogger("diplomacy.rendering.map.cache")

        # Create cache directory
        os.makedirs(cache_dir, exist_ok=True)

        # Load existing cache files
        self._load_cache_from_disk()

    def _generate_cache_key(
        self,
        svg_path: str,
        units: dict,
        phase_info: dict | None = None,
        orders: dict | None = None,
        moves: dict | None = None,
    ) -> str:
        """Generate a unique cache key for map parameters."""
        # Create a deterministic hash of all parameters
        key_data = {
            "svg_path": svg_path,
            "units": units,
            "phase_info": phase_info,
            "orders": orders,
            "moves": moves
        }

        # Convert to JSON string and hash
        key_str = json.dumps(key_data, sort_keys=True)
        # Cache key, not a security control -- usedforsecurity=False silences the
        # weak-hash warning without masking a real crypto misuse.
        return hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()

    def _load_cache_from_disk(self) -> None:
        """Load cache metadata from disk on startup."""
        try:
            cache_meta_file = os.path.join(self.cache_dir, "cache_meta.json")
            if os.path.exists(cache_meta_file):
                with open(cache_meta_file, 'r') as f:
                    meta_data = json.load(f)
                    self.access_times = meta_data.get("access_times", {})
        except (OSError, json.JSONDecodeError) as e:
            self.logger.warning(f"Could not load cache metadata: {e}")

    def _save_cache_metadata(self) -> None:
        """Save cache metadata to disk."""
        try:
            cache_meta_file = os.path.join(self.cache_dir, "cache_meta.json")
            meta_data = {
                "access_times": self.access_times,
                "cache_size": len(self.cache)
            }
            with open(cache_meta_file, 'w') as f:
                json.dump(meta_data, f)
        except OSError as e:
            self.logger.warning(f"Could not save cache metadata: {e}")

    def get(self, cache_key: str) -> bytes | None:
        """Get cached map image if available."""
        if cache_key in self.cache:
            # Update access time
            self.access_times[cache_key] = time.time()

            # Try to load from disk if not in memory
            if cache_key not in self.cache or self.cache[cache_key][0] is None:
                cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
                if os.path.exists(cache_file):
                    try:
                        with open(cache_file, 'rb') as f:
                            img_bytes = f.read()
                            self.cache[cache_key] = (img_bytes, time.time())
                            return img_bytes
                    except OSError as e:
                        self.logger.warning(f"Could not load cached image {cache_key}: {e}")

            return self.cache[cache_key][0]

        return None

    def put(self, cache_key: str, img_bytes: bytes) -> None:
        """Cache map image."""
        current_time = time.time()

        # Store in memory
        self.cache[cache_key] = (img_bytes, current_time)
        self.access_times[cache_key] = current_time

        # Save to disk
        try:
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.png")
            with open(cache_file, 'wb') as f:
                f.write(img_bytes)
        except OSError as e:
            self.logger.warning(f"Could not save cached image {cache_key}: {e}")

        # Cleanup if cache is too large
        self._cleanup_cache()

        # Save metadata
        self._save_cache_metadata()

    def _cleanup_cache(self) -> None:
        """Remove least recently used items if cache is too large."""
        if len(self.cache) <= self.max_size:
            return

        # Sort by access time (oldest first)
        sorted_items = sorted(self.access_times.items(), key=lambda x: x[1])

        # Remove oldest items
        items_to_remove = len(self.cache) - self.max_size
        for i in range(items_to_remove):
            key_to_remove = sorted_items[i][0]

            # Remove from memory
            if key_to_remove in self.cache:
                del self.cache[key_to_remove]

            # Remove from disk
            cache_file = os.path.join(self.cache_dir, f"{key_to_remove}.png")
            try:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
            except OSError as e:
                self.logger.warning(f"Could not remove cache file {cache_file}: {e}")

            # Remove from access times
            if key_to_remove in self.access_times:
                del self.access_times[key_to_remove]

    def clear(self) -> None:
        """Clear all cached maps."""
        self.cache.clear()
        self.access_times.clear()

        # Remove all cache files
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.png') or filename == 'cache_meta.json':
                    file_path = os.path.join(self.cache_dir, filename)
                    os.remove(file_path)
        except OSError as e:
            self.logger.warning(f"Could not clear cache directory: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(len(img_bytes) for img_bytes, _ in self.cache.values())
        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "total_bytes": total_size,
            "cache_dir": self.cache_dir,
            "oldest_access": min(self.access_times.values()) if self.access_times else None,
            "newest_access": max(self.access_times.values()) if self.access_times else None
        }


# Global map cache instance -- render_board_png/render_board_png_orders/
# render_board_png_resolution (rendering.board / rendering.overlays) all read and
# write through this one instance.
_map_cache = MapCache()


def get_cache_stats() -> dict[str, Any]:
    """Get map cache statistics."""
    return _map_cache.get_stats()


def clear_map_cache() -> None:
    """Clear all cached maps."""
    _map_cache.clear()
