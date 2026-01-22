"""Task decomposition tool for hierarchical task management."""

import logging
from typing import Any, Optional

from orchestrator.tasks.models import Task, TaskPriority
from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class TaskDecomposeTool(Tool):
    """
    Tool for Agent to decompose complex tasks into subtasks and manage dependencies.

    Operations:
    - create_subtask: Create a new subtask under the current task
    - add_dependency: Add a dependency relationship between tasks
    - remove_dependency: Remove a dependency relationship
    - list_subtasks: List all subtasks of the current task
    - get_task_info: Get detailed information about task relationships
    """

    definition = ToolDefinition(
        name="task_decompose",
        description=(
            "Decompose complex tasks into subtasks and manage task dependencies. "
            "Use this for multi-step workflows that require structured execution order."
        ),
        parameters=[
            ToolParameter(
                name="operation",
                type="string",
                description=(
                    "Operation to perform: "
                    "'create_subtask', 'add_dependency', 'remove_dependency', "
                    "'list_subtasks', 'get_task_info'"
                ),
                required=True,
            ),
            ToolParameter(
                name="title",
                type="string",
                description="Title for the new subtask (required for create_subtask)",
                required=False,
            ),
            ToolParameter(
                name="description",
                type="string",
                description="Description for the new subtask (optional)",
                required=False,
            ),
            ToolParameter(
                name="priority",
                type="string",
                description=(
                    "Priority for the new subtask: 'critical', 'high', 'medium', 'low' "
                    "(optional, defaults to 'medium')"
                ),
                required=False,
            ),
            ToolParameter(
                name="task_id",
                type="string",
                description=(
                    "ID of the task to operate on (for add/remove_dependency). "
                    "If not provided, uses current task."
                ),
                required=False,
            ),
            ToolParameter(
                name="depends_on_task_id",
                type="string",
                description=(
                    "ID of the task that the specified task depends on "
                    "(required for add/remove_dependency)"
                ),
                required=False,
            ),
        ],
        requires_approval=False,
    )

    def __init__(self):
        """Initialize the task decomposition tool."""
        super().__init__()
        self.current_task: Optional[Task] = None
        self.task_manager: Optional[Any] = None

    def set_current_task(self, task: Task) -> None:
        """
        Set the current task context.

        Args:
            task: Current task being executed
        """
        self.current_task = task

    def set_task_manager(self, task_manager: Any) -> None:
        """
        Set the task manager for task operations.

        Args:
            task_manager: TaskManager instance
        """
        self.task_manager = task_manager

    async def execute(
        self,
        operation: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        priority: Optional[str] = None,
        task_id: Optional[str] = None,
        depends_on_task_id: Optional[str] = None,
    ) -> ToolResult:
        """
        Execute task decomposition operation.

        Args:
            operation: Operation to perform
            title: Title for new subtask
            description: Description for new subtask
            priority: Priority level
            task_id: Task ID for dependency operations
            depends_on_task_id: Dependency target task ID

        Returns:
            ToolResult with operation result
        """
        if not self.task_manager:
            return ToolResult(
                success=False,
                error="Task manager not initialized. This tool requires orchestrator context.",
            )

        try:
            if operation == "create_subtask":
                return await self._create_subtask(title, description, priority)

            elif operation == "add_dependency":
                return await self._add_dependency(task_id, depends_on_task_id)

            elif operation == "remove_dependency":
                return await self._remove_dependency(task_id, depends_on_task_id)

            elif operation == "list_subtasks":
                return await self._list_subtasks()

            elif operation == "get_task_info":
                return await self._get_task_info(task_id)

            else:
                return ToolResult(
                    success=False,
                    error=f"Unknown operation: {operation}. "
                    f"Valid operations: create_subtask, add_dependency, remove_dependency, "
                    f"list_subtasks, get_task_info",
                )

        except Exception as e:
            logger.error(f"Error in task_decompose: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))

    async def _create_subtask(
        self,
        title: Optional[str],
        description: Optional[str],
        priority: Optional[str],
    ) -> ToolResult:
        """Create a subtask under the current task."""
        if not self.current_task:
            return ToolResult(
                success=False,
                error="No current task context. This tool must be called during task execution.",
            )

        if not title:
            return ToolResult(
                success=False,
                error="Parameter 'title' is required for create_subtask operation",
            )

        # Parse priority
        task_priority = TaskPriority.MEDIUM
        if priority:
            priority_map = {
                "critical": TaskPriority.CRITICAL,
                "high": TaskPriority.HIGH,
                "medium": TaskPriority.MEDIUM,
                "low": TaskPriority.LOW,
            }
            task_priority = priority_map.get(priority.lower(), TaskPriority.MEDIUM)

        # Create subtask
        subtask = await self.task_manager.create_subtask(
            parent_id=self.current_task.id,
            title=title,
            description=description,
            priority=task_priority,
        )

        return ToolResult(
            success=True,
            data={
                "subtask_id": subtask.id,
                "title": subtask.title,
                "parent_id": subtask.parent_id,
                "priority": subtask.priority.value,
                "message": f"Created subtask '{title}' (ID: {subtask.id})",
            },
        )

    async def _add_dependency(
        self,
        task_id: Optional[str],
        depends_on_task_id: Optional[str],
    ) -> ToolResult:
        """Add a dependency relationship."""
        if not depends_on_task_id:
            return ToolResult(
                success=False,
                error="Parameter 'depends_on_task_id' is required for add_dependency",
            )

        # Use current task if task_id not provided
        target_task_id = task_id or (self.current_task.id if self.current_task else None)
        if not target_task_id:
            return ToolResult(
                success=False,
                error="No task_id provided and no current task context",
            )

        # Add dependency
        await self.task_manager.add_dependency(target_task_id, depends_on_task_id)

        return ToolResult(
            success=True,
            data={
                "task_id": target_task_id,
                "depends_on": depends_on_task_id,
                "message": f"Task {target_task_id} now depends on {depends_on_task_id}",
            },
        )

    async def _remove_dependency(
        self,
        task_id: Optional[str],
        depends_on_task_id: Optional[str],
    ) -> ToolResult:
        """Remove a dependency relationship."""
        if not depends_on_task_id:
            return ToolResult(
                success=False,
                error="Parameter 'depends_on_task_id' is required for remove_dependency",
            )

        # Use current task if task_id not provided
        target_task_id = task_id or (self.current_task.id if self.current_task else None)
        if not target_task_id:
            return ToolResult(
                success=False,
                error="No task_id provided and no current task context",
            )

        # Remove dependency
        await self.task_manager.remove_dependency(target_task_id, depends_on_task_id)

        return ToolResult(
            success=True,
            data={
                "task_id": target_task_id,
                "removed_dependency": depends_on_task_id,
                "message": f"Removed dependency: {target_task_id} no longer depends on {depends_on_task_id}",
            },
        )

    async def _list_subtasks(self) -> ToolResult:
        """List all subtasks of the current task."""
        if not self.current_task:
            return ToolResult(
                success=False,
                error="No current task context",
            )

        subtasks = []
        for subtask_id in self.current_task.subtasks:
            subtask = await self.task_manager.get_task(subtask_id)
            if subtask:
                subtasks.append({
                    "id": subtask.id,
                    "title": subtask.title,
                    "status": subtask.status.value,
                    "priority": subtask.priority.value,
                })

        return ToolResult(
            success=True,
            data={
                "parent_task_id": self.current_task.id,
                "subtasks": subtasks,
                "count": len(subtasks),
            },
        )

    async def _get_task_info(self, task_id: Optional[str]) -> ToolResult:
        """Get detailed task information including relationships."""
        # Use current task if task_id not provided
        target_task_id = task_id or (self.current_task.id if self.current_task else None)
        if not target_task_id:
            return ToolResult(
                success=False,
                error="No task_id provided and no current task context",
            )

        # Get task
        task = await self.task_manager.get_task(target_task_id)
        if not task:
            return ToolResult(
                success=False,
                error=f"Task not found: {target_task_id}",
            )

        # Get dependencies
        deps = await self.task_manager.get_dependencies(target_task_id)

        # Format result
        result = {
            "task_id": task.id,
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority.value,
            "depends_on": [{"id": t.id, "title": t.title, "status": t.status.value} for t in deps["depends_on"]],
            "blocks": [{"id": t.id, "title": t.title, "status": t.status.value} for t in deps["blocks"]],
            "subtasks": [{"id": t.id, "title": t.title, "status": t.status.value} for t in deps["subtasks"]],
            "parent": {
                "id": deps["parent"].id,
                "title": deps["parent"].title,
                "status": deps["parent"].status.value,
            }
            if deps["parent"]
            else None,
        }

        return ToolResult(success=True, data=result)
