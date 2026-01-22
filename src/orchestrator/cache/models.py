"""Cache models and data structures."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class CacheEntry:
    """
    Cache entry with TTL and metadata.

    Attributes:
        key: Cache key (hash of input)
        value: Cached value
        created_at: Unix timestamp when created
        ttl: Time-to-live in seconds
        hits: Number of cache hits
        metadata: Additional metadata
    """

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl: int = 3600  # Default 1 hour
    hits: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """
        Check if cache entry has expired.

        Returns:
            True if expired, False otherwise
        """
        if self.ttl <= 0:  # ttl=0 means never expire
            return False
        return time.time() > (self.created_at + self.ttl)

    def increment_hits(self) -> None:
        """Increment cache hit counter."""
        self.hits += 1

    def age_seconds(self) -> float:
        """
        Get age of cache entry in seconds.

        Returns:
            Age in seconds
        """
        return time.time() - self.created_at


@dataclass
class CacheStats:
    """
    Cache statistics.

    Tracks cache performance metrics.
    """

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_entries: int = 0
    total_size_bytes: int = 0

    def hit_rate(self) -> float:
        """
        Calculate cache hit rate.

        Returns:
            Hit rate as percentage (0-100)
        """
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return (self.hits / total) * 100

    def to_dict(self) -> dict[str, Any]:
        """
        Convert stats to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_entries": self.total_entries,
            "total_size_bytes": self.total_size_bytes,
            "hit_rate": self.hit_rate(),
        }


def generate_cache_key(*args, **kwargs) -> str:
    """
    Generate cache key from arguments.

    Uses SHA256 hash of JSON-serialized arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        Cache key (hex digest)
    """
    # Combine args and kwargs into single dict for consistent hashing
    data = {"args": args, "kwargs": kwargs}

    # Serialize to JSON (sorted for consistency)
    json_str = json.dumps(data, sort_keys=True, default=str)

    # Generate SHA256 hash
    hash_obj = hashlib.sha256(json_str.encode("utf-8"))
    return hash_obj.hexdigest()
