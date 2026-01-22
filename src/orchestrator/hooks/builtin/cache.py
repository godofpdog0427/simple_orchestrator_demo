"""Cache statistics hook."""

import logging

from orchestrator.cache.manager import get_cache_manager
from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class CacheStatsHook(Hook):
    """
    Hook for tracking and logging cache statistics.

    Monitors cache performance and logs statistics at key events.
    """

    priority = 80  # Lower priority (runs later)

    def __init__(self, config: dict) -> None:
        """
        Initialize cache stats hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.log_interval = config.get("log_interval_seconds", 300)  # 5 minutes
        self.last_log_time = 0

    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute cache stats logging.

        Args:
            context: Hook context

        Returns:
            HookResult to continue
        """
        import time

        cache_manager = get_cache_manager()
        if not cache_manager or not cache_manager.enabled:
            return HookResult(action="continue")

        # Log stats at intervals or on orchestrator stop
        current_time = time.time()
        should_log = (
            context.event == "orchestrator.stop"
            or (current_time - self.last_log_time) >= self.log_interval
        )

        if should_log:
            self.last_log_time = current_time
            stats = cache_manager.get_stats()

            logger.info(
                f"Cache Stats: hits={stats.hits}, misses={stats.misses}, "
                f"hit_rate={stats.hit_rate():.1f}%, entries={stats.total_entries}, "
                f"evictions={stats.evictions}"
            )

            # Cleanup expired entries
            expired_count = cache_manager.cleanup_expired()
            if expired_count > 0:
                logger.debug(f"Cleaned up {expired_count} expired cache entries")

        return HookResult(action="continue")
