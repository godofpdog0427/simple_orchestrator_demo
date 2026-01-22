"""Subagent models and data structures."""

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SubagentStatus(Enum):
    """Subagent execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class SubagentConstraints:
    """
    Resource constraints for subagent execution.

    These constraints ensure subagents operate within defined resource budgets
    and prevent runaway execution.
    """

    max_tokens: int = 50000  # Maximum tokens for LLM calls
    timeout_seconds: int = 300  # Maximum execution time (5 minutes)
    max_iterations: int = 15  # Maximum reasoning loop iterations
    allowed_tools: Optional[list[str]] = None  # Restricted tool access
    skill: Optional[str] = None  # Optional skill to load
    max_concurrent_subagents: int = 0  # Nested subagents allowed (0 = disabled)

    def __post_init__(self):
        """Set default allowed_tools if None."""
        if self.allowed_tools is None:
            # Default to safe read-only tools
            self.allowed_tools = ["bash", "file_read", "file_write"]


@dataclass
class SubagentHandle:
    """
    Handle for managing and monitoring a spawned subagent.

    Provides async interface to wait for completion and retrieve results.
    """

    task_id: str  # Associated task ID
    parent_task_id: str  # Parent task that spawned this subagent
    status: SubagentStatus = SubagentStatus.PENDING
    result: Optional[Any] = None  # Execution result
    error: Optional[str] = None  # Error message if failed
    _future: Optional[asyncio.Future] = field(default=None, repr=False)

    async def wait(self, timeout: Optional[float] = None) -> Any:
        """
        Wait for subagent to complete.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            Subagent execution result

        Raises:
            asyncio.TimeoutError: If timeout exceeded
            RuntimeError: If subagent failed
        """
        if self._future is None:
            raise RuntimeError("Subagent has no associated future")

        try:
            if timeout:
                result = await asyncio.wait_for(self._future, timeout=timeout)
            else:
                result = await self._future

            self.status = SubagentStatus.COMPLETED
            self.result = result
            return result

        except asyncio.TimeoutError:
            self.status = SubagentStatus.TIMEOUT
            self.error = f"Subagent timeout after {timeout}s"
            raise

        except Exception as e:
            self.status = SubagentStatus.FAILED
            self.error = str(e)
            raise RuntimeError(f"Subagent failed: {e}") from e

    def is_done(self) -> bool:
        """Check if subagent has finished execution."""
        return self.status in [
            SubagentStatus.COMPLETED,
            SubagentStatus.FAILED,
            SubagentStatus.TIMEOUT,
            SubagentStatus.CANCELLED,
        ]

    def is_success(self) -> bool:
        """Check if subagent completed successfully."""
        return self.status == SubagentStatus.COMPLETED


@dataclass
class SubagentContext:
    """
    Context passed to subagent.

    Limited information from parent to ensure isolation.
    """

    task_id: str  # Current subtask ID
    task_title: str  # Subtask title
    task_description: str  # Subtask description
    parent_task_title: str  # Parent task title (for context)
    constraints: SubagentConstraints  # Resource constraints
    skill: Optional[str] = None  # Optional skill to load
    context_data: dict[str, Any] = field(default_factory=dict)  # Additional context
