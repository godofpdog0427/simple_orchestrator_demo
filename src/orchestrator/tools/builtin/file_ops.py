"""File operation tools."""

import logging
from pathlib import Path

from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)


class FileReadTool(Tool):
    """Tool for reading file contents."""

    def __init__(self, config: dict) -> None:
        """
        Initialize file read tool.

        Args:
            config: Tool configuration
        """
        self.config = config
        self.max_file_size_mb = config.get("max_file_size_mb", 10)

        self.definition = ToolDefinition(
            name="file_read",
            description="Read the contents of a file. Returns the file content as text.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to read",
                    required=True,
                ),
            ],
            requires_approval=config.get("requires_approval", False),
            category="file",
        )

    async def execute(self, path: str) -> ToolResult:
        """
        Read file contents.

        Args:
            path: File path to read

        Returns:
            ToolResult with file contents
        """
        try:
            file_path = Path(path)

            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"Not a file: {path}")

            # Check file size
            file_size_mb = file_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                return ToolResult(
                    success=False,
                    error=f"File too large: {file_size_mb:.2f}MB (max: {self.max_file_size_mb}MB)",
                )

            # Read file
            content = file_path.read_text(encoding="utf-8")

            logger.info(f"Read file: {path} ({len(content)} chars)")

            return ToolResult(success=True, data=content)

        except UnicodeDecodeError:
            return ToolResult(success=False, error=f"File is not valid UTF-8 text: {path}")
        except Exception as e:
            logger.error(f"Error reading file {path}: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Read error: {e}")


class FileWriteTool(Tool):
    """Tool for writing file contents."""

    def __init__(self, config: dict) -> None:
        """
        Initialize file write tool.

        Args:
            config: Tool configuration
        """
        self.config = config

        self.definition = ToolDefinition(
            name="file_write",
            description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to write",
                    required=True,
                ),
                ToolParameter(
                    name="content",
                    type="string",
                    description="Content to write to the file",
                    required=True,
                ),
            ],
            requires_approval=config.get("requires_approval", True),
            category="file",
        )

    async def execute(self, path: str, content: str) -> ToolResult:
        """
        Write content to file.

        Args:
            path: File path to write
            content: Content to write

        Returns:
            ToolResult
        """
        try:
            file_path = Path(path)

            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write file
            file_path.write_text(content, encoding="utf-8")

            logger.info(f"Wrote file: {path} ({len(content)} chars)")

            return ToolResult(success=True, data=f"Successfully wrote {len(content)} characters to {path}")

        except Exception as e:
            logger.error(f"Error writing file {path}: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Write error: {e}")


class FileDeleteTool(Tool):
    """Tool for deleting files."""

    def __init__(self, config: dict) -> None:
        """
        Initialize file delete tool.

        Args:
            config: Tool configuration
        """
        self.config = config

        self.definition = ToolDefinition(
            name="file_delete",
            description="Delete a file. Use with caution as this operation cannot be undone.",
            parameters=[
                ToolParameter(
                    name="path",
                    type="string",
                    description="Path to the file to delete",
                    required=True,
                ),
            ],
            requires_approval=config.get("requires_approval", True),
            category="file",
        )

    async def execute(self, path: str) -> ToolResult:
        """
        Delete a file.

        Args:
            path: File path to delete

        Returns:
            ToolResult
        """
        try:
            file_path = Path(path)

            if not file_path.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            if not file_path.is_file():
                return ToolResult(success=False, error=f"Not a file: {path}")

            # Delete file
            file_path.unlink()

            logger.info(f"Deleted file: {path}")

            return ToolResult(success=True, data=f"Successfully deleted {path}")

        except Exception as e:
            logger.error(f"Error deleting file {path}: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Delete error: {e}")
