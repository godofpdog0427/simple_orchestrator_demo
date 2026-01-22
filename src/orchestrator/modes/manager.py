"""Execution mode manager with tool filtering."""

import logging
from typing import Optional

from orchestrator.modes.models import ExecutionMode, MODE_CONFIGS, ModeConfig

logger = logging.getLogger(__name__)


class ModeManager:
    """Manages execution modes and tool filtering."""

    def __init__(self, initial_mode: ExecutionMode = ExecutionMode.EXECUTE):
        """Initialize mode manager.

        Args:
            initial_mode: The mode to start in (default: EXECUTE)
        """
        self.current_mode = initial_mode
        self.mode_config = MODE_CONFIGS[initial_mode]
        logger.info(f"ModeManager initialized in {initial_mode.value} mode")

    def set_mode(self, mode: ExecutionMode) -> None:
        """Change execution mode.

        Args:
            mode: The new execution mode
        """
        if mode != self.current_mode:
            logger.info(f"Switching mode: {self.current_mode.value} -> {mode.value}")
            self.current_mode = mode
            self.mode_config = MODE_CONFIGS[mode]
        else:
            logger.debug(f"Already in {mode.value} mode")

    def get_mode_config(self) -> ModeConfig:
        """Get current mode configuration.

        Returns:
            The current mode configuration
        """
        return self.mode_config

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if tool is allowed in current mode.

        Args:
            tool_name: Name of the tool to check

        Returns:
            True if tool is allowed, False otherwise
        """
        # Check if tool is explicitly blocked (applies to all modes)
        if tool_name in self.mode_config.blocked_tools:
            return False

        # EXECUTE mode allows all tools (except blocked ones)
        if self.current_mode == ExecutionMode.EXECUTE:
            return True

        # Other modes have restricted tool lists
        return tool_name in self.mode_config.allowed_tools

    def filter_tool_schemas(self, all_schemas: list[dict]) -> list[dict]:
        """Filter tool schemas based on current mode.

        Args:
            all_schemas: List of all available tool schemas

        Returns:
            Filtered list of tool schemas allowed in current mode
        """
        # First, remove blocked tools (applies to all modes)
        blocked_names = set(self.mode_config.blocked_tools)
        schemas_without_blocked = [
            schema for schema in all_schemas
            if schema["name"] not in blocked_names
        ]

        # EXECUTE mode: Return all non-blocked tools
        if self.current_mode == ExecutionMode.EXECUTE:
            filtered = schemas_without_blocked
        else:
            # Other modes: Filter to only allowed tools
            allowed_names = set(self.mode_config.allowed_tools)
            filtered = [
                schema for schema in schemas_without_blocked
                if schema["name"] in allowed_names
            ]

        logger.debug(
            f"Filtered tools for {self.current_mode.value} mode: "
            f"{len(filtered)}/{len(all_schemas)} tools available"
        )

        return filtered

    def get_mode_prompt_suffix(self) -> str:
        """Get system prompt suffix for current mode.

        Returns:
            Mode-specific prompt instructions
        """
        return self.mode_config.system_prompt_suffix
