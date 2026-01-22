"""Live display manager with fixed layout zones."""

import logging
from typing import Any, Optional

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from orchestrator.tasks.models import TodoItem

logger = logging.getLogger(__name__)


class LiveDisplayManager:
    """
    Live display manager with fixed layout zones.

    Provides real-time, non-jumping display with:
    - Top: TODO list progress
    - Middle: LLM thinking (streaming)
    - Bottom: Tool execution status
    """

    def __init__(self, console: Console | None = None):
        """
        Initialize live display manager.

        Args:
            console: Rich Console instance (creates new if None)
        """
        self.console = console or Console()
        self._enabled = True
        self._live: Optional[Live] = None
        self._layout: Optional[Layout] = None

        # State for each zone
        self._todo_items: list[TodoItem] = []
        self._thinking_text: str = ""
        self._tool_status: str = ""
        self._is_live_active = False

    def enable(self) -> None:
        """Enable display output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable display output."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if display is enabled."""
        return self._enabled

    def start_live(self) -> None:
        """Start live display mode with fixed layout."""
        if not self._enabled or self._is_live_active:
            return

        # Create layout with 3 zones
        self._layout = Layout()
        self._layout.split_column(
            Layout(name="todo", size=10),
            Layout(name="thinking", ratio=2),
            Layout(name="tool", size=8),
        )

        # Initialize zones
        self._update_layout()

        # Start live display
        self._live = Live(
            self._layout,
            console=self.console,
            refresh_per_second=10,
            screen=False,
        )
        self._live.start()
        self._is_live_active = True

        logger.debug("Live display started")

    def stop_live(self) -> None:
        """Stop live display mode."""
        if self._live and self._is_live_active:
            self._live.stop()
            self._is_live_active = False
            self._live = None
            logger.debug("Live display stopped")

    def update_thinking_stream(self, text_chunk: str) -> None:
        """
        Update thinking zone with streaming text.

        Args:
            text_chunk: New text chunk to append
        """
        if not self._enabled or not self._is_live_active:
            return

        self._thinking_text += text_chunk
        self._update_layout()

    def clear_thinking(self) -> None:
        """Clear thinking zone."""
        self._thinking_text = ""
        if self._is_live_active:
            self._update_layout()

    def update_todo_list(self, todos: list[TodoItem]) -> None:
        """
        Update TODO list zone.

        Args:
            todos: List of TODO items
        """
        if not self._enabled:
            return

        self._todo_items = todos
        if self._is_live_active:
            self._update_layout()

    def update_tool_status(self, status: str) -> None:
        """
        Update tool execution status zone.

        Args:
            status: Status text to display
        """
        if not self._enabled:
            return

        self._tool_status = status
        if self._is_live_active:
            self._update_layout()

    def clear_tool_status(self) -> None:
        """Clear tool status zone."""
        self._tool_status = ""
        if self._is_live_active:
            self._update_layout()

    def _update_layout(self) -> None:
        """Update all layout zones with current state."""
        if not self._layout:
            return

        # Update TODO zone
        self._layout["todo"].update(self._render_todo_zone())

        # Update thinking zone
        self._layout["thinking"].update(self._render_thinking_zone())

        # Update tool zone
        self._layout["tool"].update(self._render_tool_zone())

    def _render_todo_zone(self) -> Panel:
        """Render TODO list zone."""
        if not self._todo_items:
            content = Text("No active tasks", style="dim")
        else:
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column("#", style="dim", width=2)
            table.add_column("Status", width=3)
            table.add_column("Task", style="white")

            for idx, todo in enumerate(self._todo_items[:5], 1):  # Show max 5
                # Status icons
                if todo.status == "completed":
                    icon = "[green]✅[/green]"
                elif todo.status == "in_progress":
                    icon = "[yellow]⏳[/yellow]"
                else:  # pending
                    icon = "[dim]⏸ [/dim]"

                # Truncate long tasks
                task_text = todo.content
                if len(task_text) > 50:
                    task_text = task_text[:47] + "..."

                table.add_row(str(idx), icon, task_text)

            content = table

        return Panel(
            content,
            title="[bold magenta]📝 TODO Progress[/bold magenta]",
            border_style="magenta",
            expand=True,
        )

    def _render_thinking_zone(self) -> Panel:
        """Render LLM thinking zone."""
        if not self._thinking_text:
            content = Text("Waiting for response...", style="dim cyan")
        else:
            # Truncate if too long (keep last 1000 chars for display)
            display_text = self._thinking_text
            if len(display_text) > 1000:
                display_text = "..." + display_text[-997:]

            content = Text(display_text, style="cyan")

        return Panel(
            content,
            title="[bold cyan]💭 Thinking[/bold cyan]",
            border_style="cyan",
            expand=True,
        )

    def _render_tool_zone(self) -> Panel:
        """Render tool execution zone."""
        if not self._tool_status:
            content = Text("No active tools", style="dim")
        else:
            content = Text(self._tool_status, style="yellow")

        return Panel(
            content,
            title="[bold yellow]🔧 Tool Execution[/bold yellow]",
            border_style="yellow",
            expand=True,
        )

    # Compatibility methods for existing code
    def show_thinking(self, text: str) -> None:
        """Display LLM reasoning/thinking (legacy compatibility)."""
        if not self._enabled:
            return

        if self._is_live_active:
            self._thinking_text = text
            self._update_layout()
        else:
            # Fallback to panel display
            panel = Panel(
                Text(text, style="dim cyan"),
                title="[bold cyan]💭 Thinking[/bold cyan]",
                border_style="cyan",
                expand=True,
            )
            self.console.print(panel)

    def show_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """Display tool execution start (legacy compatibility)."""
        if not self._enabled:
            return

        # Format arguments
        args_text = self._format_args(args)
        status = f"▶ Running: [bold]{tool_name}[/bold]\n{args_text}"

        if self._is_live_active:
            self.update_tool_status(status)
        else:
            # Fallback to panel display
            panel = Panel(
                status,
                title="[bold yellow]🔧 Executing Tool[/bold yellow]",
                border_style="yellow",
                expand=True,
            )
            self.console.print(panel)

    def show_tool_result(
        self, tool_name: str, success: bool, data: Any = None, error: str | None = None
    ) -> None:
        """Display tool execution result (legacy compatibility)."""
        if not self._enabled:
            return

        if success:
            status = f"✓ [green]Success[/green]: {tool_name}"
            color = "green"
        else:
            status = f"✗ [red]Failed[/red]: {tool_name}"
            if error:
                status += f"\n[red]{error}[/red]"
            color = "red"

        if self._is_live_active:
            self.update_tool_status(status)
        else:
            # Fallback to panel display
            panel = Panel(
                status,
                title=f"[bold {color}]📋 Tool Result[/bold {color}]",
                border_style=color,
                expand=True,
            )
            self.console.print(panel)

    def show_todo_status(self, todos: list[TodoItem]) -> None:
        """Display current TODO list status (legacy compatibility)."""
        if not self._enabled:
            return

        if self._is_live_active:
            self.update_todo_list(todos)
        else:
            # Fallback to table display
            if not todos:
                return

            table = Table(
                title="📝 TODO Progress", show_header=True, header_style="bold magenta"
            )
            table.add_column("#", style="dim", width=2)
            table.add_column("Status", width=15)
            table.add_column("Task", style="white")

            for idx, todo in enumerate(todos, 1):
                if todo.status == "completed":
                    status = "[green]✅ Completed[/green]"
                elif todo.status == "in_progress":
                    status = "[yellow]⏳ In Progress[/yellow]"
                else:
                    status = "[dim]⏸  Pending[/dim]"

                table.add_row(str(idx), status, todo.content)

            self.console.print(table)
            self.console.print()

    def _format_args(self, args: dict[str, Any]) -> str:
        """Format tool arguments for display."""
        if not args:
            return "[dim](no arguments)[/dim]"

        lines = []
        for key, value in args.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:97] + "..."
            lines.append(f"  {key}: {value_str}")

        return "\n".join(lines)

    # Phase 7: Interrupt status display methods

    def show_interrupt_status(self, message: str = "Interrupt requested...") -> None:
        """
        Display interrupt status to user.

        Args:
            message: Status message to display
        """
        if not self._enabled:
            return

        # If live display is active, update the tool status zone
        if self._is_live_active:
            self._tool_status = f"[bold yellow]⚠️  {message}[/bold yellow]"
            self._update_layout()
        else:
            self.console.print(f"\n[bold yellow]⚠️  {message}[/bold yellow]")

    def show_interrupt_complete(self, message: str = "Execution stopped") -> None:
        """
        Display interrupt completion status.

        Args:
            message: Completion message
        """
        if not self._enabled:
            return

        # Stop live display first if active
        if self._is_live_active:
            self.stop_live()

        self.console.print(f"\n[bold green]✓ {message}[/bold green]")
        self.console.print("[dim]Ready for next command[/dim]\n")
