"""Bash command execution tool."""

import asyncio
import logging
import re
from pathlib import Path
from typing import Optional

from orchestrator.tools.base import Tool, ToolDefinition, ToolParameter, ToolResult

logger = logging.getLogger(__name__)

# Dangerous commands blocked in read-only mode
DANGEROUS_COMMANDS = [
    "reboot", "shutdown", "halt", "poweroff",
    "killall", "pkill",
    "dd", "mkfs", "fdisk", "parted",
    ":()",  # Fork bomb
]

# Dangerous patterns blocked in read-only mode (regex)
DANGEROUS_PATTERNS = [
    r"\bsudo\b",
    r"rm\s+-rf\s+/",
    r">\s*/dev/",
    r"curl.*\|.*bash",
    r"wget.*\|.*sh",
]


class BashTool(Tool):
    """Tool for executing bash commands."""

    def __init__(self, config: dict, read_only_mode: bool = False) -> None:
        """
        Initialize bash tool.

        Args:
            config: Tool configuration
            read_only_mode: If True, blocks commands that can modify the system
        """
        self.config = config
        self.read_only_mode = read_only_mode
        self.timeout_seconds = config.get("timeout_seconds", 30)
        self.max_output_length = config.get("max_output_length", 10000)
        self.blocked_commands = config.get("blocked_commands", [])
        self.working_dir = Path(config.get("working_dir", "."))
        self.environment = config.get("environment", {})

        # Define tool
        self.definition = ToolDefinition(
            name="bash",
            description="Execute bash commands in a shell. Use this to run terminal commands, manage files, or perform system operations.",
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="The bash command to execute",
                    required=True,
                ),
            ],
            requires_approval=config.get("requires_approval", True),
            timeout_seconds=self.timeout_seconds,
            category="system",
        )

    async def execute(self, command: str) -> ToolResult:
        """
        Execute a bash command.

        Args:
            command: Command to execute

        Returns:
            ToolResult with stdout/stderr
        """
        # Check for dangerous commands in read-only mode
        is_dangerous, reason = self._is_dangerous_command(command)
        if is_dangerous:
            return ToolResult(success=False, error=f"Security: {reason}")

        # Validate command
        validation_error = self._validate_command(command)
        if validation_error:
            return ToolResult(success=False, error=validation_error)

        logger.info(f"Executing bash command: {command}")

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.working_dir,
                env={**self.environment},
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    error=f"Command timed out after {self.timeout_seconds} seconds",
                )

            # Decode output
            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # Truncate if too long
            if len(stdout_str) > self.max_output_length:
                stdout_str = (
                    stdout_str[: self.max_output_length]
                    + f"\n... (truncated, {len(stdout_str)} total bytes)"
                )

            if len(stderr_str) > self.max_output_length:
                stderr_str = (
                    stderr_str[: self.max_output_length]
                    + f"\n... (truncated, {len(stderr_str)} total bytes)"
                )

            # Build result
            output = ""
            if stdout_str:
                output += stdout_str
            if stderr_str:
                if output:
                    output += "\n--- stderr ---\n"
                output += stderr_str

            exit_code = process.returncode

            return ToolResult(
                success=exit_code == 0,
                data=output if output else "(no output)",
                error=None if exit_code == 0 else f"Command exited with code {exit_code}",
                metadata={"exit_code": exit_code},
            )

        except Exception as e:
            logger.error(f"Error executing bash command: {e}", exc_info=True)
            return ToolResult(success=False, error=f"Execution error: {e}")

    def _is_dangerous_command(self, command: str) -> tuple[bool, str]:
        """
        Check if command is dangerous in read-only mode.

        Args:
            command: Command to check

        Returns:
            Tuple of (is_dangerous, reason)
        """
        if not self.read_only_mode:
            return False, ""

        # Check exact command matches
        for dangerous in DANGEROUS_COMMANDS:
            # For special characters (like fork bomb), check if it's in the command string
            # For normal commands, check if it's a word in the command
            if dangerous in command:
                return True, f"Command '{dangerous}' not allowed in read-only mode"

        # Check dangerous patterns with regex
        for pattern in DANGEROUS_PATTERNS:
            if re.search(pattern, command):
                return True, f"Pattern matching '{pattern}' not allowed in read-only mode"

        # Check output redirection
        if " > " in command or " >> " in command:
            return True, "Output redirection not allowed in read-only mode"

        return False, ""

    def _validate_command(self, command: str) -> Optional[str]:
        """
        Validate command against blocked patterns.

        Args:
            command: Command to validate

        Returns:
            Error message if invalid, None if valid
        """
        # Check blocked commands
        for pattern in self.blocked_commands:
            if re.search(pattern, command):
                return f"Command blocked by pattern: {pattern}"

        return None
