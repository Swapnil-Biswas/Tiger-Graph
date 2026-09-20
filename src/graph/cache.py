"""
Enterprise Thread-Safe LRU Query Cache with Dynamic Tag Invalidation
===================================================================
Provides high-throughput microsecond caching for repetitive graph traversals,
entity profiling, and nexus queries with automatic TTL eviction and tag-based
invalidation on streaming updates.
"""

import time
import threading
from collections import OrderedDict
from typing import Dict, Set, Any, Optional, List, Tuple


class CacheEntry:
    __slots__ = ("key", "val", "created_at", "tags")

    def __init__(self, key: str, val: Any, tags: Optional[Set[str]] = None):
        self.key = key
        self.val = val
        self.created_at = time.time()
        self.tags = tags or set()


class LRUQueryCache:
    """Thread-safe LRU Cache with TTL and tag-based invalidation."""

    def __init__(self, max_capacity: int = 5000, ttl_seconds: float = 60.0):
        self.max_capacity = max(1, max_capacity)
        self.ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tag_index: Dict[str, Set[str]] = {}  # tag -> set of keys

        # Telemetry metrics
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.invalidations = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from cache if present and unexpired."""
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self.misses += 1
                return None

            # Check TTL
            if (time.time() - entry.created_at) > self.ttl_seconds:
                self._remove_entry(key)
                self.misses += 1
                return None

            # Mark as recently used
            self._cache.move_to_end(key)
            self.hits += 1
            return entry.val

    def put(self, key: str, val: Any, tags: Optional[Set[str]] = None) -> None:
        """Insert or update an item in the cache."""
        with self._lock:
            tag_set = set(tags) if tags else set()

            if key in self._cache:
                self._remove_entry(key)

            # Evict LRU if at capacity
            while len(self._cache) >= self.max_capacity:
                oldest_key, _ = self._cache.popitem(last=False)
                self._cleanup_tag_references(oldest_key)
                self.evictions += 1

            # Insert new entry
            entry = CacheEntry(key, val, tag_set)
            self._cache[key] = entry
            for tag in tag_set:
                if tag not in self._tag_index:
                    self._tag_index[tag] = set()
                self._tag_index[tag].add(key)

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all cached entries associated with a specific tag (e.g. card_id, device_id)."""
        with self._lock:
            keys_to_remove = self._tag_index.get(tag, set()).copy()
            for k in keys_to_remove:
                self._remove_entry(k)
            self.invalidations += len(keys_to_remove)
            return len(keys_to_remove)

    def invalidate_by_tags(self, tags: List[str]) -> int:
        """Invalidate entries matching any of the provided tags."""
        with self._lock:
            total = 0
            for t in tags:
                total += self.invalidate_by_tag(t)
            return total

    def _remove_entry(self, key: str) -> None:
        """Helper to cleanly remove entry and update tag index."""
        entry = self._cache.pop(key, None)
        if entry:
            self._cleanup_tag_references(key, entry.tags)

    def _cleanup_tag_references(self, key: str, tags: Optional[Set[str]] = None) -> None:
        """Remove key from tag indices."""
        target_tags = tags
        if target_tags is None:
            # Fallback: scan indices
            for tag, keys in list(self._tag_index.items()):
                keys.discard(key)
                if not keys:
                    del self._tag_index[tag]
            return

        for tag in target_tags:
            if tag in self._tag_index:
                self._tag_index[tag].discard(key)
                if not self._tag_index[tag]:
                    del self._tag_index[tag]

    def clear(self) -> None:
        """Reset cache and statistics."""
        with self._lock:
            self._cache.clear()
            self._tag_index.clear()
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.invalidations = 0

    def stats(self) -> Dict[str, Any]:
        """Return operational metrics for telemetry exposition."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_ratio = round((self.hits / total_requests), 4) if total_requests > 0 else 0.0
            return {
                "current_size": len(self._cache),
                "max_capacity": self.max_capacity,
                "ttl_seconds": self.ttl_seconds,
                "hits": self.hits,
                "misses": self.misses,
                "total_requests": total_requests,
                "hit_ratio": hit_ratio,
                "evictions": self.evictions,
                "invalidations": self.invalidations,
                "active_tags_count": len(self._tag_index),
            }


_DEFAULT_QUERY_CACHE = LRUQueryCache()


def get_query_cache() -> LRUQueryCache:
    """Get singleton default query cache instance."""
    return _DEFAULT_QUERY_CACHE
