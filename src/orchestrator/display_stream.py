"""Minimal streaming display manager - pure text output, no Live, no Panel."""

import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from rich.console import Console
from rich.table import Table

from orchestrator.display_activity import ActivityIndicator, ToolActivityIndicator
from orchestrator.tasks.models import TodoItem

logger = logging.getLogger(__name__)


class StreamingDisplayManager:
    """
    極簡串流輸出 display manager。

    特點:
    - 純文字輸出，無 Panel 框框
    - 無 Live display，無固定區域
    - TODO 只在更新時印表格
    - 內容持續向下滾動
    """

    def __init__(
        self,
        console: Console | None = None,
        activity_enabled: bool = True,
        spinner_style: str = "dots",
        spinner_color: str = "cyan",
        warning_delay: float = 10.0,
        warning_interval: float = 15.0,
    ):
        """
        Initialize minimal streaming display manager.

        Args:
            console: Rich Console instance (creates new if None)
            activity_enabled: Whether to show activity indicators during operations
            spinner_style: Style of spinner animation (dots, line, arc, etc.)
            spinner_color: Color of spinner
            warning_delay: Seconds before showing "still waiting" message
            warning_interval: Seconds between subsequent warning updates
        """
        self.console = console or Console()
        self._enabled = True
        self._current_todos: list[TodoItem] = []
        self._last_todo_output = ""  # Track last TODO line to avoid spam

        # Activity indicator for tool execution feedback
        self._activity_indicator = ToolActivityIndicator(
            console=self.console,
            spinner_name=spinner_style,
            style=spinner_color,
            enabled=activity_enabled,
            warning_delay=warning_delay,
            warning_interval=warning_interval,
        )
        self._activity_enabled = activity_enabled

    def enable(self) -> None:
        """Enable display output."""
        self._enabled = True

    def disable(self) -> None:
        """Disable display output."""
        self._enabled = False

    def is_enabled(self) -> bool:
        """Check if display is enabled."""
        return self._enabled

    def _stream_text(self, text: str, style: str = "") -> None:
        """
        Stream text character-by-character (typewriter effect).

        Args:
            text: Text to stream
            style: Rich style to apply
        """
        # Use Rich's console for styled output
        for char in text:
            # Print char without newline
            if style:
                self.console.print(char, end="", style=style)
            else:
                self.console.print(char, end="")
            # Small delay for typewriter effect
            import time
            time.sleep(0.005)  # 5ms delay per char
        # Print final newline
        self.console.print()

    # Core append methods (pure text output)

    def update_todo_list(self, todos: list[TodoItem]) -> None:
        """
        只在 TODO 改變時印表格。

        Args:
            todos: List of TODO items
        """
        if not self._enabled or not todos:
            return

        self._current_todos = todos

        # 建立 Rich Table
        table = Table(show_header=True, header_style="bold magenta", box=None)
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

        # 產生表格字串用於比較
        from io import StringIO
        string_buffer = StringIO()
        temp_console = Console(file=string_buffer, force_terminal=True)
        temp_console.print(table)
        table_output = string_buffer.getvalue()

        # 只在改變時才印
        if table_output != self._last_todo_output:
            # 印標題（綠點 + Update Todos）- Issue 3: Add spacing
            self.console.print("\n● Update Todos", style="bold green")
            # 印表格內容
            self.console.print(table)
            self._last_todo_output = table_output

    def append_thinking(self, text: str) -> None:
        """
        印思考文字（純文字，無框框）。

        Args:
            text: Reasoning text from LLM
        """
        if not self._enabled or not text.strip():
            return

        # UX Fix: Add spacing before thinking block
        self.console.print("\n● Thinking", style="bold cyan")
        # UX Fix: Change thinking content from cyan to white for better readability
        self.console.print("  ", end="")  # Indentation
        self._stream_text(text, style="white")

    # Streaming thinking methods (for real-time LLM output)

    def start_thinking_stream(self) -> None:
        """
        開始 thinking 串流，印標題。
        在收到 LLM 第一個 token 後呼叫（Phase 7B）。
        此時 activity spinner 已停止。
        """
        if not self._enabled:
            return

        self.console.print("\n● Thinking", style="bold cyan")
        self.console.print("  ", end="")  # Indentation for streaming content

    def update_thinking_stream(self, text: str) -> None:
        """
        即時串流 thinking 文字（不換行）。
        在 LLM streaming 期間呼叫。

        Args:
            text: Text chunk from LLM streaming
        """
        if not self._enabled:
            return

        # 直接輸出字元，不換行
        self.console.print(text, end="", style="white")

    def end_thinking_stream(self) -> None:
        """
        結束 thinking 串流，印換行。
        在 LLM streaming 結束後呼叫。
        """
        if not self._enabled:
            return

        self.console.print()  # Print newline to end the stream

    def append_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """
        印工具執行開始。

        Args:
            tool_name: Name of the tool
            args: Tool arguments
        """
        if not self._enabled:
            return

        # Format description from args
        description = self._format_tool_description(tool_name, args)

        # Issue 3: Add spacing before
        # 印標題（綠點 + 工具名稱 + 描述）
        self.console.print(f"\n● {tool_name}  {description}", style="bold")

    def _format_tool_description(self, tool_name: str, args: dict[str, Any]) -> str:
        """Format tool description based on tool type and arguments."""
        # Special formatting for common tools
        if tool_name == "bash":
            cmd = args.get("command", "")
            return cmd[:80] if len(cmd) <= 80 else cmd[:77] + "..."

        # Generic formatting for other tools
        args_str = ", ".join(
            f"{k}={str(v)[:20]}"
            for k, v in list(args.items())[:2]
        )
        if len(args) > 2:
            args_str += "..."
        return args_str

    def append_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """
        印工具執行結果。

        Args:
            tool_name: Name of the tool
            success: Whether execution succeeded
            data: Tool result data
            error: Error message if failed
        """
        if not self._enabled:
            return

        # 印輸出內容（縮排）
        if success and data:
            # 將多行輸出每行都加上縮排
            result_str = str(data)
            for line in result_str.splitlines():
                self.console.print(f"  {line}")
        elif not success:
            self.console.print(f"  Error: {error or 'Unknown error'}", style="red")

    def append_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """
        印任務開始。

        Args:
            task_title: Task title
            task_description: Optional task description
        """
        if not self._enabled:
            return

        self.console.print(f"\n● Task  {task_title}", style="bold green")
        if task_description and task_description != task_title:
            self.console.print(f"  {task_description}", style="dim")

    def append_task_complete(self, task_title: str, result: str | None = None) -> None:
        """
        印任務完成。

        Args:
            task_title: Task title
            result: Task result
        """
        if not self._enabled:
            return

        self.console.print(f"\n● Task Complete  {task_title}", style="bold green")
        if result:
            # UX Fix: Change from "dim" to "white" for better visibility
            for line in str(result).splitlines():
                self.console.print("  ", end="")  # Indentation
                self._stream_text(line, style="white")

    def append_task_failed(self, task_title: str, error: str) -> None:
        """
        印任務失敗。

        Args:
            task_title: Task title
            error: Error message
        """
        if not self._enabled:
            return

        self.console.print(f"\n● Task Failed  {task_title}", style="bold red")
        self.console.print(f"  Error: {error}", style="red")

    def append_iteration(self, current: int, maximum: int) -> None:
        """
        印迭代計數。

        Args:
            current: Current iteration
            maximum: Maximum iterations
        """
        if not self._enabled:
            return

        # Issue 5: Add spacing before and after
        self.console.print(f"\n[Iteration {current}/{maximum}]\n", style="dim")

    def append_subtask_progress(self, current: int, total: int, task_title: str) -> None:
        """
        Display subtask execution progress.

        Args:
            current: Current subtask number (1-indexed)
            total: Total number of subtasks
            task_title: Title of current subtask
        """
        if not self._enabled:
            return

        # Progress bar style display
        progress = f"[{current}/{total}]"
        self.console.print(
            f"\n▶ Subtask {progress} {task_title}",
            style="bold cyan"
        )

    # Backward compatibility with DisplayManager interface

    def show_thinking(self, text: str) -> None:
        """Alias for append_thinking (backward compatibility)."""
        self.append_thinking(text)

    def show_tool_execution(self, tool_name: str, args: dict[str, Any]) -> None:
        """Alias for append_tool_execution (backward compatibility)."""
        self.append_tool_execution(tool_name, args)

    def show_tool_result(self, tool_name: str, success: bool, data: Any = None, error: str | None = None) -> None:
        """Alias for append_tool_result (backward compatibility)."""
        self.append_tool_result(tool_name, success, data, error)

    def show_todo_status(self, todos: list[TodoItem]) -> None:
        """Alias for update_todo_list (backward compatibility)."""
        self.update_todo_list(todos)

    def show_task_start(self, task_title: str, task_description: str | None = None) -> None:
        """Alias for append_task_start (backward compatibility)."""
        self.append_task_start(task_title, task_description)

    def show_task_complete(self, task_title: str, result: str | None = None) -> None:
        """Alias for append_task_complete (backward compatibility)."""
        self.append_task_complete(task_title, result)

    def show_task_failed(self, task_title: str, error: str) -> None:
        """Alias for append_task_failed (backward compatibility)."""
        self.append_task_failed(task_title, error)

    def show_iteration(self, current: int, maximum: int) -> None:
        """Alias for append_iteration (backward compatibility)."""
        self.append_iteration(current, maximum)

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
        bar_length = 20
        filled = int((current / total) * bar_length) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_length - filled)

        text = f"[{bar}] {percentage}% ({current}/{total})"
        if message:
            text += f" {message}"

        self.console.print(text, style="blue")

    # Phase 7: Interrupt status display methods

    def show_interrupt_status(self, message: str = "Interrupt requested...") -> None:
        """
        Display interrupt status to user.

        Args:
            message: Status message to display
        """
        if not self._enabled:
            return

        self.console.print(f"\n[bold yellow]⚠️  {message}[/bold yellow]")

    def show_interrupt_complete(self, message: str = "Execution stopped") -> None:
        """
        Display interrupt completion status.

        Args:
            message: Completion message
        """
        if not self._enabled:
            return

        self.console.print(f"\n[bold green]✓ {message}[/bold green]")
        self.console.print("[dim]Ready for next command[/dim]\n")

    # Phase 7B: Activity Indicator methods

    @asynccontextmanager
    async def show_activity(self, message: str) -> AsyncIterator[None]:
        """
        Show activity indicator during long-running operations.

        Usage:
            async with display.show_activity("Executing bash..."):
                result = await tool.execute()

        Args:
            message: Description of current activity
        """
        if not self._enabled or not self._activity_enabled:
            yield
            return

        async with self._activity_indicator.show(message):
            yield

    @asynccontextmanager
    async def show_tool_activity(
        self,
        tool_name: str,
        args: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> AsyncIterator[None]:
        """
        Show activity indicator for tool execution.

        Args:
            tool_name: Name of the tool being executed
            args: Tool arguments (used to format descriptive message)
            timeout: Optional timeout in seconds (for display only)
        """
        if not self._enabled or not self._activity_enabled:
            yield
            return

        # Format descriptive message based on tool and args
        message = self._activity_indicator.format_tool_message(tool_name, args)

        async with self._activity_indicator.show(message):
            yield

    def start_activity(self, message: str) -> None:
        """
        Start showing activity indicator (manual control).

        Must call stop_activity() when done.

        Args:
            message: Description of current activity
        """
        if not self._enabled or not self._activity_enabled:
            return

        self._activity_indicator.start(message)

    def stop_activity(self) -> None:
        """Stop the activity indicator."""
        self._activity_indicator.stop()

    def update_activity_message(self, message: str) -> None:
        """
        Update the activity message while indicator is running.

        Args:
            message: New message to display
        """
        if self._activity_indicator.is_running:
            self._activity_indicator.update_message(message)
