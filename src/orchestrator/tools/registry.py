"""Tool registry for managing available tools."""

import logging
from pathlib import Path
from typing import Optional

from orchestrator.tools.base import Tool, ToolDefinition

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing and discovering tools."""

    def __init__(self, config: dict) -> None:
        """
        Initialize tool registry.

        Args:
            config: Tool configuration
        """
        self.config = config
        self.tools: dict[str, Tool] = {}

    async def initialize(self) -> None:
        """Initialize and load all tools."""
        logger.info("Initializing tool registry...")

        # Register built-in tools
        await self._register_builtin_tools()

        # Load user tools from directories
        user_dirs = self.config.get("directories", [])
        for directory in user_dirs:
            await self._load_tools_from_directory(Path(directory))

        logger.info(f"Tool registry initialized with {len(self.tools)} tools")

    async def _register_builtin_tools(self) -> None:
        """Register built-in tools."""
        from orchestrator.tools.builtin.bash import BashTool
        from orchestrator.tools.builtin.file_ops import FileDeleteTool, FileReadTool, FileWriteTool
        from orchestrator.tools.builtin.task_decompose import TaskDecomposeTool
        from orchestrator.tools.builtin.todo import TodoListTool
        from orchestrator.tools.builtin.web_fetch import WebFetchTool

        # Register bash tool
        bash_config = self.config.get("bash", {})
        if bash_config.get("enabled", True):
            bash_tool = BashTool(bash_config)
            self.register(bash_tool)

        # Register file tools
        file_read_config = self.config.get("file_read", {})
        if file_read_config.get("enabled", True):
            self.register(FileReadTool(file_read_config))

        file_write_config = self.config.get("file_write", {})
        if file_write_config.get("enabled", True):
            self.register(FileWriteTool(file_write_config))

        file_delete_config = self.config.get("file_delete", {})
        if file_delete_config.get("enabled", True):
            self.register(FileDeleteTool(file_delete_config))

        # Register TodoList tool (Phase 2.5)
        todo_config = self.config.get("todo_list", {})
        if todo_config.get("enabled", True):
            self.register(TodoListTool())

        # Register TaskDecompose tool (Phase 3)
        task_decompose_config = self.config.get("task_decompose", {})
        if task_decompose_config.get("enabled", True):
            self.register(TaskDecomposeTool())

        # Register WebFetch tool
        web_fetch_config = self.config.get("web_fetch", {})
        if web_fetch_config.get("enabled", True):
            self.register(WebFetchTool(web_fetch_config))

    async def _load_tools_from_directory(self, directory: Path) -> None:
        """
        Load tools from a directory.

        Args:
            directory: Directory to scan for tools
        """
        if not directory.exists():
            logger.warning(f"Tool directory does not exist: {directory}")
            return

        # For Phase 1, we skip auto-discovery
        # Tools must be explicitly registered
        logger.debug(f"Skipping auto-discovery for: {directory}")

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool instance to register
        """
        tool_name = tool.definition.name
        if tool_name in self.tools:
            logger.warning(f"Tool already registered, overwriting: {tool_name}")

        self.tools[tool_name] = tool
        logger.info(f"Registered tool: {tool_name}")

    def unregister(self, name: str) -> None:
        """
        Unregister a tool.

        Args:
            name: Tool name to unregister
        """
        if name in self.tools:
            del self.tools[name]
            logger.info(f"Unregistered tool: {name}")

    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None
        """
        return self.tools.get(name)

    def list_all(self) -> list[ToolDefinition]:
        """
        List all registered tools.

        Returns:
            List of tool definitions
        """
        return [tool.definition for tool in self.tools.values()]

    def get_tool_schemas(self) -> list[dict]:
        """
        Get tool schemas in Anthropic format.

        Returns:
            List of tool schema dicts
        """
        schemas = []
        for tool in self.tools.values():
            schema = self._convert_to_anthropic_schema(tool.definition)
            schemas.append(schema)

        return schemas

    def _convert_to_anthropic_schema(self, definition: ToolDefinition) -> dict:
        """
        Convert ToolDefinition to Anthropic tool schema format.

        Args:
            definition: Tool definition

        Returns:
            Anthropic-compatible tool schema
        """
        # Build input schema
        properties = {}
        required = []

        for param in definition.parameters:
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }

            if param.enum:
                properties[param.name]["enum"] = param.enum

            if param.required:
                required.append(param.name)

        input_schema = {
            "type": "object",
            "properties": properties,
        }

        if required:
            input_schema["required"] = required

        # Build tool schema
        schema = {
            "name": definition.name,
            "description": definition.description,
            "input_schema": input_schema,
        }

        return schema
