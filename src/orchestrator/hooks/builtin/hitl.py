"""Built-in Human-in-the-Loop (HITL) hooks."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Optional

from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class HITLHook(Hook):
    """
    Hook that prompts user for approval on critical operations.

    Triggers on: tool.requires_approval event

    Config options:
        timeout: Approval timeout in seconds (default: 300)
        auto_approve_safe_tools: Auto-approve tools with requires_approval=False (default: True)
        prompt_format: Custom prompt format (default: standard)
    """

    priority = 50  # Medium priority, after logging but before metrics

    def __init__(self, config: dict[str, Any], workspace: Optional[Any] = None):
        """
        Initialize HITL hook.

        Args:
            config: Hook configuration
            workspace: Optional workspace reference for approval whitelist (Phase 6D)
        """
        self.config = config
        self.timeout = config.get("timeout", 300)
        self.auto_approve_safe_tools = config.get("auto_approve_safe_tools", True)
        self.prompt_format = config.get("prompt_format", "standard")
        self.workspace = workspace  # NEW (Phase 6D): Workspace reference for whitelist

    async def execute(self, context: HookContext) -> HookResult:
        """
        Prompt user for approval.

        Context data should contain:
            - tool_name: str - Name of the tool
            - tool_input: dict - Tool input parameters
            - requires_approval: bool - Whether tool requires approval

        Args:
            context: Hook context

        Returns:
            HookResult: continue if approved, block if denied
        """
        data = context.data
        tool_name = data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})
        requires_approval = data.get("requires_approval", False)

        # Auto-approve tools that don't require approval
        if self.auto_approve_safe_tools and not requires_approval:
            logger.debug(f"Auto-approving safe tool: {tool_name}")
            return HookResult(action="continue")

        # NEW (Phase 6D): Check approval whitelist
        if self._is_whitelisted(tool_name):
            logger.info(f"Auto-approved (whitelisted): {tool_name}")
            return HookResult(
                action="continue",
                metadata={"approval_source": "whitelist"}
            )

        # Prompt user for approval (with "always" option)
        try:
            approval_type = await self._prompt_user_enhanced(
                tool_name, tool_input, context.orchestrator_state
            )

            if approval_type in ["yes", "always"]:
                # Add to whitelist if "always"
                if approval_type == "always":
                    self._add_to_whitelist(tool_name)

                logger.info(f"User approved tool execution: {tool_name}")
                return HookResult(action="continue")
            else:
                reason = f"User denied approval for tool '{tool_name}'"
                logger.info(reason)
                return HookResult(action="block", reason=reason)

        except asyncio.TimeoutError:
            reason = f"Approval timeout ({self.timeout}s) for tool '{tool_name}'"
            logger.warning(reason)
            return HookResult(action="block", reason=reason)

        except Exception as e:
            reason = f"Error during approval prompt: {e}"
            logger.error(reason, exc_info=True)
            return HookResult(action="block", reason=reason)

    async def _prompt_user(self, tool_name: str, tool_input: dict[str, Any]) -> bool:
        """
        Prompt user for approval via console.

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters

        Returns:
            bool: True if approved, False if denied

        Raises:
            asyncio.TimeoutError: If prompt times out
        """
        # Format prompt
        prompt_text = self._format_prompt(tool_name, tool_input)

        # Run prompt in executor to avoid blocking
        loop = asyncio.get_event_loop()

        async def get_input():
            return await loop.run_in_executor(None, input, prompt_text)

        # Wait for user input with timeout
        try:
            response = await asyncio.wait_for(get_input(), timeout=self.timeout)
            return response.strip().lower() in ["y", "yes"]
        except asyncio.TimeoutError:
            print("\n[Timeout - request denied]")
            raise

    def _format_prompt(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """
        Format approval prompt.

        Args:
            tool_name: Tool name
            tool_input: Tool input

        Returns:
            Formatted prompt string
        """
        if self.prompt_format == "detailed":
            lines = [
                "\n" + "=" * 60,
                "APPROVAL REQUIRED",
                "=" * 60,
                f"Tool: {tool_name}",
                "Parameters:",
            ]
            for key, value in tool_input.items():
                # Truncate long values
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:97] + "..."
                lines.append(f"  {key}: {value_str}")
            lines.append("=" * 60)
            lines.append("Approve? [y/N]: ")
            return "\n".join(lines)

        else:  # standard format
            # Format tool input concisely
            input_str = self._format_input_brief(tool_input)
            return f"\n⚠️  Tool '{tool_name}' requires approval\n   Input: {input_str}\n   Approve? [y/N]: "

    def _format_input_brief(self, tool_input: dict[str, Any]) -> str:
        """
        Format tool input briefly for prompt.

        Args:
            tool_input: Tool input parameters

        Returns:
            Brief formatted string
        """
        if not tool_input:
            return "{}"

        items = []
        for key, value in tool_input.items():
            value_str = str(value)
            # Truncate long values
            if len(value_str) > 50:
                value_str = value_str[:47] + "..."
            items.append(f"{key}={value_str}")

        return "{" + ", ".join(items) + "}"

    async def _prompt_user_enhanced(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        orchestrator_state: Optional[Any] = None,
    ) -> str:
        """
        Prompt user for approval with 'always' option (Phase 6D).

        Args:
            tool_name: Name of the tool
            tool_input: Tool input parameters
            orchestrator_state: Optional orchestrator reference (for display control)

        Returns:
            str: "yes", "no", or "always"

        Raises:
            asyncio.TimeoutError: If prompt times out
        """
        # Phase 7B: Stop activity indicator before showing prompt
        if orchestrator_state and hasattr(orchestrator_state, 'display_manager'):
            display = orchestrator_state.display_manager
            if hasattr(display, 'stop_activity'):
                display.stop_activity()

        # Format prompt with three options
        input_str = self._format_input_brief(tool_input)
        prompt_text = (
            f"\n⚠️  Tool '{tool_name}' requires approval\n"
            f"   Input: {input_str}\n"
            f"   Approve? [y/n/always]: "
        )

        # Run prompt in executor to avoid blocking
        loop = asyncio.get_event_loop()

        async def get_input():
            return await loop.run_in_executor(None, input, prompt_text)

        # Wait for user input with timeout
        try:
            response = await asyncio.wait_for(get_input(), timeout=self.timeout)
            response = response.strip().lower()

            if response in ["y", "yes"]:
                return "yes"
            elif response in ["a", "always"]:
                return "always"
            else:
                return "no"

        except asyncio.TimeoutError:
            print("\n[Timeout - request denied]")
            raise

    def _is_whitelisted(self, tool_name: str) -> bool:
        """
        Check if tool is in approval whitelist (Phase 6D).

        Args:
            tool_name: Name of the tool to check

        Returns:
            bool: True if whitelisted, False otherwise
        """
        if not self.workspace:
            return False

        whitelist = self.workspace.user_preferences.get("approval_whitelist", {})
        tools = whitelist.get("tools", [])

        return any(entry["tool_name"] == tool_name for entry in tools)

    def _add_to_whitelist(self, tool_name: str) -> None:
        """
        Add tool to approval whitelist (Phase 6D).

        Args:
            tool_name: Name of the tool to whitelist
        """
        if not self.workspace:
            logger.warning("Cannot add to whitelist: no workspace reference")
            return

        # Initialize whitelist structure if needed
        if "approval_whitelist" not in self.workspace.user_preferences:
            self.workspace.user_preferences["approval_whitelist"] = {"tools": []}

        whitelist = self.workspace.user_preferences["approval_whitelist"]

        # Check if already whitelisted (avoid duplicates)
        if self._is_whitelisted(tool_name):
            return

        # Add entry
        whitelist["tools"].append({
            "tool_name": tool_name,
            "approved_at": datetime.now().isoformat(),
            "match_type": "tool_name_only"
        })

        logger.info(f"✓ {tool_name} whitelisted for this session")
        print(f"\n✓ {tool_name} whitelisted for this session\n")

    def should_run(self, context: HookContext) -> bool:
        """
        Check if hook should run for this context.

        Only run for tool.requires_approval event.

        Args:
            context: Hook context

        Returns:
            bool: True if should run
        """
        return context.event == "tool.requires_approval"
