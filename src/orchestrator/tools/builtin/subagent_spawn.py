"""Subagent spawn tool for delegating tasks to isolated child agents."""

import json
import logging
from typing import Any, Optional

from orchestrator.subagents.manager import SubagentManager
from orchestrator.subagents.models import SubagentConstraints
from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class SubagentSpawnTool(Tool):
    """
    Tool for spawning and managing subagents.

    Allows Agent to delegate complex subtasks to isolated child agents
    with resource constraints.
    """

    definition = ToolDefinition(
        name="subagent_spawn",
        description=(
            "Spawn isolated subagent to execute a subtask with resource constraints. "
            "Use this when a subtask is complex enough to warrant dedicated Agent execution. "
            "Subagents have limited context, tools, and resources to ensure isolation."
        ),
        parameters=[
            ToolParameter(
                name="operation",
                type="string",
                description=(
                    "Operation to perform: "
                    "'spawn' (create new subagent), "
                    "'wait' (wait for subagent completion), "
                    "'list_active' (list active subagents), "
                    "'get_status' (get subagent status)"
                ),
                required=True,
            ),
            ToolParameter(
                name="subtask_id",
                type="string",
                description="Subtask ID (required for spawn operation)",
                required=False,
            ),
            ToolParameter(
                name="max_tokens",
                type="integer",
                description="Maximum tokens for LLM calls (default: 50000)",
                required=False,
            ),
            ToolParameter(
                name="timeout_seconds",
                type="integer",
                description="Maximum execution time in seconds (default: 300)",
                required=False,
            ),
            ToolParameter(
                name="max_iterations",
                type="integer",
                description="Maximum reasoning loop iterations (default: 15)",
                required=False,
            ),
            ToolParameter(
                name="allowed_tools",
                type="array",
                description=(
                    "List of allowed tool names "
                    "(default: ['bash', 'file_read', 'file_write'])"
                ),
                required=False,
            ),
            ToolParameter(
                name="skill",
                type="string",
                description="Optional skill name to load for subagent",
                required=False,
            ),
            ToolParameter(
                name="context",
                type="object",
                description="Additional context data to pass to subagent",
                required=False,
            ),
            ToolParameter(
                name="wait_timeout",
                type="integer",
                description="Timeout for wait operation in seconds",
                required=False,
            ),
        ],
        requires_approval=False,
    )

    def __init__(
        self,
        subagent_manager: SubagentManager,
        task_manager: Any,
        orchestrator_factory: callable,
    ):
        """
        Initialize subagent spawn tool.

        Args:
            subagent_manager: SubagentManager instance
            task_manager: TaskManager instance
            orchestrator_factory: Factory function to create orchestrator instances
        """
        self.subagent_manager = subagent_manager
        self.task_manager = task_manager
        self.orchestrator_factory = orchestrator_factory

    async def execute(
        self,
        operation: str,
        subtask_id: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout_seconds: Optional[int] = None,
        max_iterations: Optional[int] = None,
        allowed_tools: Optional[list[str]] = None,
        skill: Optional[str] = None,
        context: Optional[dict] = None,
        wait_timeout: Optional[int] = None,
    ) -> ToolResult:
        """
        Execute subagent operation.

        Args:
            operation: Operation to perform
            subtask_id: Subtask ID (for spawn/wait/get_status)
            max_tokens: Token limit constraint
            timeout_seconds: Timeout constraint
            max_iterations: Iteration limit constraint
            allowed_tools: Tool restriction list
            skill: Optional skill to load
            context: Additional context data
            wait_timeout: Timeout for wait operation

        Returns:
            ToolResult with operation outcome
        """
        try:
            if operation == "spawn":
                return await self._spawn_subagent(
                    subtask_id=subtask_id,
                    max_tokens=max_tokens,
                    timeout_seconds=timeout_seconds,
                    max_iterations=max_iterations,
                    allowed_tools=allowed_tools,
                    skill=skill,
                    context=context or {},
                )

            elif operation == "wait":
                return await self._wait_for_subagent(
                    subtask_id=subtask_id, timeout=wait_timeout
                )

            elif operation == "list_active":
                return self._list_active_subagents()

            elif operation == "get_status":
                return self._get_subagent_status(subtask_id=subtask_id)

            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown operation: {operation}. "
                    f"Valid operations: spawn, wait, list_active, get_status",
                )

        except Exception as e:
            logger.error(f"SubagentSpawnTool error: {e}")
            return ToolResult(success=False, error=str(e))

    async def _spawn_subagent(
        self,
        subtask_id: str,
        max_tokens: Optional[int],
        timeout_seconds: Optional[int],
        max_iterations: Optional[int],
        allowed_tools: Optional[list[str]],
        skill: Optional[str],
        context: dict,
    ) -> ToolResult:
        """Spawn a new subagent."""
        if not subtask_id:
            return ToolResult(success=False, error="subtask_id is required for spawn")

        # Get subtask
        subtask = await self.task_manager.get_task(subtask_id)
        if not subtask:
            return ToolResult(success=False, error=f"Subtask not found: {subtask_id}")

        # Get parent task
        parent_task = None
        if subtask.parent_id:
            parent_task = await self.task_manager.get_task(subtask.parent_id)

        if not parent_task:
            return ToolResult(
                success=False, error="Cannot spawn subagent: parent task not found"
            )

        # Build constraints
        constraints = SubagentConstraints(
            max_tokens=max_tokens or 50000,
            timeout_seconds=timeout_seconds or 300,
            max_iterations=max_iterations or 15,
            allowed_tools=allowed_tools,
            skill=skill,
        )

        # Spawn subagent
        try:
            handle = await self.subagent_manager.spawn(
                parent_task=parent_task,
                subtask=subtask,
                context=context,
                constraints=constraints,
                orchestrator_factory=self.orchestrator_factory,
            )

            return ToolResult(
                success=True,
                data={
                    "message": f"Subagent spawned for task '{subtask.title}'",
                    "task_id": subtask_id,
                    "status": handle.status.value,
                    "constraints": {
                        "max_tokens": constraints.max_tokens,
                        "timeout_seconds": constraints.timeout_seconds,
                        "max_iterations": constraints.max_iterations,
                        "allowed_tools": constraints.allowed_tools,
                    },
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to spawn subagent: {e}")

    async def _wait_for_subagent(
        self, subtask_id: str, timeout: Optional[int]
    ) -> ToolResult:
        """Wait for subagent completion."""
        if not subtask_id:
            return ToolResult(success=False, error="subtask_id is required for wait")

        handle = self.subagent_manager.get_handle(subtask_id)
        if not handle:
            return ToolResult(
                success=False, error=f"No active subagent for task: {subtask_id}"
            )

        try:
            result = await handle.wait(timeout=timeout)

            return ToolResult(
                success=True,
                data={
                    "message": "Subagent completed successfully",
                    "task_id": subtask_id,
                    "status": handle.status.value,
                    "result": str(result),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Subagent wait failed: {e}",
                data={
                    "task_id": subtask_id,
                    "status": handle.status.value,
                    "error": handle.error,
                },
            )

    def _list_active_subagents(self) -> ToolResult:
        """List all active subagents."""
        active = self.subagent_manager.list_active()

        if not active:
            return ToolResult(success=True, data={"message": "No active subagents"})

        subagents_info = []
        for handle in active:
            subagents_info.append(
                {
                    "task_id": handle.task_id,
                    "parent_task_id": handle.parent_task_id,
                    "status": handle.status.value,
                }
            )

        return ToolResult(
            success=True,
            data={
                "active_count": len(active),
                "subagents": subagents_info,
            },
        )

    def _get_subagent_status(self, subtask_id: str) -> ToolResult:
        """Get status of a specific subagent."""
        if not subtask_id:
            return ToolResult(
                success=False, error="subtask_id is required for get_status"
            )

        handle = self.subagent_manager.get_handle(subtask_id)
        if not handle:
            return ToolResult(
                success=False, error=f"No active subagent for task: {subtask_id}"
            )

        return ToolResult(
            success=True,
            data={
                "task_id": handle.task_id,
                "parent_task_id": handle.parent_task_id,
                "status": handle.status.value,
                "is_done": handle.is_done(),
                "is_success": handle.is_success(),
                "error": handle.error,
            },
        )
