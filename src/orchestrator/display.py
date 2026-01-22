"""Display manager for rich CLI output."""

import logging
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from orchestrator.tasks.models import TodoItem

logger = logging.getLogger(__name__)


# Import LiveDisplayManager for new functionality
try:
    from orchestrator.display_live import LiveDisplayManager
except ImportError:
    LiveDisplayManager = None


class DisplayManager:
    """
    Manages rich CLI display for orchestrator execution.

    Provides real-time feedback on:
    - LLM reasoning (thinking)
    - Tool execution status
    - TODO list progress
    - Task results
    """

    def __init__(self, console: Console | None = None):
        """
        Initialize display manager.

        Args:
            console: Rich Console instance (creates new if None)
        """
        self.console = console or Console()
        self._enabled = True

    def enable(self) -> None:
        """Enable display output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable display output."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if display is enabled."""
        return self._enabled

    def show_thinking(self, text: str) -> None:
        """
        Display LLM reasoning/thinking.

        Args:
            text: Reasoning text from LLM
        """
        if not self._enabled or not text.strip():
            return

        panel = Panel(
            Text(text, style="dim cyan"),
            title="[bold cyan]💭 Thinking[/bold cyan]",
            border_style="cyan",
            expand=True,
        )
        self.console.print(panel)

    def show_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """
        Display tool execution start.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
        """
        if not self._enabled:
            return

        # Format arguments
        args_text = self._format_args(args)

        panel = Panel(
            f"[bold]{tool_name}[/bold]\n{args_text}",
            title="[bold yellow]🔧 Executing Tool[/bold yellow]",
            border_style="yellow",
            expand=True,
        )
        self.console.print(panel)

    def show_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """
        Display tool execution result.

        Args:
            tool_name: Name of the tool
            success: Whether execution succeeded
            data: Tool result data
            error: Error message if failed
        """
        if not self._enabled:
            return

        if success:
            status = "[green]✓ Success[/green]"
            color = "green"
        else:
            status = "[red]✗ Failed[/red]"
            color = "red"

        content = f"Tool: [bold]{tool_name}[/bold]\nStatus: {status}"

        if error:
            content += f"\n[red]Error: {error}[/red]"
        elif data:
            # Truncate long data
            data_str = str(data)
            if len(data_str) > 200:
                data_str = data_str[:197] + "..."
            content += f"\nResult: {data_str}"

        panel = Panel(
            content,
            title=f"[bold {color}]📋 Tool Result[/bold {color}]",
            border_style=color,
            expand=True,
        )
        self.console.print(panel)

    def show_todo_status(self, todos: list[TodoItem]) -> None:
        """
        Display current TODO list status.

        Args:
            todos: List of TODO items
        """
        if not self._enabled or not todos:
            return

        table = Table(title="📝 TODO Progress", show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=2)
        table.add_column("Status", width=15)
        table.add_column("Task", style="white")

        for idx, todo in enumerate(todos, 1):
            # Status icons
            if todo.status == "completed":
                status = "[green]✅ Completed[/green]"
            elif todo.status == "in_progress":
                status = "[yellow]⏳ In Progress[/yellow]"
            else:  # pending
                status = "[dim]⏸  Pending[/dim]"

            table.add_row(str(idx), status, todo.content)

        self.console.print(table)
        self.console.print()  # Empty line for spacing

    def show_progress(self, current: int, total: int, message: str = "") -> None:
        """
        Display progress indicator.

        Args:
            current: Current step
            total: Total steps
            message: Optional progress message
        """
        if not self._enabled:
            return

        percentage = int((current / total) * 100) if total > 0 else 0
        bar_length = 30
        filled = int((current / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        text = f"Progress: [{bar}] {percentage}% ({current}/{total})"
        if message:
            text += f"\n{message}"

        self.console.print(f"[bold blue]{text}[/bold blue]")

    def show_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """
        Display task start.

        Args:
            task_title: Task title
            task_description: Optional task description
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]"
        if task_description and task_description != task_title:
            content += f"\n{task_description}"

        panel = Panel(
            content,
            title="[bold green]🚀 Starting Task[/bold green]",
            border_style="green",
            expand=True,
        )
        self.console.print(panel)

    def show_task_complete(self, task_title: str, result: str | None = None) -> None:
        """
        Display task completion.

        Args:
            task_title: Task title
            result: Task result
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]"
        if result:
            # Truncate long results
            result_str = str(result)
            if len(result_str) > 500:
                result_str = result_str[:497] + "..."
            content += f"\n\n{result_str}"

        panel = Panel(
            content,
            title="[bold green]✅ Task Completed[/bold green]",
            border_style="green",
            expand=True,
        )
        self.console.print(panel)

    def show_task_failed(self, task_title: str, error: str) -> None:
        """
        Display task failure.

        Args:
            task_title: Task title
            error: Error message
        """
        if not self._enabled:
            return

        content = f"[bold]{task_title}[/bold]\n\n[red]Error: {error}[/red]"

        panel = Panel(
            content,
            title="[bold red]❌ Task Failed[/bold red]",
            border_style="red",
            expand=True,
        )
        self.console.print(panel)

    def show_iteration(self, current: int, maximum: int) -> None:
        """
        Display reasoning iteration number.

        Args:
            current: Current iteration
            maximum: Maximum iterations
        """
        if not self._enabled:
            return

        self.console.print(f"[dim]── Iteration {current}/{maximum} ──[/dim]")

    def _format_args(self, args: dict[str, Any]) -> str:
        """
        Format tool arguments for display.

        Args:
            args: Tool arguments

        Returns:
            Formatted string
        """
        if not args:
            return "[dim](no arguments)[/dim]"

        lines = []
        for key, value in args.items():
            value_str = str(value)
            # Truncate long values
            if len(value_str) > 100:
                value_str = value_str[:97] + "..."
            lines.append(f"  {key}: {value_str}")

        return "\n".join(lines)


# Global instance for easy access
_display_manager: DisplayManager | None = None


def get_display_manager() -> DisplayManager:
    """
    Get global DisplayManager instance.

    Returns:
        DisplayManager instance
    """
    global _display_manager
    if _display_manager is None:
        _display_manager = DisplayManager()
    return _display_manager


def set_display_manager(manager: DisplayManager) -> None:
    """
    Set global DisplayManager instance.

    Args:
        manager: DisplayManager to use globally
    """
    global _display_manager
    _display_manager = manager


# Task Hierarchy Display Methods (Phase 3)

def show_task_hierarchy(task: Any, all_tasks: dict, depth: int = 0) -> None:
    """
    Display task hierarchy tree.

    Args:
        task: Task object to display
        all_tasks: Dictionary of all tasks {task_id: task}
        depth: Current nesting depth
    """
    display = get_display_manager()
    if not display._enabled:
        return

    # Build tree representation
    indent = "  " * depth
    prefix = "├─ " if depth > 0 else "📋 "

    # Status icon
    status_icons = {
        "pending": "⏸️ ",
        "in_progress": "⏳",
        "completed": "✅",
        "failed": "❌",
        "blocked": "🔒",
        "cancelled": "⛔",
    }
    icon = status_icons.get(task.status.value, "?")

    # Task line
    task_line = f"{indent}{prefix}{icon} {task.title}"

    # Add dependency info if any
    if task.depends_on:
        dep_count = len(task.depends_on)
        task_line += f" [dim](depends on {dep_count} task{'s' if dep_count != 1 else ''})[/dim]"

    display.console.print(task_line)

    # Recursively display subtasks
    for subtask_id in task.subtasks:
        subtask = all_tasks.get(subtask_id)
        if subtask:
            show_task_hierarchy(subtask, all_tasks, depth + 1)


def show_dependency_info(task: Any, dependencies: dict) -> None:
    """
    Show dependency relationships for a task.

    Args:
        task: Task object
        dependencies: Dictionary from task_manager.get_dependencies()
    """
    display = get_display_manager()
    if not display._enabled:
        return

    from rich.panel import Panel
    from rich.table import Table

    # Build dependency info
    lines = []

    if dependencies["depends_on"]:
        lines.append("[bold]Depends on:[/bold]")
        for dep in dependencies["depends_on"]:
            status_color = "green" if dep.status.value == "completed" else "yellow"
            lines.append(f"  → [{status_color}]{dep.title}[/{status_color}] ({dep.status.value})")

    if dependencies["blocks"]:
        lines.append("\n[bold]Blocks:[/bold]")
        for blocked in dependencies["blocks"]:
            status_color = "green" if blocked.status.value == "completed" else "red"
            lines.append(f"  ← [{status_color}]{blocked.title}[/{status_color}] ({blocked.status.value})")

    if dependencies["subtasks"]:
        lines.append(f"\n[bold]Subtasks ({len(dependencies['subtasks'])}):[/bold]")
        for subtask in dependencies["subtasks"]:
            status_icon = "✅" if subtask.status.value == "completed" else "⏳" if subtask.status.value == "in_progress" else "⏸️"
            lines.append(f"  {status_icon} {subtask.title}")

    if dependencies["parent"]:
        parent = dependencies["parent"]
        lines.append(f"\n[bold]Parent Task:[/bold]\n  ↑ {parent.title} ({parent.status.value})")

    if lines:
        content = "\n".join(lines)
        panel = Panel(content, title=f"Dependencies: {task.title}", border_style="cyan")
        display.console.print(panel)
