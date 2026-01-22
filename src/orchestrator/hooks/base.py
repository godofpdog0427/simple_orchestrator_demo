"""Base classes for the hook system."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class HookContext:
    """Context passed to hooks during execution."""

    event: str  # Event name (e.g., "task.started", "tool.before_execute")
    data: dict[str, Any]  # Event-specific data
    orchestrator_state: Optional[Any] = None  # OrchestratorState
    metadata: dict[str, Any] = field(default_factory=dict)  # Metadata from previous hooks


@dataclass
class HookResult:
    """Result returned from hook execution."""

    action: str = "continue"  # "continue" or "block"
    reason: Optional[str] = None  # Reason for blocking (if action="block")
    modified_context: Optional[dict[str, Any]] = None  # Modified context data
    metadata: Optional[dict[str, Any]] = None  # Metadata for next hooks


class Hook(ABC):
    """Base hook interface for user implementation."""

    priority: int = 100  # Lower = higher priority

    @abstractmethod
    async def execute(self, context: HookContext) -> HookResult:
        """
        Execute the hook logic.

        Args:
            context: Hook execution context

        Returns:
            HookResult with:
            - continue_execution: bool - Whether to continue execution
            - modified_payload: Optional[dict] - Modified payload to pass to next hooks
            - metadata: Optional[dict] - Metadata to pass to subsequent hooks
        """
        pass

    def should_run(self, context: HookContext) -> bool:
        """
        Optional filter to skip hook execution.

        Args:
            context: Hook execution context

        Returns:
            bool: True if hook should run, False to skip
        """
        return True


def hook(
    event: str,
    priority: int = 100,
) -> Any:
    """
    Decorator to register a function or class as a hook.

    Args:
        event: Event name to hook into
        priority: Priority (lower = higher priority)

    Returns:
        Decorated function or class
    """

    def decorator(func_or_class: Any) -> Any:
        # If it's a class, just set attributes
        if isinstance(func_or_class, type):
            func_or_class._hook_event = event
            func_or_class._hook_priority = priority
            return func_or_class

        # If it's a function, wrap it in a Hook class
        class FunctionHook(Hook):
            priority = priority

            async def execute(self, context: HookContext) -> HookResult:
                return await func_or_class(context)

        FunctionHook._hook_event = event
        FunctionHook._hook_priority = priority
        return FunctionHook()

    return decorator
