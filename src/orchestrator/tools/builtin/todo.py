"""TodoList tool for agent task progress tracking."""

import logging
from typing import Any

from orchestrator.tasks.models import TodoItem
from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class TodoListTool(Tool):
    """
    Tool for managing task TODO lists.

    Allows the agent to track progress across multiple reasoning iterations
    by maintaining a structured TODO list within the task context.

    Operations:
    - write: Create/update the entire TODO list
    - add: Add a single TODO item
    - update: Update status of a TODO item
    - list: Get current TODO list
    - clear: Remove all TODO items
    """

    definition = ToolDefinition(
        name="todo_list",
        description="Manage task TODO list to track progress across reasoning iterations. "
        "Use this for complex multi-step tasks to maintain context. "
        "Operations: write (set full list), add (add item), update (change status), "
        "list (view all), clear (remove all)",
        parameters=[
            ToolParameter(
                name="operation",
                type="string",
                description="Operation to perform: 'write', 'add', 'update', 'list', 'clear'",
                required=True,
                enum=["write", "add", "update", "list", "clear"],
            ),
            ToolParameter(
                name="todos",
                type="array",
                description="For 'write': Full list of TODO items. "
                "Each item: {content: str, status: 'pending'|'in_progress'|'completed', "
                "active_form: str}",
                required=False,
            ),
            ToolParameter(
                name="content",
                type="string",
                description="For 'add': Content of the TODO item to add",
                required=False,
            ),
            ToolParameter(
                name="active_form",
                type="string",
                description="For 'add': Active form description (e.g., 'Creating database')",
                required=False,
            ),
            ToolParameter(
                name="index",
                type="integer",
                description="For 'update': Index of TODO item to update (0-based)",
                required=False,
            ),
            ToolParameter(
                name="status",
                type="string",
                description="For 'update': New status ('pending'|'in_progress'|'completed')",
                required=False,
                enum=["pending", "in_progress", "completed"],
            ),
        ],
        requires_approval=False,
        timeout_seconds=10,
        category="task_management",
    )

    def __init__(self):
        """Initialize TodoList tool."""
        self.current_task = None  # Will be injected by orchestrator

    def set_current_task(self, task: Any) -> None:
        """
        Set the current task for this tool instance.

        Args:
            task: Current Task object
        """
        self.current_task = task

    async def execute(
        self,
        operation: str,
        todos: list[dict[str, str]] | None = None,
        content: str | None = None,
        active_form: str | None = None,
        index: int | None = None,
        status: str | None = None,
    ) -> ToolResult:
        """
        Execute TODO list operation.

        Args:
            operation: Operation to perform
            todos: Full TODO list (for 'write')
            content: TODO content (for 'add')
            active_form: Active form description (for 'add')
            index: TODO index (for 'update')
            status: New status (for 'update')

        Returns:
            ToolResult with operation result
        """
        if not self.current_task:
            return ToolResult(
                success=False, error="No current task set. TodoList tool requires task context."
            )

        try:
            if operation == "write":
                return await self._write_todos(todos)
            elif operation == "add":
                return await self._add_todo(content, active_form)
            elif operation == "update":
                return await self._update_todo(index, status)
            elif operation == "list":
                return await self._list_todos()
            elif operation == "clear":
                return await self._clear_todos()
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")

        except Exception as e:
            logger.error(f"Error in TodoListTool: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))

    async def _write_todos(self, todos: list[dict[str, str]] | None) -> ToolResult:
        """
        Write (replace) entire TODO list.

        Args:
            todos: List of TODO dictionaries

        Returns:
            ToolResult
        """
        if not todos:
            return ToolResult(success=False, error="'todos' parameter required for 'write' operation")

        try:
            # Convert to TodoItem objects
            todo_items = []
            for todo_dict in todos:
                todo_items.append(
                    TodoItem(
                        content=todo_dict.get("content", ""),
                        status=todo_dict.get("status", "pending"),
                        active_form=todo_dict.get("active_form", todo_dict.get("content", "")),
                    )
                )

            # Update task
            self.current_task.todo_list = todo_items
            logger.info(f"Updated TODO list with {len(todo_items)} items")

            return ToolResult(
                success=True,
                data={
                    "message": f"TODO list updated with {len(todo_items)} items",
                    "todos": self._format_todos(),
                },
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Failed to write todos: {e}")

    async def _add_todo(self, content: str | None, active_form: str | None) -> ToolResult:
        """
        Add a single TODO item.

        Args:
            content: TODO content
            active_form: Active form description

        Returns:
            ToolResult
        """
        if not content:
            return ToolResult(success=False, error="'content' parameter required for 'add' operation")

        todo_item = TodoItem(
            content=content, status="pending", active_form=active_form or content  # Default to content
        )

        self.current_task.todo_list.append(todo_item)
        logger.info(f"Added TODO item: {content}")

        return ToolResult(
            success=True,
            data={"message": f"Added TODO: {content}", "todos": self._format_todos()},
        )

    async def _update_todo(self, index: int | None, status: str | None) -> ToolResult:
        """
        Update status of a TODO item.

        Args:
            index: TODO index (0-based)
            status: New status

        Returns:
            ToolResult
        """
        if index is None:
            return ToolResult(success=False, error="'index' parameter required for 'update' operation")

        if not status:
            return ToolResult(success=False, error="'status' parameter required for 'update' operation")

        if index < 0 or index >= len(self.current_task.todo_list):
            return ToolResult(
                success=False,
                error=f"Invalid index {index}. TODO list has {len(self.current_task.todo_list)} items",
            )

        # Update status
        self.current_task.todo_list[index].status = status
        updated_content = self.current_task.todo_list[index].content

        logger.info(f"Updated TODO {index} to status '{status}'")

        return ToolResult(
            success=True,
            data={
                "message": f"Updated TODO {index} ({updated_content}) to '{status}'",
                "todos": self._format_todos(),
            },
        )

    async def _list_todos(self) -> ToolResult:
        """
        List all TODO items.

        Returns:
            ToolResult with formatted TODO list
        """
        if not self.current_task.todo_list:
            return ToolResult(success=True, data={"message": "TODO list is empty", "todos": []})

        return ToolResult(success=True, data={"todos": self._format_todos()})

    async def _clear_todos(self) -> ToolResult:
        """
        Clear all TODO items.

        Returns:
            ToolResult
        """
        count = len(self.current_task.todo_list)
        self.current_task.todo_list = []

        logger.info(f"Cleared {count} TODO items")

        return ToolResult(success=True, data={"message": f"Cleared {count} TODO items"})

    def _format_todos(self) -> list[dict[str, Any]]:
        """
        Format TODO list for output.

        Returns:
            Formatted TODO list
        """
        return [
            {
                "index": idx,
                "content": todo.content,
                "status": todo.status,
                "active_form": todo.active_form,
            }
            for idx, todo in enumerate(self.current_task.todo_list)
        ]
