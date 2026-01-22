"""Hook engine for event-driven lifecycle management."""

import importlib
import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class HookEngine:
    """
    Hook engine that manages lifecycle hooks.

    Features:
    - Load hooks from YAML configuration
    - Register hooks from user extensions
    - Trigger hooks at lifecycle events
    - Execute hooks in priority order
    - Handle hook results (continue/block/modify)
    """

    def __init__(self, config: dict):
        """
        Initialize hook engine.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.hooks: dict[str, list[tuple[int, Hook]]] = {}  # event -> [(priority, hook)]
        self.enabled = config.get("enabled", False)

    async def initialize(self) -> None:
        """Initialize hook engine and load hooks."""
        if not self.enabled:
            logger.info("Hook system disabled in configuration")
            return

        logger.info("Initializing hook engine...")

        # Load hooks from YAML config
        config_file = self.config.get("config_file", "./config/hooks.yaml")
        if Path(config_file).exists():
            await self._load_hooks_from_yaml(config_file)
        else:
            logger.warning(f"Hook config file not found: {config_file}")

        # TODO: Load hooks from user_extensions directories
        # user_dirs = self.config.get("directories", [])
        # for dir_path in user_dirs:
        #     await self._load_hooks_from_directory(dir_path)

        logger.info(f"Hook engine initialized with {self._count_hooks()} hooks")

    def _count_hooks(self) -> int:
        """Count total number of registered hooks."""
        return sum(len(hooks) for hooks in self.hooks.values())

    async def _load_hooks_from_yaml(self, config_file: str) -> None:
        """
        Load hooks from YAML configuration file.

        Args:
            config_file: Path to hooks.yaml
        """
        try:
            with open(config_file) as f:
                hook_config = yaml.safe_load(f)

            if not hook_config or "hooks" not in hook_config:
                logger.warning(f"No hooks found in {config_file}")
                return

            hooks_by_event = hook_config["hooks"]

            for event, hook_list in hooks_by_event.items():
                if not isinstance(hook_list, list):
                    logger.warning(f"Invalid hook list for event {event}")
                    continue

                for hook_spec in hook_list:
                    await self._register_hook_from_spec(event, hook_spec)

        except Exception as e:
            logger.error(f"Error loading hooks from {config_file}: {e}", exc_info=True)

    async def _register_hook_from_spec(self, event: str, spec: dict) -> None:
        """
        Register a hook from YAML spec.

        Args:
            event: Event name
            spec: Hook specification with path, priority, enabled, config
        """
        if not spec.get("enabled", True):
            logger.debug(f"Skipping disabled hook for event {event}")
            return

        hook_path = spec.get("path")
        if not hook_path:
            logger.warning(f"Hook spec missing 'path' for event {event}")
            return

        try:
            # Parse path as "module.path:ClassName"
            if ":" not in hook_path:
                logger.warning(f"Invalid hook path format: {hook_path}")
                return

            module_path, class_name = hook_path.split(":")

            # Import module and get hook class
            module = importlib.import_module(module_path)
            hook_class = getattr(module, class_name)

            # Instantiate hook with config
            hook_config = spec.get("config", {})
            hook = hook_class(config=hook_config)

            # Register hook
            priority = spec.get("priority", 100)
            self.register(event, hook, priority=priority)

            logger.info(f"Registered hook {class_name} for event '{event}' (priority={priority})")

        except Exception as e:
            logger.error(f"Error registering hook {hook_path} for event {event}: {e}", exc_info=True)

    def register(self, event: str, hook: Hook, priority: int = 100) -> None:
        """
        Register a hook for an event.

        Args:
            event: Event name (e.g., "task.started")
            hook: Hook instance
            priority: Priority (lower = higher priority, executed first)
        """
        if event not in self.hooks:
            self.hooks[event] = []

        self.hooks[event].append((priority, hook))

        # Sort by priority (lower first)
        self.hooks[event].sort(key=lambda x: x[0])

        logger.debug(f"Registered hook {hook.__class__.__name__} for event '{event}' (priority={priority})")

    async def trigger(
        self,
        event: str,
        data: dict[str, Any],
        orchestrator_state: Optional[Any] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> HookResult:
        """
        Trigger all hooks for an event.

        Args:
            event: Event name
            data: Event-specific data
            orchestrator_state: Current orchestrator state

        Returns:
            HookResult: Combined result from all hooks
        """
        if not self.enabled:
            return HookResult(action="continue")

        # Get hooks for this specific event
        event_hooks = self.hooks.get(event, [])

        # Also get wildcard hooks (*)
        wildcard_hooks = self.hooks.get("*", [])

        # Combine and sort by priority
        all_hooks = event_hooks + wildcard_hooks
        all_hooks.sort(key=lambda x: x[0])

        if not all_hooks:
            logger.debug(f"No hooks registered for event '{event}'")
            return HookResult(action="continue")

        logger.debug(f"Triggering {len(all_hooks)} hooks for event '{event}'")

        # Execute hooks in priority order
        context = HookContext(
            event=event,
            data=data,
            orchestrator_state=orchestrator_state,
            metadata=metadata or {},
        )

        for priority, hook in all_hooks:
            try:
                # Check if hook should run
                if not hook.should_run(context):
                    logger.debug(f"Hook {hook.__class__.__name__} skipped (should_run=False)")
                    continue

                # Execute hook
                logger.debug(f"Executing hook {hook.__class__.__name__} (priority={priority})")
                result = await hook.execute(context)

                # Handle modified context
                if result.modified_context:
                    context.data.update(result.modified_context)
                    logger.debug(f"Hook {hook.__class__.__name__} modified context")

                # Propagate metadata
                if result.metadata:
                    context.metadata.update(result.metadata)

                # Check for blocking
                if result.action == "block":
                    reason = result.reason or "Blocked by hook"
                    logger.info(f"Hook {hook.__class__.__name__} blocked event '{event}': {reason}")
                    return HookResult(action="block", reason=reason, modified_context=context.data)

            except Exception as e:
                logger.error(
                    f"Error executing hook {hook.__class__.__name__} for event '{event}': {e}",
                    exc_info=True,
                )
                # Continue with other hooks on error

        # All hooks passed
        return HookResult(action="continue", modified_context=context.data, metadata=context.metadata)

    def get_hooks_for_event(self, event: str) -> list[Hook]:
        """
        Get all hooks registered for an event.

        Args:
            event: Event name

        Returns:
            List of hooks
        """
        event_hooks = [hook for _, hook in self.hooks.get(event, [])]
        wildcard_hooks = [hook for _, hook in self.hooks.get("*", [])]
        return event_hooks + wildcard_hooks

    def is_enabled(self) -> bool:
        """Check if hook system is enabled."""
        return self.enabled
