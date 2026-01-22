"""Display hook for real-time CLI output."""

import logging
from typing import Any

from orchestrator.display import get_display_manager
from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class DisplayHook(Hook):
    """
    Hook for real-time CLI display of orchestrator execution.

    Monitors events and displays:
    - Task start/completion
    - LLM reasoning (thinking)
    - Tool execution and results
    - TODO list progress
    - Iteration progress
    """

    priority = 5  # Very high priority to display before other hooks

    def __init__(self, config: dict[str, Any]):
        """
        Initialize display hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.show_iterations = config.get("show_iterations", True)
        self.show_reasoning = config.get("show_reasoning", True)
        self.show_tools = config.get("show_tools", True)
        self.show_todos = config.get("show_todos", True)

        self.display = get_display_manager()

        # Check display manager type
        # StreamingDisplayManager: Use append_* methods for continuous output
        # LiveDisplayManager: Skip most outputs (handled in zones)
        # DisplayManager: Use show_* methods (panel-based)
        self.is_streaming_display = hasattr(self.display, 'append_thinking')
        self.is_live_display = hasattr(self.display, 'start_live') and not self.is_streaming_display

        # Track last TODO state to avoid redundant displays
        self._last_todo_hash: str | None = None

    async def execute(self, context: HookContext) -> HookResult:
        """
        Display event information.

        Args:
            context: Hook context

        Returns:
            HookResult to continue execution
        """
        if not self.enabled:
            return HookResult(action="continue")

        try:
            event = context.event
            data = context.data

            # Task lifecycle events
            if event == "task.started":
                self._display_task_start(data)

            elif event == "task.completed":
                self._display_task_complete(data)

            elif event == "task.failed":
                self._display_task_failed(data)

            # LLM events
            elif event == "llm.before_call":
                self._display_iteration(context.metadata)

            elif event == "llm.after_call":
                self._display_reasoning(data)

            # Tool events
            elif event == "tool.before_execute":
                self._display_tool_execution(data)

            elif event == "tool.after_execute":
                self._display_tool_result(data)

        except Exception as e:
            logger.error(f"Error in DisplayHook: {e}", exc_info=True)

        return HookResult(action="continue")

    def _display_task_start(self, data: dict[str, Any]) -> None:
        """Display task start."""
        # Skip if using live display (handled in reasoning loop)
        if self.is_live_display:
            return

        task = data.get("task")
        if task and hasattr(task, "title"):
            description = getattr(task, "description", None)

            if self.is_streaming_display:
                self.display.append_task_start(task.title, description)
            else:
                self.display.show_task_start(task.title, description)

    def _display_task_complete(self, data: dict[str, Any]) -> None:
        """Display task completion."""
        # Skip if using live display (handled in reasoning loop)
        if self.is_live_display:
            return

        task = data.get("task")
        result = data.get("result")

        if task and hasattr(task, "title"):
            if self.is_streaming_display:
                # UX Fix: In streaming mode, skip Task Complete if result is empty
                # (thinking text was already displayed during streaming)
                if result and result.strip():
                    self.display.append_task_complete(task.title, result=None)
                # Otherwise, don't display anything (avoid empty Task Complete block)
            else:
                self.display.show_task_complete(task.title, result)

    def _display_task_failed(self, data: dict[str, Any]) -> None:
        """Display task failure."""
        # Skip if using live display (handled in reasoning loop)
        if self.is_live_display:
            return

        task = data.get("task")
        error = data.get("error", "Unknown error")

        if task and hasattr(task, "title"):
            if self.is_streaming_display:
                self.display.append_task_failed(task.title, str(error))
            else:
                self.display.show_task_failed(task.title, str(error))

    def _display_iteration(self, metadata: dict[str, Any]) -> None:
        """Display reasoning iteration number."""
        if not self.show_iterations:
            return

        # Skip if using live display (shown in layout)
        if self.is_live_display:
            return

        current = metadata.get("iteration", 0)
        maximum = metadata.get("max_iterations", 20)

        if current > 0:
            if self.is_streaming_display:
                self.display.append_iteration(current, maximum)
            else:
                self.display.show_iteration(current, maximum)

    def _display_reasoning(self, data: dict[str, Any]) -> None:
        """Display LLM reasoning text."""
        if not self.show_reasoning:
            return

        # Skip if using live display (streamed in real-time)
        if self.is_live_display:
            return

        # Skip if using streaming display - already handled by start_thinking_stream
        # in orchestrator._reasoning_loop() to avoid duplicate "● Thinking" headers
        if self.is_streaming_display:
            return

        # Extract reasoning text from response (only for basic display)
        reasoning = data.get("reasoning_text")
        if reasoning:
            self.display.show_thinking(reasoning)

    def _display_tool_execution(self, data: dict[str, Any]) -> None:
        """Display tool execution start."""
        if not self.show_tools:
            return

        # Skip if using live display (handled in reasoning loop)
        if self.is_live_display:
            return

        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})

        if self.is_streaming_display:
            self.display.append_tool_execution(tool_name, tool_input)
            # Note: Activity indicator (spinner) is managed by orchestrator._execute_tool()
            # via show_tool_activity() context manager. No need to start it here.
        else:
            self.display.show_tool_execution(tool_name, tool_input)

    def _display_tool_result(self, data: dict[str, Any]) -> None:
        """Display tool execution result."""
        tool_name = data.get("tool_name", "unknown")

        if not self.show_tools:
            return

        success = data.get("success", False)
        result = data.get("result")

        # Extract data and error from ToolResult
        result_data = None
        error = None

        if result and hasattr(result, "success"):
            result_data = getattr(result, "data", None)
            error = getattr(result, "error", None)

        # Special handling for todo_list tool
        # Update TODO zone for all display types (streaming, live, panel)
        if tool_name == "todo_list" and self.show_todos and success and result_data:
            todos = result_data.get("todos", [])
            if todos:
                # Calculate hash of TODO state to detect changes
                import hashlib
                import json
                todo_state = json.dumps(todos, sort_keys=True)
                todo_hash = hashlib.md5(todo_state.encode()).hexdigest()

                # Only display if TODO state changed
                if todo_hash != self._last_todo_hash:
                    self._last_todo_hash = todo_hash

                    # Convert dict todos to TodoItem-like objects for display
                    from orchestrator.tasks.models import TodoItem

                    todo_items = []
                    for todo_dict in todos:
                        if isinstance(todo_dict, dict):
                            todo_items.append(
                                TodoItem(
                                    content=todo_dict.get("content", ""),
                                    status=todo_dict.get("status", "pending"),
                                    active_form=todo_dict.get("active_form", ""),
                                )
                            )
                    if todo_items:
                        # Update TODO zone (works for all display managers)
                        self.display.show_todo_status(todo_items)
                return  # Don't show regular tool result for todo_list (changed or not)

        # Skip regular tool results if using live display (handled in reasoning loop)
        if self.is_live_display:
            return

        # Show regular tool result
        if self.is_streaming_display:
            self.display.append_tool_result(tool_name, success, result_data, error)
        else:
            self.display.show_tool_result(tool_name, success, result_data, error)
