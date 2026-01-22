"""Cache manager for tool results and LLM responses."""

import logging
from typing import Any, Optional

from orchestrator.cache.models import CacheEntry, CacheStats, generate_cache_key

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Manages caching of tool results and LLM responses.

    Features:
    - TTL-based expiration
    - Automatic cleanup of expired entries
    - Cache statistics tracking
    - Configurable max size
    """

    def __init__(self, config: dict) -> None:
        """
        Initialize cache manager.

        Args:
            config: Cache configuration
        """
        self.config = config
        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()

        # Configuration
        self.enabled = config.get("enabled", False)
        self.default_ttl = config.get("ttl", 3600)  # Default 1 hour
        self.max_entries = config.get("max_entries", 1000)
        self.tool_results_enabled = config.get("tool_results", True)
        self.llm_responses_enabled = config.get("llm_responses", False)

        logger.info(
            f"CacheManager initialized (enabled={self.enabled}, "
            f"ttl={self.default_ttl}s, max_entries={self.max_entries})"
        )

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if not self.enabled:
            return None

        entry = self._cache.get(key)
        if entry is None:
            self._stats.misses += 1
            return None

        # Check expiration
        if entry.is_expired():
            logger.debug(f"Cache entry expired: {key[:16]}...")
            del self._cache[key]
            self._stats.evictions += 1
            self._stats.misses += 1
            return None

        # Cache hit
        entry.increment_hits()
        self._stats.hits += 1
        logger.debug(
            f"Cache hit: {key[:16]}... (age={entry.age_seconds():.1f}s, hits={entry.hits})"
        )

        return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
            metadata: Optional metadata
        """
        if not self.enabled:
            return

        # Check max entries limit
        if len(self._cache) >= self.max_entries and key not in self._cache:
            self._evict_oldest()

        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            ttl=ttl if ttl is not None else self.default_ttl,
            metadata=metadata or {},
        )

        self._cache[key] = entry
        self._stats.total_entries = len(self._cache)

        logger.debug(f"Cached: {key[:16]}... (ttl={entry.ttl}s)")

    def invalidate(self, key: str) -> bool:
        """
        Invalidate cache entry.

        Args:
            key: Cache key

        Returns:
            True if entry was removed, False if not found
        """
        if key in self._cache:
            del self._cache[key]
            self._stats.evictions += 1
            self._stats.total_entries = len(self._cache)
            logger.debug(f"Invalidated: {key[:16]}...")
            return True
        return False

    def clear(self) -> None:
        """Clear all cache entries."""
        count = len(self._cache)
        self._cache.clear()
        self._stats.evictions += count
        self._stats.total_entries = 0
        logger.info(f"Cache cleared ({count} entries removed)")

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items() if entry.is_expired()
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            self._stats.evictions += len(expired_keys)
            self._stats.total_entries = len(self._cache)
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def _evict_oldest(self) -> None:
        """Evict oldest cache entry to make room."""
        if not self._cache:
            return

        # Find oldest entry (by creation time)
        oldest_key = min(self._cache.items(), key=lambda x: x[1].created_at)[0]

        del self._cache[oldest_key]
        self._stats.evictions += 1
        logger.debug(f"Evicted oldest entry: {oldest_key[:16]}...")

    def get_stats(self) -> CacheStats:
        """
        Get cache statistics.

        Returns:
            CacheStats object
        """
        self._stats.total_entries = len(self._cache)
        return self._stats

    def cache_tool_result(
        self, tool_name: str, tool_input: dict, result: Any, ttl: Optional[int] = None
    ) -> str:
        """
        Cache tool execution result.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            result: Tool execution result
            ttl: Optional TTL override

        Returns:
            Cache key
        """
        if not self.tool_results_enabled:
            return ""

        key = generate_cache_key(tool_name, tool_input)
        metadata = {"type": "tool_result", "tool_name": tool_name}

        self.set(key, result, ttl=ttl, metadata=metadata)
        return key

    def get_cached_tool_result(self, tool_name: str, tool_input: dict) -> Optional[Any]:
        """
        Get cached tool result.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            Cached result if found, None otherwise
        """
        if not self.tool_results_enabled:
            return None

        key = generate_cache_key(tool_name, tool_input)
        return self.get(key)

    def cache_llm_response(
        self, messages: list[dict], response: Any, ttl: Optional[int] = None
    ) -> str:
        """
        Cache LLM response.

        Args:
            messages: LLM message history
            response: LLM response
            ttl: Optional TTL override

        Returns:
            Cache key
        """
        if not self.llm_responses_enabled:
            return ""

        key = generate_cache_key("llm", messages)
        metadata = {"type": "llm_response", "message_count": len(messages)}

        self.set(key, response, ttl=ttl, metadata=metadata)
        return key

    def get_cached_llm_response(self, messages: list[dict]) -> Optional[Any]:
        """
        Get cached LLM response.

        Args:
            messages: LLM message history

        Returns:
            Cached response if found, None otherwise
        """
        if not self.llm_responses_enabled:
            return None

        key = generate_cache_key("llm", messages)
        return self.get(key)


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> Optional[CacheManager]:
    """
    Get global CacheManager instance.

    Returns:
        CacheManager instance or None if not initialized
    """
    return _cache_manager


def set_cache_manager(manager: CacheManager) -> None:
    """
    Set global CacheManager instance.

    Args:
        manager: CacheManager to use globally
    """
    global _cache_manager
    _cache_manager = manager
