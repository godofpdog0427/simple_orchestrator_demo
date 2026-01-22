"""Built-in logging hooks."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class LoggingHook(Hook):
    """
    Hook that logs all events to a file.

    Config options:
        log_file: Path to log file (default: .orchestrator/hooks.log)
        log_format: "text" or "json" (default: "text")
        include_metadata: Whether to log metadata (default: False)
    """

    priority = 10  # High priority to log everything

    def __init__(self, config: dict[str, Any]):
        """
        Initialize logging hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.log_file = config.get("log_file", ".orchestrator/hooks.log")
        self.log_format = config.get("log_format", "text")
        self.include_metadata = config.get("include_metadata", False)

        # Ensure log directory exists
        Path(self.log_file).parent.mkdir(parents=True, exist_ok=True)

    async def execute(self, context: HookContext) -> HookResult:
        """
        Log the event.

        Args:
            context: Hook context

        Returns:
            HookResult to continue execution
        """
        try:
            timestamp = datetime.now().isoformat()

            if self.log_format == "json":
                log_entry = {
                    "timestamp": timestamp,
                    "event": context.event,
                    "data": self._sanitize_data(context.data),
                }
                if self.include_metadata and context.metadata:
                    log_entry["metadata"] = context.metadata

                with open(self.log_file, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")

            else:  # text format
                data_str = self._format_data(context.data)
                log_line = f"[{timestamp}] Event: {context.event} | Data: {data_str}\n"

                with open(self.log_file, "a") as f:
                    f.write(log_line)

        except Exception as e:
            logger.error(f"Error in LoggingHook: {e}", exc_info=True)

        return HookResult(action="continue")

    def _sanitize_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize data for logging (remove sensitive info, make JSON-serializable).

        Args:
            data: Event data

        Returns:
            Sanitized data
        """
        sanitized = {}
        for key, value in data.items():
            # Skip non-serializable objects
            if hasattr(value, "__dict__"):
                sanitized[key] = str(value)
            else:
                try:
                    json.dumps(value)  # Test if serializable
                    sanitized[key] = value
                except (TypeError, ValueError):
                    sanitized[key] = str(value)

        return sanitized

    def _format_data(self, data: dict[str, Any]) -> str:
        """
        Format data for text logging.

        Args:
            data: Event data

        Returns:
            Formatted string
        """
        items = []
        for key, value in data.items():
            if hasattr(value, "__dict__"):
                items.append(f"{key}={value.__class__.__name__}")
            else:
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                items.append(f"{key}={value_str}")

        return ", ".join(items)


class StartupLoggingHook(Hook):
    """Hook that logs orchestrator startup."""

    priority = 10

    def __init__(self, config: dict[str, Any]):
        """Initialize startup logging hook."""
        self.config = config

    async def execute(self, context: HookContext) -> HookResult:
        """Log startup event."""
        logger.info("Orchestrator starting...")
        return HookResult(action="continue")


class LLMCallLoggingHook(Hook):
    """Hook that logs LLM API calls."""

    priority = 100

    def __init__(self, config: dict[str, Any]):
        """Initialize LLM logging hook."""
        self.config = config
        self.log_prompts = config.get("log_prompts", False)
        self.log_tokens = config.get("log_tokens", True)

    async def execute(self, context: HookContext) -> HookResult:
        """Log LLM call details."""
        data = context.data

        if context.event == "llm.before_call":
            msg_count = len(data.get("messages", []))
            tool_count = len(data.get("tools", []))
            logger.info(f"LLM call: {msg_count} messages, {tool_count} tools")

            if self.log_prompts:
                logger.debug(f"Messages: {data.get('messages')}")

        elif context.event == "llm.after_call":
            if self.log_tokens:
                token_count = data.get("token_count", "unknown")
                logger.info(f"LLM response: {token_count} tokens")

        return HookResult(action="continue")
