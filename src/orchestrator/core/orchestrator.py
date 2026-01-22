"""Core orchestrator implementation."""

import asyncio
import logging
import sys
from datetime import datetime
from typing import Any, Optional, TYPE_CHECKING

from orchestrator.tasks.models import Task, TaskStatus

if TYPE_CHECKING:
    from orchestrator.modes.models import ExecutionMode

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main orchestrator class for managing tasks and LLM interactions."""

    def __init__(self, config: dict) -> None:
        """
        Initialize the orchestrator.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.should_stop = False
        self.current_task: Optional[Task] = None

        # Components will be initialized in initialize()
        self.llm_client: Optional[Any] = None
        self.tool_registry: Optional[Any] = None
        self.task_manager: Optional[Any] = None
        self.hook_engine: Optional[Any] = None
        self.skill_registry: Optional[Any] = None  # Phase 4A
        self.subagent_manager: Optional[Any] = None  # Phase 4B
        self.cache_manager: Optional[Any] = None  # Phase 5A
        self.display_manager: Optional[Any] = None  # Phase 2.6 streaming display
        self.workspace_manager: Optional[Any] = None  # Phase 5B workspace
        self.workspace: Optional[Any] = None  # Phase 5B workspace state
        self.summarizer: Optional[Any] = None  # Phase 5B task summarizer
        self.mode_manager: Optional[Any] = None  # Phase 6A execution mode
        self.interrupt_controller: Optional[Any] = None  # Phase 7 interrupt handling

        # Setup logging
        self._setup_logging()

    def _setup_logging(self) -> None:
        """Setup logging based on configuration."""
        from pathlib import Path

        log_config = self.config.get("logging", {})
        log_level = log_config.get("level", "INFO")
        log_file = log_config.get("file", "./.orchestrator/logs/orchestrator.log")

        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Configure logger
        logging.basicConfig(
            level=getattr(logging, log_level),
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler() if log_config.get("console", True) else logging.NullHandler(),
            ],
        )

    def _resolve_relative_paths_in_config(self) -> None:
        """
        Convert relative paths in config to absolute paths.

        This is necessary because we change working directory to workspace,
        but config paths are relative to project root.

        Must be called BEFORE changing working directory.
        """
        from pathlib import Path

        # Helper function to resolve path
        def resolve_path(path_str: str) -> str:
            path = Path(path_str)
            if not path.is_absolute():
                return str((Path(self.original_cwd) / path).resolve())
            return path_str

        # Resolve hooks config_file
        if "hooks" in self.config and "config_file" in self.config["hooks"]:
            self.config["hooks"]["config_file"] = resolve_path(
                self.config["hooks"]["config_file"]
            )
            logger.debug(f"Resolved hook config_file: {self.config['hooks']['config_file']}")

        # Resolve logging file
        if "logging" in self.config and "file" in self.config["logging"]:
            self.config["logging"]["file"] = resolve_path(
                self.config["logging"]["file"]
            )
            logger.debug(f"Resolved logging file: {self.config['logging']['file']}")

        # Resolve persistence state_file
        if "persistence" in self.config and "state_file" in self.config["persistence"]:
            self.config["persistence"]["state_file"] = resolve_path(
                self.config["persistence"]["state_file"]
            )
            logger.debug(f"Resolved persistence state_file: {self.config['persistence']['state_file']}")

        # Resolve skills paths
        if "skills" in self.config:
            if "builtin_path" in self.config["skills"]:
                self.config["skills"]["builtin_path"] = resolve_path(
                    self.config["skills"]["builtin_path"]
                )
                logger.debug(f"Resolved skills builtin_path: {self.config['skills']['builtin_path']}")

            if "user_path" in self.config["skills"]:
                self.config["skills"]["user_path"] = resolve_path(
                    self.config["skills"]["user_path"]
                )
                logger.debug(f"Resolved skills user_path: {self.config['skills']['user_path']}")

        # Resolve workspace directory (Phase 5B)
        if "workspace" in self.config and "workspace_dir" in self.config["workspace"]:
            self.config["workspace"]["workspace_dir"] = resolve_path(
                self.config["workspace"]["workspace_dir"]
            )
            logger.debug(f"Resolved workspace workspace_dir: {self.config['workspace']['workspace_dir']}")

    async def initialize(self) -> None:
        """Initialize orchestrator components."""
        logger.info("Initializing orchestrator...")

        # Import here to avoid circular imports
        import os
        from pathlib import Path

        from orchestrator.cache.manager import CacheManager, set_cache_manager
        from orchestrator.hooks.engine import HookEngine
        from orchestrator.llm.client import LLMClient
        from orchestrator.skills.registry import SkillRegistry
        from orchestrator.subagents.manager import SubagentManager
        from orchestrator.tasks.manager import TaskManager
        from orchestrator.tools.registry import ToolRegistry

        # Setup isolated working directory (Phase 3.5)
        orchestrator_config = self.config.get("orchestrator", {})
        working_dir = orchestrator_config.get("working_directory", "./.orchestrator/workspace")
        working_dir_path = Path(working_dir).resolve()
        working_dir_path.mkdir(parents=True, exist_ok=True)

        # Store original directory for reference
        self.original_cwd = os.getcwd()

        # Convert relative paths to absolute BEFORE changing directory (Hotfix)
        # This fixes paths in config that are relative to project root
        self._resolve_relative_paths_in_config()

        # Change to workspace
        os.chdir(working_dir_path)
        logger.info(f"Working directory: {working_dir_path}")
        logger.info(f"Original directory: {self.original_cwd}")

        # Initialize cache manager (Phase 5)
        cache_config = self.config.get("cache", {})
        self.cache_manager = CacheManager(cache_config)
        set_cache_manager(self.cache_manager)  # Set global instance

        # Initialize display manager (Phase 5B/5C)
        # Priority: Streaming > Live > Panel
        # Create display manager based on config
        from orchestrator.display import get_display_manager, set_display_manager, DisplayManager

        cli_config = self.config.get("cli", {})
        use_streaming = cli_config.get("use_streaming_display", False)
        use_live_display = cli_config.get("use_live_display", False)

        # Check if display manager was already set externally (e.g., by CLI)
        # Note: get_display_manager() auto-creates DisplayManager, so check type
        existing_manager = get_display_manager()
        is_default_manager = type(existing_manager).__name__ == "DisplayManager"

        if not is_default_manager:
            # Use externally set display manager
            self.display_manager = existing_manager
            logger.info(f"Using existing display manager: {type(self.display_manager).__name__}")
        elif use_streaming:
            from orchestrator.display_stream import StreamingDisplayManager
            # Get activity indicator settings (Phase 7B/7C)
            activity_config = cli_config.get("activity_indicator", {})
            self.display_manager = StreamingDisplayManager(
                activity_enabled=activity_config.get("enabled", True),
                spinner_style=activity_config.get("spinner_style", "dots"),
                spinner_color=activity_config.get("color", "cyan"),
                warning_delay=activity_config.get("warning_delay", 10.0),
                warning_interval=activity_config.get("warning_interval", 15.0),
            )
            set_display_manager(self.display_manager)
            logger.info("Created StreamingDisplayManager")
        elif use_live_display:
            from orchestrator.display_live import LiveDisplayManager
            self.display_manager = LiveDisplayManager()
            set_display_manager(self.display_manager)
            logger.info("Created LiveDisplayManager")
        else:
            # Use default DisplayManager (already created by get_display_manager)
            self.display_manager = existing_manager
            logger.info("Created DisplayManager (panel mode)")

        # Initialize hook engine first
        hook_config = self.config.get("hooks", {})
        self.hook_engine = HookEngine(hook_config)
        await self.hook_engine.initialize()

        # Trigger orchestrator.start event
        await self._trigger_hook("orchestrator.start", {"config": self.config})

        # Initialize LLM client
        llm_config = self.config.get("llm", {})
        self.llm_client = LLMClient(llm_config)

        # Initialize tool registry
        tool_config = self.config.get("tools", {})
        self.tool_registry = ToolRegistry(tool_config)
        await self.tool_registry.initialize()

        # Initialize task manager
        task_config = self.config.get("tasks", {})
        self.task_manager = TaskManager(task_config)

        # Initialize skill registry (Phase 4A)
        skill_config = self.config.get("skills", {})
        self.skill_registry = SkillRegistry(skill_config)
        await self.skill_registry.initialize()

        # Initialize mode manager (Phase 6A)
        from orchestrator.modes.manager import ModeManager
        from orchestrator.modes.models import ExecutionMode

        default_mode_str = self.config.get("mode", "execute")
        default_mode = ExecutionMode(default_mode_str)
        self.mode_manager = ModeManager(initial_mode=default_mode)
        logger.info(f"Mode manager initialized in {default_mode.value} mode")

        # Update bash tool with read-only mode based on current mode (Phase 6A++)
        bash_tool = self.tool_registry.get("bash")
        if bash_tool:
            read_only = default_mode in [ExecutionMode.ASK, ExecutionMode.PLAN]
            bash_tool.read_only_mode = read_only
            logger.info(f"Bash tool read_only_mode set to {read_only} for {default_mode.value} mode")

        # Initialize subagent manager (Phase 4B)
        subagent_config = self.config.get("subagents", {})
        # Pass base config for subagent orchestrators
        subagent_config["base_config"] = self.config
        self.subagent_manager = SubagentManager(subagent_config, hook_engine=self.hook_engine)

        # Register subagent spawn tool if enabled (Phase 4B)
        if subagent_config.get("enabled", False):
            from orchestrator.tools.builtin.subagent_spawn import SubagentSpawnTool

            subagent_tool = SubagentSpawnTool(
                subagent_manager=self.subagent_manager,
                task_manager=self.task_manager,
                orchestrator_factory=self._create_orchestrator_instance,
            )
            self.tool_registry.register(subagent_tool)

        # Initialize workspace manager and state (Phase 5B)
        # Phase 8: Session Registry integration
        workspace_config = self.config.get("workspace", {})
        if workspace_config.get("enabled", True):
            from orchestrator.workspace.state import WorkspaceManager
            from orchestrator.workspace.session import SessionRegistry
            from orchestrator.workspace.summarizer import TaskSummarizer

            workspace_dir = workspace_config.get("workspace_dir", ".orchestrator/workspace_state")
            registry_file = workspace_config.get("session_registry", ".orchestrator/sessions.json")

            self.workspace_manager = WorkspaceManager(workspace_dir)
            self.session_registry = SessionRegistry(registry_file)

            # Determine session_id based on config options (Phase 8)
            session_id = self._resolve_session_id()

            # Load or create workspace for this session
            self.workspace = self.workspace_manager.load_or_create(session_id)
            self.current_session = self.session_registry.get_session(session_id)

            # Initialize task summarizer
            self.summarizer = TaskSummarizer(self.llm_client)

            # Update session stats
            self.session_registry.update_session_stats(
                session_id,
                message_count=len(self.workspace.workspace_conversation),
                task_count=len(self.workspace.task_summaries),
            )

            logger.info(f"Loaded workspace: {session_id}")
            if self.current_session:
                logger.info(f"Session: {self.current_session.name}")
            logger.info(f"Workspace has {len(self.workspace.task_summaries)} task summaries")

            # NEW (Phase 6D): Inject workspace into HITLHook for approval whitelist
            self._inject_workspace_to_hitl_hook()

        logger.info("Orchestrator initialized successfully")

    async def shutdown(self) -> None:
        """Shutdown orchestrator and cleanup resources."""
        import os

        logger.info("Shutting down orchestrator...")
        self.should_stop = True

        # Trigger orchestrator.stop event
        await self._trigger_hook("orchestrator.stop", {"final_state": {"should_stop": self.should_stop}})

        # Save workspace before shutdown (Phase 5B)
        if self.workspace_manager and self.workspace:
            self.workspace_manager.save(self.workspace)
            logger.info(f"Workspace saved: {self.workspace.session_id}")

            # Phase 8: Update session stats
            if hasattr(self, 'session_registry') and self.session_registry:
                self.session_registry.update_session_stats(
                    self.workspace.session_id,
                    message_count=len(self.workspace.workspace_conversation),
                    task_count=len(self.workspace.task_summaries),
                )

        # Shutdown subagent manager (Phase 4B)
        if self.subagent_manager:
            await self.subagent_manager.shutdown()

        # Cleanup components
        if self.task_manager:
            await self.task_manager.save_state()

        # Restore original working directory (Phase 3.5)
        if hasattr(self, "original_cwd"):
            os.chdir(self.original_cwd)
            logger.info(f"Restored working directory: {self.original_cwd}")

        logger.info("Orchestrator shutdown complete")

    def _inject_workspace_to_hitl_hook(self) -> None:
        """
        Inject workspace reference into HITLHook instances (Phase 6D).

        This allows HITLHook to access and persist approval whitelist.
        """
        if not self.workspace or not self.hook_engine:
            return

        # Import HITLHook to check instance type
        from orchestrator.hooks.builtin.hitl import HITLHook

        # Find HITLHook instances and inject workspace
        for hooks in self.hook_engine.hooks.values():
            for hook in hooks:
                if isinstance(hook, HITLHook):
                    hook.workspace = self.workspace
                    logger.debug("Injected workspace into HITLHook for approval whitelist")

    def _resolve_session_id(self) -> str:
        """
        Resolve session_id based on config options (Phase 8).

        Priority:
        1. Explicit session_id in config
        2. resume_session=True -> most recent session
        3. new_session=True -> create new session with auto-generated name
        4. Default: create new session (backward compatible)

        Returns:
            Session UUID
        """
        from datetime import datetime

        # 1. Explicit session_id provided
        session_id = self.config.get("session_id")
        if session_id:
            # Ensure it's registered (for backward compatibility with existing workspaces)
            if not self.session_registry.session_exists(session_id):
                # Check if workspace file exists (migrating from pre-Phase 8)
                if self.workspace_manager.exists(session_id):
                    # Auto-register existing workspace
                    stats = self.workspace_manager.get_stats(session_id)
                    self.session_registry.create_session(
                        name=f"Migrated Session",
                        description="Auto-migrated from existing workspace",
                        session_id=session_id,
                    )
                    if stats:
                        self.session_registry.update_session_stats(session_id, *stats)
            return session_id

        # 2. Resume most recent session
        resume_session = self.config.get("resume_session", False)
        if resume_session:
            sessions = self.session_registry.list_sessions(limit=1)
            if sessions:
                logger.info(f"Resuming session: {sessions[0].name}")
                return sessions[0].id

        # 3. Create new session
        session_name = self.config.get("session_name")
        if not session_name:
            # Auto-generate name with timestamp
            session_name = f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        session_description = self.config.get("session_description", "")
        session = self.session_registry.create_session(
            name=session_name,
            description=session_description,
        )
        return session.id

    def _create_orchestrator_instance(self, config: dict) -> "Orchestrator":
        """
        Factory method to create orchestrator instance for subagents.

        This is used by SubagentManager to spawn isolated child orchestrators.

        Args:
            config: Configuration for the new orchestrator instance

        Returns:
            New Orchestrator instance
        """
        return Orchestrator(config)

    def set_mode(self, mode: "ExecutionMode") -> None:
        """
        Change execution mode (Phase 6A).

        Args:
            mode: The new execution mode
        """
        if not self.mode_manager:
            raise RuntimeError("Mode manager not initialized")

        self.mode_manager.set_mode(mode)
        logger.info(f"Switched to {mode.value} mode")

        # Update bash tool read-only mode (Phase 6A++)
        bash_tool = self.tool_registry.get("bash")
        if bash_tool:
            from orchestrator.modes.models import ExecutionMode
            read_only = mode in [ExecutionMode.ASK, ExecutionMode.PLAN]
            bash_tool.read_only_mode = read_only
            logger.info(f"Bash tool read_only_mode updated to {read_only} for {mode.value} mode")

    async def run(self) -> None:
        """
        Main orchestrator execution loop.

        This is the core loop that:
        1. Gets next task
        2. Executes task
        3. Repeats until stopped
        """
        await self.initialize()

        try:
            while not self.should_stop:
                # Get next executable task
                task = await self.task_manager.get_next_executable_task()

                if not task:
                    logger.debug("No executable tasks, waiting...")
                    break

                # Execute task
                await self._execute_task(task)

        except Exception as e:
            logger.error(f"Error in orchestrator loop: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()

    async def process_input(self, user_input: str) -> str:
        """
        Process user input in interactive mode based on execution mode.

        Args:
            user_input: User's input string

        Returns:
            Response string
        """
        from orchestrator.modes.models import ExecutionMode

        try:
            # Get current mode (default to EXECUTE if mode manager not initialized)
            current_mode = (
                self.mode_manager.current_mode
                if self.mode_manager
                else ExecutionMode.EXECUTE
            )

            # Dispatch to mode-specific handler
            if current_mode == ExecutionMode.ASK:
                return await self._process_ask_mode(user_input)
            elif current_mode == ExecutionMode.PLAN:
                return await self._process_plan_mode(user_input)
            else:
                return await self._process_execute_mode(user_input)

        except Exception as e:
            logger.error(f"Error processing input: {e}", exc_info=True)
            return f"Error: {e}"

    async def _process_ask_mode(self, user_input: str) -> str:
        """
        Process input in ASK mode - Q&A without task persistence.

        Args:
            user_input: User's question

        Returns:
            Answer to the question
        """
        logger.info("Processing in ASK mode (Q&A)")

        # Create temporary task (not persisted to TaskManager)
        temp_task = Task(
            title=user_input[:100],
            description=user_input,
            status=TaskStatus.IN_PROGRESS,
        )

        # Build context and execute reasoning loop
        context = self._build_context(temp_task)
        result = await self._reasoning_loop(temp_task, context)

        return result or "I've processed your question."

    async def _process_plan_mode(self, user_input: str) -> str:
        """
        Process input in PLAN mode - Create plan without execution.

        Args:
            user_input: Planning request

        Returns:
            Plan summary with tasks and todos
        """
        logger.info("Processing in PLAN mode (Planning)")

        # Create planning task
        planning_task = Task(
            title=f"[PLAN] {user_input[:80]}",
            description=user_input,
            status=TaskStatus.PENDING,
        )

        # Add to TaskManager for persistence
        planning_task = await self.task_manager.create_task(planning_task)
        logger.info(f"Created planning task: {planning_task.id}")

        # Execute planning task (LLM may call task_decompose to create subtasks)
        await self._execute_task(planning_task)

        # Get updated task with results
        updated_task = await self.task_manager.get_task(planning_task.id)

        # Build and return plan summary
        if updated_task:
            summary = await self._build_plan_summary(updated_task)
            return summary
        else:
            return "Planning task completed but could not retrieve results."

    async def _process_execute_mode(self, user_input: str) -> str:
        """
        Process input in EXECUTE mode - Execute tasks.

        Args:
            user_input: Execution request

        Returns:
            Execution results
        """
        logger.info("Processing in EXECUTE mode (Execution)")

        # Check for pending tasks from PLAN mode
        pending_tasks = await self.task_manager.list_tasks(status=TaskStatus.PENDING)

        # Check if user wants to execute pending tasks
        execute_keywords = ["execute", "start", "run", "開始", "執行", "运行"]
        should_execute_pending = any(
            keyword in user_input.lower() for keyword in execute_keywords
        )

        if pending_tasks and should_execute_pending:
            # Execute all pending tasks
            logger.info(f"Executing {len(pending_tasks)} pending tasks")
            return await self._execute_all_pending_tasks()
        else:
            # Create and execute new task directly
            task = Task(
                title=user_input[:100],
                description=user_input,
                status=TaskStatus.PENDING,
            )

            task = await self.task_manager.create_task(task)
            logger.info(f"Created task: {task.id}")

            # Execute task
            await self._execute_task(task)

            # Execute subtasks if any were created
            await self._execute_subtasks_recursive(task.id)

            # Get final result
            updated_task = await self.task_manager.get_task(task.id)

            if updated_task and updated_task.status == TaskStatus.COMPLETED:
                return updated_task.result or "Task completed successfully"
            elif updated_task and updated_task.status == TaskStatus.FAILED:
                return f"Task failed: {updated_task.error}"
            else:
                return "Task execution status unknown"

    async def _execute_task(self, task: Task) -> None:
        """
        Execute a single task.

        Args:
            task: Task to execute
        """
        logger.info(f"Executing task: {task.id} - {task.title}")

        try:
            # Update task status
            await self.task_manager.update_task(task.id, {"status": TaskStatus.IN_PROGRESS})
            self.current_task = task

            # Trigger task.started event
            hook_result = await self._trigger_hook("task.started", {"task": task})
            if hook_result.action == "block":
                raise RuntimeError(f"Task blocked by hook: {hook_result.reason}")

            # Build context for LLM
            context = self._build_context(task)

            # Execute reasoning loop
            result = await self._reasoning_loop(task, context)

            # Update task with result
            await self.task_manager.update_task(
                task.id, {"status": TaskStatus.COMPLETED, "result": result}
            )

            # Trigger task.completed event
            await self._trigger_hook("task.completed", {"task": task, "result": result})

            # Phase 5B: Generate summary and add to workspace
            if self.workspace and self.summarizer:
                try:
                    from orchestrator.workspace.state import TaskSummary

                    # Generate summary
                    summary_text = await self.summarizer.generate_summary(
                        task, context.get("conversation_history", [])
                    )

                    # Extract tools used
                    tools_used = self.summarizer._extract_tools_used(
                        context.get("conversation_history", [])
                    )

                    # Create task summary
                    task_summary = TaskSummary(
                        task_id=task.id,
                        task_description=task.description or task.title,
                        timestamp=datetime.now(),
                        summary=summary_text,
                        key_results=[str(result)[:200]] if result else [],
                        tools_used=tools_used,
                        status="COMPLETED",
                    )

                    # Add to workspace
                    self.workspace.add_task_summary(task_summary)

                    # Save workspace after each task
                    self.workspace_manager.save(self.workspace)

                    logger.debug(f"Added task summary to workspace: {task.id}")
                except Exception as e:
                    logger.error(f"Error generating task summary: {e}", exc_info=True)
                    # Continue despite summary error

            # Phase 3: Handle task completion for dependencies and hierarchy
            await self._handle_task_completion(task.id)

            logger.info(f"Task completed: {task.id}")

        except Exception as e:
            logger.error(f"Task failed: {task.id} - {e}", exc_info=True)
            await self.task_manager.update_task(
                task.id, {"status": TaskStatus.FAILED, "error": str(e)}
            )

            # Trigger task.failed event
            await self._trigger_hook("task.failed", {"task": task, "error": str(e)})

            raise

    def _build_context(self, task: Task) -> dict[str, Any]:
        """
        Build context for LLM based on task.

        Args:
            task: Task to build context for

        Returns:
            Context dictionary
        """
        # Get all tool schemas
        all_tool_schemas = self.tool_registry.get_tool_schemas() if self.tool_registry else []

        # Phase 6A: Filter tools based on execution mode
        if self.mode_manager:
            tool_schemas = self.mode_manager.filter_tool_schemas(all_tool_schemas)
        else:
            tool_schemas = all_tool_schemas

        context = {
            "task": task,
            "task_description": task.description or task.title,  # Phase 4A: for skill matching
            "tools": tool_schemas,
            "conversation_history": [],
            "workspace_context": None,  # Phase 5B: Workspace context
        }

        # Phase 5B: Inject workspace context
        if self.workspace:
            context["workspace_context"] = self._get_workspace_context(task)

        return context

    def _get_workspace_context(self, task: Task) -> str:
        """
        Extract relevant context from workspace for current task.

        Args:
            task: Current task

        Returns:
            Formatted workspace context string
        """
        context_parts = []

        # 1. Recent task summaries (last 3 tasks)
        recent_summaries = list(self.workspace.task_summaries)[-3:]
        if recent_summaries:
            context_parts.append("## Recent Tasks:")
            for ts in recent_summaries:
                context_parts.append(
                    f"- [{ts.timestamp.strftime('%H:%M')}] {ts.task_description}\n"
                    f"  Summary: {ts.summary}\n"
                    f"  Status: {ts.status}"
                )

        # 2. Keyword search in summaries (first 5 words of task description)
        task_desc = task.description or task.title
        keywords = task_desc.split()[:5]
        related_summaries = self.workspace.search_summaries(keywords)
        if related_summaries:
            context_parts.append("\n## Related Past Tasks:")
            for ts in related_summaries[:2]:  # Top 2 related
                context_parts.append(
                    f"- {ts.task_description}\n"
                    f"  Summary: {ts.summary}"
                )

        # 3. Recent workspace conversation (last 10 messages)
        recent_conversation = self.workspace.get_recent_context(max_messages=10)
        if recent_conversation:
            context_parts.append("\n## Recent Conversation:")
            for msg in recent_conversation:
                role_label = "User" if msg.role == "user" else "Assistant"
                content = msg.content if isinstance(msg.content, str) else "[Tool use]"
                context_parts.append(f"{role_label}: {content[:200]}...")

        return "\n".join(context_parts) if context_parts else ""

    async def _build_plan_summary(self, planning_task: Task) -> str:
        """
        Build a summary of the planning task with subtasks and todos.

        Args:
            planning_task: The completed planning task

        Returns:
            Formatted plan summary
        """
        summary_parts = []
        summary_parts.append(f"Plan: {planning_task.title}")
        summary_parts.append("=" * 60)

        # Get subtasks created by task_decompose
        # Note: Removed todo_list display as it's no longer used in PLAN mode
        subtasks = await self.task_manager.list_tasks(parent_id=planning_task.id)
        if subtasks:
            summary_parts.append(f"\n🔨 Subtasks Created ({len(subtasks)}):")
            for i, subtask in enumerate(subtasks, 1):
                deps = (
                    f" [depends on: {', '.join(subtask.depends_on)}]"
                    if subtask.depends_on
                    else ""
                )
                summary_parts.append(
                    f"  {i}. {subtask.title} ({subtask.priority.value}){deps}"
                )

        # Add suggestion to switch to EXECUTE mode
        summary_parts.append("\n" + "=" * 60)
        summary_parts.append(
            "✨ Plan complete! To execute, switch to EXECUTE mode with: /mode execute"
        )

        return "\n".join(summary_parts)

    async def _execute_all_pending_tasks(self) -> str:
        """
        Execute all pending tasks in dependency order.

        Returns:
            Execution summary
        """
        pending_tasks = await self.task_manager.list_tasks(status=TaskStatus.PENDING)

        if not pending_tasks:
            return "No pending tasks to execute."

        logger.info(f"Executing {len(pending_tasks)} pending tasks")
        total_tasks = len(pending_tasks)
        executed_count = 0
        failed_count = 0

        # Get executable tasks in dependency order
        while pending_tasks:
            # Find a task with no unsatisfied dependencies
            executable_task = None
            for task in pending_tasks:
                if await self._are_dependencies_met(task):
                    executable_task = task
                    break

            if not executable_task:
                # No executable tasks found - check for circular dependencies
                logger.warning("No executable tasks found - possible circular dependency")
                break

            # UX Enhancement: Display task progress
            task_number = executed_count + failed_count + 1
            if hasattr(self.display_manager, 'append_subtask_progress'):
                self.display_manager.append_subtask_progress(
                    task_number, total_tasks, executable_task.title
                )

            # Execute the task
            try:
                await self._execute_task(executable_task)

                # Execute its subtasks recursively
                await self._execute_subtasks_recursive(executable_task.id)

                executed_count += 1
            except Exception as e:
                logger.error(f"Failed to execute task {executable_task.id}: {e}")
                failed_count += 1

            # Refresh pending tasks list
            pending_tasks = await self.task_manager.list_tasks(status=TaskStatus.PENDING)

        return (
            f"Executed {executed_count} tasks successfully. "
            f"{failed_count} tasks failed. "
            f"{len(pending_tasks)} tasks remain pending."
        )

    async def _execute_subtasks_recursive(self, parent_id: str) -> None:
        """
        Recursively execute all subtasks of a parent task.

        Args:
            parent_id: ID of the parent task
        """
        # Get all subtasks
        subtasks = await self.task_manager.list_tasks(parent_id=parent_id)

        if not subtasks:
            return

        logger.info(f"Executing {len(subtasks)} subtasks of {parent_id}")

        # UX Enhancement: Display total number of subtasks
        total_subtasks = len(subtasks)
        executed_count = 0

        for subtask in subtasks:
            if subtask.status == TaskStatus.PENDING:
                # Check if dependencies are met
                if await self._are_dependencies_met(subtask):
                    executed_count += 1

                    # UX Enhancement: Display subtask progress
                    if hasattr(self.display_manager, 'append_subtask_progress'):
                        self.display_manager.append_subtask_progress(
                            executed_count, total_subtasks, subtask.title
                        )

                    # Execute subtask with isolated context
                    await self._execute_task(subtask)

                    # Recursively execute its subtasks
                    await self._execute_subtasks_recursive(subtask.id)
                else:
                    logger.info(
                        f"Subtask {subtask.id} blocked by dependencies, skipping"
                    )

    async def _are_dependencies_met(self, task: Task) -> bool:
        """
        Check if all dependencies of a task are completed.

        Args:
            task: Task to check

        Returns:
            True if all dependencies are met, False otherwise
        """
        if not task.depends_on:
            return True

        for dep_id in task.depends_on:
            dep_task = await self.task_manager.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    async def _get_dependency_results(self, dependency_ids: list[str]) -> dict[str, Any]:
        """
        Get results from dependency tasks.

        Args:
            dependency_ids: List of task IDs

        Returns:
            Dictionary mapping task ID to its result
        """
        results = {}

        for dep_id in dependency_ids:
            dep_task = await self.task_manager.get_task(dep_id)
            if dep_task and dep_task.result:
                results[dep_id] = {
                    "title": dep_task.title,
                    "result": dep_task.result,
                }

        return results

    def _check_interrupt(self) -> bool:
        """
        Check if interrupt is requested and handle accordingly.

        Returns:
            True if should stop execution, False to continue
        """
        if not self.interrupt_controller:
            return False

        state = self.interrupt_controller.check_interrupt()
        if state is None:
            return False

        # For any interrupt type, set should_stop flag
        self.should_stop = True
        logger.info(f"Interrupt detected: {state.interrupt_type.value}")

        # Show interrupt status in display
        if self.display_manager and hasattr(self.display_manager, "show_interrupt_status"):
            self.display_manager.show_interrupt_status("Interrupt requested, finishing current operation...")

        return True

    async def _handle_interrupt(self, task: Task, partial_result: Optional[str] = None) -> None:
        """
        Handle interrupt cleanup and state preservation.

        Args:
            task: Current task being executed
            partial_result: Any partial results to save
        """
        logger.info(f"Handling interrupt for task: {task.id}")

        # 1. Save workspace state
        if self.workspace and self.workspace_manager:
            try:
                self.workspace.add_assistant_message(
                    f"[Execution interrupted] Task: {task.title}"
                )
                self.workspace_manager.save(self.workspace)
                logger.info("Workspace saved on interrupt")
            except Exception as e:
                logger.error(f"Failed to save workspace on interrupt: {e}")

        # 2. Update task status - reset to PENDING (not FAILED)
        try:
            await self.task_manager.update_task(
                task.id,
                {
                    "status": TaskStatus.PENDING,
                    "error": "Interrupted by user",
                    "result": partial_result,
                },
            )
            logger.info(f"Task {task.id} reset to PENDING after interrupt")
        except Exception as e:
            logger.error(f"Failed to update task on interrupt: {e}")

        # 3. Cancel any active subagents
        if self.subagent_manager:
            try:
                active_count = self.subagent_manager.get_active_count()
                if active_count > 0:
                    logger.info(f"Cancelling {active_count} active subagents")
                    await self.subagent_manager.shutdown()
            except Exception as e:
                logger.error(f"Failed to cancel subagents on interrupt: {e}")

        # 4. Trigger interrupt hook
        await self._trigger_hook(
            "orchestrator.interrupted",
            {
                "task_id": task.id,
                "task_title": task.title,
                "partial_result": partial_result,
            },
        )

        # 5. Reset interrupt state and should_stop for next operation
        if self.interrupt_controller:
            await self.interrupt_controller.reset()
        self.should_stop = False

        # 6. Display completion message
        if self.display_manager and hasattr(self.display_manager, "show_interrupt_complete"):
            self.display_manager.show_interrupt_complete("Execution stopped. Ready for next command.")

    async def _reasoning_loop(self, task: Task, context: dict[str, Any]) -> Any:
        """
        Core LLM reasoning loop using Anthropic's native tool calling.

        Args:
            task: Current task
            context: Execution context

        Returns:
            Task result
        """
        max_iterations = self.config.get("orchestrator", {}).get("max_iterations", 20)
        conversation_history = []

        # Start live display if using LiveDisplayManager (Phase 5B)
        cli_config = self.config.get("cli", {})
        use_streaming = cli_config.get("use_streaming_display", False)
        use_live_display = cli_config.get("use_live_display", False)

        if use_live_display and hasattr(self.display_manager, 'start_live'):
            self.display_manager.start_live()

        try:
            for iteration in range(max_iterations):
                # === INTERRUPT CHECK POINT 1: Before each iteration ===
                if self._check_interrupt():
                    logger.info(f"Interrupt at iteration {iteration + 1}")
                    await self._handle_interrupt(task, partial_result=None)
                    return "[Execution interrupted by user]"

                logger.debug(f"Reasoning iteration {iteration + 1}/{max_iterations}")

                # Prepare messages for LLM
                messages = self._prepare_messages(task, context, conversation_history)

                # Get tool schemas for API
                tools = context.get("tools", [])

                # Trigger llm.before_call event with iteration metadata
                await self._trigger_hook(
                    "llm.before_call",
                    {"messages": messages, "tools": tools},
                    metadata={"iteration": iteration + 1, "max_iterations": max_iterations},
                )

                # Use streaming if available (Phase 5B)
                # Enable streaming for both live display and streaming display modes
                enable_streaming = (use_live_display or use_streaming) and hasattr(self.llm_client.provider, 'chat_stream')
                if enable_streaming:
                    from orchestrator.llm.client import StreamChunk, LLMResponse as LLMResp

                    # Clear/prepare thinking zone before streaming
                    if hasattr(self.display_manager, 'clear_thinking'):
                        self.display_manager.clear_thinking()

                    # Phase 7B: Show activity indicator while waiting for first token
                    # This provides visual feedback that the system is working
                    if hasattr(self.display_manager, 'start_activity'):
                        self.display_manager.start_activity("Thinking...")

                    # Stream response
                    reasoning_text = ""
                    response = None
                    first_token_received = False
                    stream_generator = self.llm_client.chat_stream(messages, tools=tools if tools else None)

                    # Consume stream - yields StreamChunk objects, then final LLMResponse
                    # Phase 7: Check interrupt between chunks for responsiveness
                    # Phase 7C: Track streaming progress and show warning if stalled
                    activity_config = cli_config.get("activity_indicator", {})
                    stream_warning_delay = activity_config.get("warning_delay", 10.0)
                    stream_warning_interval = activity_config.get("warning_interval", 15.0)

                    # Phase 7C: Background task to show warnings during streaming stalls
                    # Since async for blocks waiting for next chunk, we need a concurrent task
                    streaming_start_time = asyncio.get_event_loop().time()
                    last_chunk_time = streaming_start_time
                    warning_task_stop = asyncio.Event()

                    async def _streaming_warning_task():
                        """Background task to show warnings if streaming stalls."""
                        nonlocal last_chunk_time
                        last_warning_time = 0.0

                        # Wait for first token before starting warning checks
                        while not first_token_received and not warning_task_stop.is_set():
                            await asyncio.sleep(0.5)

                        while not warning_task_stop.is_set():
                            await asyncio.sleep(1.0)  # Check every second

                            if warning_task_stop.is_set():
                                break

                            current_time = asyncio.get_event_loop().time()
                            time_since_chunk = current_time - last_chunk_time
                            time_since_warning = current_time - last_warning_time if last_warning_time > 0 else float('inf')

                            # Show warning if stalled longer than warning_delay
                            if time_since_chunk >= stream_warning_delay:
                                # Only show warning at intervals
                                if time_since_warning >= stream_warning_interval or last_warning_time == 0:
                                    elapsed = int(time_since_chunk)
                                    sys.stdout.write(f"\n\033[33m⏳ Still waiting for response... ({elapsed}s)\033[0m\n")
                                    sys.stdout.flush()
                                    last_warning_time = current_time

                    # Start warning task
                    warning_task = asyncio.create_task(_streaming_warning_task())

                    try:
                        async for item in stream_generator:
                            # Update last chunk time for warning task
                            last_chunk_time = asyncio.get_event_loop().time()

                            # === INTERRUPT CHECK POINT 2: During streaming ===
                            if self._check_interrupt():
                                logger.info("Interrupt during streaming")
                                # Stop activity indicator if still running
                                if not first_token_received and hasattr(self.display_manager, 'stop_activity'):
                                    self.display_manager.stop_activity()
                                await self._handle_interrupt(task, partial_result=reasoning_text if reasoning_text else None)
                                return f"[Execution interrupted]\n\nPartial response:\n{reasoning_text}" if reasoning_text else "[Execution interrupted by user]"

                            if isinstance(item, StreamChunk):
                                # Phase 7B: On first token, stop spinner and show thinking header
                                if not first_token_received:
                                    first_token_received = True
                                    # Stop the "Thinking..." spinner
                                    if hasattr(self.display_manager, 'stop_activity'):
                                        self.display_manager.stop_activity()
                                    # Show "● Thinking" header and prepare for streaming
                                    if hasattr(self.display_manager, 'start_thinking_stream'):
                                        self.display_manager.start_thinking_stream()

                                # Text chunk - add to display
                                reasoning_text += item.text
                                if hasattr(self.display_manager, 'update_thinking_stream'):
                                    self.display_manager.update_thinking_stream(item.text)
                            elif isinstance(item, LLMResp):
                                # Final response
                                response = item
                    finally:
                        # Stop warning task when streaming completes
                        warning_task_stop.set()
                        warning_task.cancel()
                        try:
                            await warning_task
                        except asyncio.CancelledError:
                            pass

                    # End thinking stream (add newline for streaming display)
                    if first_token_received and hasattr(self.display_manager, 'end_thinking_stream'):
                        self.display_manager.end_thinking_stream()
                    # If no tokens were received (e.g., tool_use only), stop spinner
                    elif not first_token_received and hasattr(self.display_manager, 'stop_activity'):
                        self.display_manager.stop_activity()

                    # Verify we got a response
                    if response is None:
                        raise RuntimeError("Streaming API did not yield final LLMResponse")

                else:
                    # Fallback to non-streaming
                    response = await self.llm_client.chat(messages, tools=tools if tools else None)

                    # Extract reasoning text from response
                    reasoning_text = ""
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "text":
                            reasoning_text += block.text + "\n"

                # Trigger llm.after_call event with reasoning text
                token_count = getattr(response, "usage", {}).get("total_tokens", "unknown")
                await self._trigger_hook(
                    "llm.after_call",
                    {"response": response, "token_count": token_count, "reasoning_text": reasoning_text.strip()},
                )

                # Process response based on stop_reason
                if response.stop_reason == "end_turn":
                    # Extract text content from response
                    text_content = []
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "text":
                            text_content.append(block.text)

                    # UX Fix: In streaming mode, thinking text was already displayed
                    # Return empty to avoid duplication in Task Complete block
                    if enable_streaming and reasoning_text:
                        return ""  # Empty result prevents duplicate display
                    else:
                        result = "\n".join(text_content) if text_content else "Task completed"
                        return result

                elif response.stop_reason == "tool_use":
                    # Add assistant message with tool_use blocks to history
                    conversation_history.append({"role": "assistant", "content": response.content})

                    # Process each tool use
                    tool_results = []
                    for block in response.content:
                        if hasattr(block, "type") and block.type == "tool_use":
                            # === INTERRUPT CHECK POINT 3: Before each tool execution ===
                            if self._check_interrupt():
                                logger.info(f"Interrupt before tool execution: {block.name}")
                                await self._handle_interrupt(task, partial_result=reasoning_text if reasoning_text else None)
                                return "[Execution interrupted before tool execution]"

                            logger.info(f"Executing tool: {block.name}")

                            # Update display with tool execution
                            if hasattr(self.display_manager, 'update_tool_status'):
                                self.display_manager.update_tool_status(f"▶ Running: {block.name}")

                            # Execute tool
                            tool_result = await self._execute_tool(block.name, block.input)

                            # Update display with result
                            if hasattr(self.display_manager, 'update_tool_status'):
                                status = "✓ Success" if tool_result.success else "✗ Failed"
                                self.display_manager.update_tool_status(f"{status}: {block.name}")

                            # Build tool result in Anthropic format
                            tool_results.append(
                                {
                                    "type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": str(tool_result.data if tool_result.success else tool_result.error),
                                }
                            )

                    # Add tool results as user message
                    conversation_history.append({"role": "user", "content": tool_results})

                elif response.stop_reason == "max_tokens":
                    logger.warning("Response hit max_tokens limit, continuing...")
                    # Add partial response to history so LLM can continue
                    if response.content:
                        conversation_history.append({"role": "assistant", "content": response.content})
                        # Add a continuation prompt
                        conversation_history.append({
                            "role": "user",
                            "content": "Please continue from where you left off."
                        })
                    # Continue loop to get more output

                else:
                    logger.warning(f"Unknown stop_reason: {response.stop_reason}")

            raise RuntimeError(f"Task {task.id} exceeded max iterations ({max_iterations})")
        finally:
            # Stop live display when reasoning loop ends
            if use_live_display and hasattr(self.display_manager, 'stop_live'):
                self.display_manager.stop_live()

    def _prepare_messages(
        self, task: Task, context: dict[str, Any], conversation_history: list[dict]
    ) -> list[dict]:
        """
        Prepare messages for LLM.

        Args:
            task: Current task
            context: Context dictionary
            conversation_history: Previous conversation

        Returns:
            List of messages
        """
        messages = [
            {
                "role": "system",
                "content": self._build_system_prompt(context),
            },
            {
                "role": "user",
                "content": f"Task: {task.description or task.title}",
            },
        ]

        # Add conversation history
        messages.extend(conversation_history)

        return messages

    def _build_system_prompt(self, context: dict[str, Any]) -> str:
        """
        Build system prompt for LLM.

        Args:
            context: Context dictionary

        Returns:
            System prompt string
        """
        # For Anthropic, tools are passed via API parameter, not in system prompt
        max_iterations = self.config.get("orchestrator", {}).get("max_iterations", 20)

        # Build base prompt
        prompt = f"""You are an AI assistant helping with task execution.

You have access to tools that will be provided via the API. Use them as needed to complete tasks."""

        # Inject skills if available (Phase 4A)
        skill_instructions = self._get_skill_instructions(context)
        if skill_instructions:
            prompt += f"\n\n{skill_instructions}"

        # Phase 6A: Inject mode-specific instructions
        if self.mode_manager:
            mode_suffix = self.mode_manager.get_mode_prompt_suffix()
            prompt += f"\n{mode_suffix}"

        # Inject workspace context if available (Phase 5B)
        workspace_context = context.get("workspace_context")
        if workspace_context:
            prompt += f"\n\n# Context from This Session:\n{workspace_context}"

        prompt += """

IMPORTANT - Task Progress Tracking:
For complex multi-step tasks, use the 'todo_list' tool to track your progress:
1. Break down the task into clear, actionable steps
2. Use 'write' operation to create your TODO list at the start
3. Mark current step as 'in_progress' when working on it
4. Mark steps as 'completed' when done
5. Use 'list' operation to review progress

This helps you maintain context across reasoning iterations (max {max_iterations} iterations).
Without a TODO list, you may lose track of progress in long-running tasks.

IMPORTANT - Task Decomposition:
For very complex multi-step tasks that require structured execution order, use the 'task_decompose' tool:
1. Analyze the task and identify logical subtasks
2. Use 'create_subtask' operation to break down the work
3. Use 'add_dependency' to set execution order between subtasks (optional)
4. Subtasks will execute automatically before the parent task completes

Example - Create subtask:
{{
  "operation": "create_subtask",
  "title": "Design database schema",
  "description": "Design tables and relationships for user management",
  "priority": "high"
}}

Example - Add dependency (subtask B depends on subtask A):
{{
  "operation": "add_dependency",
  "task_id": "subtask_b_id",
  "depends_on_task_id": "subtask_a_id"
}}

Example - List all subtasks:
{{
  "operation": "list_subtasks"
}}

When to use task_decompose vs todo_list:
- Use 'task_decompose' when subtasks need to be tracked separately, have dependencies, or could fail independently
- Use 'todo_list' for tracking progress within a single task execution

When the task is complete, provide a clear summary of what was accomplished.

If you need more information from the user, ask clearly and specifically."""

        return prompt

    async def _execute_tool(self, tool_name: str, tool_args: dict) -> Any:
        """
        Execute a tool with hook support for HITL.

        Args:
            tool_name: Name of tool to execute
            tool_args: Tool arguments

        Returns:
            Tool result
        """
        logger.info(f"Executing tool: {tool_name}")

        # Check cache for tool result (Phase 5)
        if self.cache_manager and self.cache_manager.tool_results_enabled:
            cached_result = self.cache_manager.get_cached_tool_result(tool_name, tool_args)
            if cached_result is not None:
                logger.info(f"Cache hit for tool: {tool_name}")
                return cached_result

        tool = self.tool_registry.get(tool_name)
        if not tool:
            from orchestrator.tools.base import ToolResult

            return ToolResult(success=False, error=f"Tool not found: {tool_name}")

        # Check if tool requires approval
        requires_approval = tool.definition.requires_approval

        # Trigger tool.before_execute event
        hook_result = await self._trigger_hook(
            "tool.before_execute",
            {"tool_name": tool_name, "tool_input": tool_args, "requires_approval": requires_approval},
        )

        if hook_result.action == "block":
            from orchestrator.tools.base import ToolResult

            reason = hook_result.reason or "Tool execution blocked by hook"
            logger.warning(f"Tool {tool_name} blocked: {reason}")
            return ToolResult(success=False, error=reason)

        # Trigger HITL approval if needed
        if requires_approval:
            # Phase 7B: Activity indicator is started by DisplayHook in tool.before_execute
            # HITLHook will stop it before showing the prompt
            approval_result = await self._trigger_hook(
                "tool.requires_approval",
                {"tool_name": tool_name, "tool_input": tool_args, "requires_approval": True},
            )

            if approval_result.action == "block":
                from orchestrator.tools.base import ToolResult

                reason = approval_result.reason or "Tool execution denied by user"
                logger.warning(f"Tool {tool_name} denied: {reason}")
                return ToolResult(success=False, error=reason)

        # Inject current task into TodoListTool if applicable
        if tool_name == "todo_list" and hasattr(tool, "set_current_task"):
            tool.set_current_task(self.current_task)

        # Inject current task and task manager into TaskDecomposeTool (Phase 3)
        if tool_name == "task_decompose":
            if hasattr(tool, "set_current_task"):
                tool.set_current_task(self.current_task)
            if hasattr(tool, "set_task_manager"):
                tool.set_task_manager(self.task_manager)

        # Execute tool with activity indicator (Phase 7B)
        # Show spinner during tool execution for better UX feedback
        if hasattr(self.display_manager, "show_tool_activity"):
            async with self.display_manager.show_tool_activity(tool_name, tool_args):
                result = await tool.execute(**tool_args)
        else:
            result = await tool.execute(**tool_args)
        logger.info(f"Tool result: {result.success}")

        # Cache successful tool results (Phase 5)
        if self.cache_manager and self.cache_manager.tool_results_enabled and result.success:
            self.cache_manager.cache_tool_result(tool_name, tool_args, result)
            logger.debug(f"Cached tool result: {tool_name}")

        # Trigger tool.after_execute event
        await self._trigger_hook(
            "tool.after_execute",
            {"tool_name": tool_name, "tool_input": tool_args, "success": result.success, "result": result},
        )

        # NEW (Phase 6D): Save workspace after tool execution to persist whitelist changes
        if self.workspace and self.workspace_manager:
            self.workspace_manager.save(self.workspace)

        return result

    async def _trigger_hook(self, event: str, data: dict[str, Any], metadata: dict[str, Any] | None = None) -> Any:
        """
        Trigger a hook event.

        Args:
            event: Event name
            data: Event data
            metadata: Optional metadata to pass to hooks

        Returns:
            HookResult
        """
        if not self.hook_engine or not self.hook_engine.is_enabled():
            from orchestrator.hooks.base import HookResult

            return HookResult(action="continue")

        return await self.hook_engine.trigger(event, data, orchestrator_state=self, metadata=metadata)

    async def _handle_task_completion(self, completed_task_id: str) -> None:
        """
        Handle task completion for Phase 3 hierarchy and dependencies.

        After a task completes:
        1. Unblock tasks that were waiting on this task
        2. Check if parent task can be marked as completed

        Args:
            completed_task_id: ID of the task that just completed
        """
        # Unblock dependent tasks
        await self._unblock_dependent_tasks(completed_task_id)

        # Check parent completion
        completed_task = await self.task_manager.get_task(completed_task_id)
        if completed_task and completed_task.parent_id:
            await self._check_parent_completion(completed_task.parent_id)

    async def _unblock_dependent_tasks(self, completed_task_id: str) -> None:
        """
        Check and unblock tasks that were waiting on the completed task.

        Args:
            completed_task_id: ID of the completed task
        """
        completed_task = await self.task_manager.get_task(completed_task_id)
        if not completed_task:
            return

        # Get all tasks blocked by this task
        for blocked_task_id in completed_task.blocks:
            blocked_task = await self.task_manager.get_task(blocked_task_id)
            if not blocked_task or blocked_task.status != TaskStatus.BLOCKED:
                continue

            # Check if all dependencies are now completed
            all_deps_completed = True
            for dep_id in blocked_task.depends_on:
                dep_task = await self.task_manager.get_task(dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    all_deps_completed = False
                    break

            # Unblock task if all dependencies are satisfied
            if all_deps_completed:
                await self.task_manager.update_task(
                    blocked_task_id, {"status": TaskStatus.PENDING}
                )
                logger.info(
                    f"Unblocked task {blocked_task_id} (all dependencies completed)"
                )

    async def _check_parent_completion(self, parent_id: str) -> None:
        """
        Check if parent task can be marked as completed.

        A parent task is automatically completed if all its subtasks are completed.

        Args:
            parent_id: ID of the parent task to check
        """
        parent = await self.task_manager.get_task(parent_id)
        if not parent:
            return

        # Only auto-complete if parent is IN_PROGRESS
        if parent.status != TaskStatus.IN_PROGRESS:
            return

        # Check if all subtasks are completed
        all_subtasks_completed = True
        for subtask_id in parent.subtasks:
            subtask = await self.task_manager.get_task(subtask_id)
            if not subtask or subtask.status != TaskStatus.COMPLETED:
                all_subtasks_completed = False
                break

        # Auto-complete parent if all subtasks are done
        if all_subtasks_completed and parent.subtasks:
            await self.task_manager.update_task(
                parent_id,
                {
                    "status": TaskStatus.COMPLETED,
                    "result": f"All {len(parent.subtasks)} subtasks completed successfully",
                },
            )
            logger.info(f"Auto-completed parent task {parent_id} (all subtasks done)")

            # Trigger completion event
            await self._trigger_hook(
                "task.completed",
                {"task": parent, "result": "All subtasks completed"},
            )

            # Recursively check grandparent
            if parent.parent_id:
                await self._check_parent_completion(parent.parent_id)

    def _get_skill_instructions(self, context: dict[str, Any]) -> str:
        """
        Get skill instructions to inject into system prompt (Phase 4A).

        Matches skills to the current task based on:
        - Task description keywords
        - Available tools

        Args:
            context: Context dictionary with task info

        Returns:
            Formatted skill instructions or empty string
        """
        if not self.skill_registry or not self.config.get("skills", {}).get("enabled", True):
            return ""

        # Get current task description
        task_description = context.get("task_description", "")
        if not task_description:
            return ""

        # Get available tool names
        available_tools = [tool.definition.name for tool in self.tool_registry.tools.values()]

        # Get recommended skills
        skills = self.skill_registry.get_skills_for_task(task_description, available_tools)

        # Limit to top 3 skills to avoid prompt bloat
        max_skills = self.config.get("skills", {}).get("max_auto_inject", 3)
        skills = skills[:max_skills]

        if not skills:
            return ""

        # Format skill instructions
        skill_text = "# Available Skills\n\n"
        skill_text += "The following skills are available to guide your work:\n\n"

        for skill in skills:
            skill_text += f"## {skill.metadata.name}\n"
            skill_text += f"{skill.metadata.description}\n\n"
            skill_text += f"{skill.content}\n\n"
            skill_text += "---\n\n"

        return skill_text
