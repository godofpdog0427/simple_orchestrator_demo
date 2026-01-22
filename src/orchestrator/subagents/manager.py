"""Subagent manager for spawning and managing isolated child agents."""

import asyncio
import logging
from typing import Any, Optional

from orchestrator.subagents.models import (
    SubagentConstraints,
    SubagentContext,
    SubagentHandle,
    SubagentStatus,
)
from orchestrator.tasks.models import Task

logger = logging.getLogger(__name__)


class SubagentManager:
    """
    Manages spawning and lifecycle of subagents.

    Subagents are isolated child orchestrators with:
    - Limited context (only subtask info)
    - Resource constraints (tokens, time, tools)
    - Independent execution
    - Result propagation to parent
    """

    def __init__(self, config: dict, hook_engine: Optional[Any] = None) -> None:
        """
        Initialize subagent manager.

        Args:
            config: Subagent configuration
            hook_engine: Optional hook engine for event triggers
        """
        self.config = config
        self.hook_engine = hook_engine
        self._active_subagents: dict[str, SubagentHandle] = {}
        self._semaphore: Optional[asyncio.Semaphore] = None

        # Initialize semaphore for concurrency control
        max_concurrent = self.config.get("max_concurrent", 3)
        self._semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(f"SubagentManager initialized (max_concurrent={max_concurrent})")

    async def spawn(
        self,
        parent_task: Task,
        subtask: Task,
        context: dict[str, Any],
        constraints: Optional[SubagentConstraints] = None,
        orchestrator_factory: Optional[callable] = None,
    ) -> SubagentHandle:
        """
        Spawn isolated subagent for subtask execution.

        Args:
            parent_task: Parent task that spawned this subagent
            subtask: Subtask to execute
            context: Additional context data
            constraints: Resource constraints (uses defaults if None)
            orchestrator_factory: Factory function to create orchestrator instance

        Returns:
            SubagentHandle for monitoring and result retrieval

        Raises:
            ValueError: If subagent spawning disabled or invalid parameters
            RuntimeError: If max concurrent subagents exceeded
        """
        if not self.config.get("enabled", False):
            raise ValueError("Subagent system is disabled in configuration")

        # Use default constraints if not provided
        if constraints is None:
            default_constraints = self.config.get("default_constraints", {})
            constraints = SubagentConstraints(**default_constraints)

        # Create subagent context
        subagent_context = SubagentContext(
            task_id=subtask.id,
            task_title=subtask.title,
            task_description=subtask.description,
            parent_task_title=parent_task.title,
            constraints=constraints,
            skill=constraints.skill,
            context_data=context,
        )

        # Create handle
        handle = SubagentHandle(
            task_id=subtask.id,
            parent_task_id=parent_task.id,
            status=SubagentStatus.PENDING,
        )

        # Create future for async execution
        handle._future = asyncio.Future()

        # Register as active subagent
        self._active_subagents[subtask.id] = handle

        logger.info(
            f"Spawning subagent for task '{subtask.title}' "
            f"(parent: '{parent_task.title}', constraints: {constraints})"
        )

        # Trigger subagent.spawned hook
        if self.hook_engine:
            await self.hook_engine.trigger(
                event="subagent.spawned",
                data={
                    "parent_task": parent_task,
                    "subtask": subtask,
                    "constraints": constraints,
                },
            )

        # Execute subagent in background
        asyncio.create_task(
            self._execute_subagent(
                handle, subagent_context, orchestrator_factory
            )
        )

        return handle

    async def _execute_subagent(
        self,
        handle: SubagentHandle,
        context: SubagentContext,
        orchestrator_factory: Optional[callable],
    ) -> None:
        """
        Execute subagent with resource constraints.

        Args:
            handle: Subagent handle to update
            context: Subagent execution context
            orchestrator_factory: Factory to create orchestrator instance
        """
        # Acquire semaphore for concurrency control
        async with self._semaphore:
            handle.status = SubagentStatus.RUNNING

            try:
                # Create isolated orchestrator instance
                if orchestrator_factory is None:
                    raise ValueError("orchestrator_factory is required")

                # Build subagent config with constraints
                subagent_config = self._build_subagent_config(context.constraints)

                # Create subagent orchestrator
                subagent = orchestrator_factory(subagent_config)

                # Initialize subagent
                await subagent.initialize()

                logger.info(f"Subagent executing task: {context.task_title}")

                # Execute with timeout
                try:
                    result = await asyncio.wait_for(
                        self._run_subagent_task(subagent, context),
                        timeout=context.constraints.timeout_seconds,
                    )

                    # Mark as completed
                    handle.status = SubagentStatus.COMPLETED
                    handle.result = result
                    handle._future.set_result(result)

                    logger.info(
                        f"Subagent completed task '{context.task_title}' successfully"
                    )

                    # Trigger subagent.completed hook
                    if self.hook_engine:
                        await self.hook_engine.trigger(
                            event="subagent.completed",
                            data={
                                "task_id": context.task_id,
                                "result": result,
                            },
                        )

                except asyncio.TimeoutError:
                    error_msg = (
                        f"Subagent timeout after {context.constraints.timeout_seconds}s"
                    )
                    logger.error(f"Subagent timeout: {context.task_title}")

                    handle.status = SubagentStatus.TIMEOUT
                    handle.error = error_msg
                    handle._future.set_exception(asyncio.TimeoutError(error_msg))

                finally:
                    # Shutdown subagent
                    await subagent.shutdown()

            except Exception as e:
                error_msg = f"Subagent execution failed: {e}"
                logger.error(f"Subagent error: {error_msg}")

                handle.status = SubagentStatus.FAILED
                handle.error = error_msg
                handle._future.set_exception(e)

                # Trigger subagent.failed hook
                if self.hook_engine:
                    await self.hook_engine.trigger(
                        event="subagent.failed",
                        data={
                            "task_id": context.task_id,
                            "error": error_msg,
                        },
                    )

            finally:
                # Remove from active subagents
                if context.task_id in self._active_subagents:
                    del self._active_subagents[context.task_id]

    async def _run_subagent_task(
        self, subagent: Any, context: SubagentContext
    ) -> Any:
        """
        Run subagent task execution.

        Args:
            subagent: Orchestrator instance
            context: Subagent context

        Returns:
            Task execution result
        """
        # Build task input with context
        task_input = f"""Parent Task: {context.parent_task_title}

Current Subtask: {context.task_title}
{context.task_description}

Additional Context:
{self._format_context_data(context.context_data)}

Please complete this subtask and return the result."""

        # Process task input
        result = await subagent.process_input(task_input)
        return result

    def _build_subagent_config(self, constraints: SubagentConstraints) -> dict:
        """
        Build configuration for subagent orchestrator.

        Args:
            constraints: Resource constraints

        Returns:
            Configuration dictionary with applied constraints
        """
        import copy

        # Deep copy base config
        config = copy.deepcopy(self.config.get("base_config", {}))

        # Apply constraints
        if "llm" not in config:
            config["llm"] = {}
        if "anthropic" not in config["llm"]:
            config["llm"]["anthropic"] = {}

        config["llm"]["anthropic"]["max_tokens"] = constraints.max_tokens

        # Set max iterations
        if "orchestrator" not in config:
            config["orchestrator"] = {}
        config["orchestrator"]["max_iterations"] = constraints.max_iterations

        # Disable subagents for child (prevent deep nesting)
        config["subagents"] = {
            "enabled": constraints.max_concurrent_subagents > 0,
            "max_concurrent": constraints.max_concurrent_subagents,
        }

        # Restrict tools
        if constraints.allowed_tools:
            if "tools" not in config:
                config["tools"] = {}

            # Disable all tools first
            for tool_name in [
                "bash",
                "file_read",
                "file_write",
                "file_delete",
                "todo_list",
                "task_decompose",
            ]:
                if tool_name not in config["tools"]:
                    config["tools"][tool_name] = {}
                config["tools"][tool_name]["enabled"] = (
                    tool_name in constraints.allowed_tools
                )

        return config

    def _format_context_data(self, context_data: dict[str, Any]) -> str:
        """
        Format context data for display.

        Args:
            context_data: Context dictionary

        Returns:
            Formatted string
        """
        if not context_data:
            return "(none)"

        lines = []
        for key, value in context_data.items():
            lines.append(f"- {key}: {value}")

        return "\n".join(lines)

    async def wait_for(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """
        Wait for a subagent to complete.

        Args:
            task_id: Task ID of subagent
            timeout: Optional timeout in seconds

        Returns:
            Subagent result

        Raises:
            ValueError: If subagent not found
            asyncio.TimeoutError: If timeout exceeded
        """
        if task_id not in self._active_subagents:
            raise ValueError(f"No active subagent for task: {task_id}")

        handle = self._active_subagents[task_id]
        return await handle.wait(timeout=timeout)

    def get_active_count(self) -> int:
        """
        Get number of currently active subagents.

        Returns:
            Count of active subagents
        """
        return len(self._active_subagents)

    def get_handle(self, task_id: str) -> Optional[SubagentHandle]:
        """
        Get subagent handle by task ID.

        Args:
            task_id: Task ID

        Returns:
            SubagentHandle if found, None otherwise
        """
        return self._active_subagents.get(task_id)

    def list_active(self) -> list[SubagentHandle]:
        """
        List all active subagent handles.

        Returns:
            List of active SubagentHandle objects
        """
        return list(self._active_subagents.values())

    async def shutdown(self) -> None:
        """Shutdown manager and cancel all active subagents."""
        logger.info("Shutting down SubagentManager...")

        # Cancel all active subagents
        for handle in list(self._active_subagents.values()):
            if not handle.is_done():
                handle.status = SubagentStatus.CANCELLED
                handle.error = "Cancelled by manager shutdown"
                if handle._future and not handle._future.done():
                    handle._future.cancel()

        self._active_subagents.clear()
        logger.info("SubagentManager shutdown complete")
