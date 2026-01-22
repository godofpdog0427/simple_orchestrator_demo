"""Task manager for managing task lifecycle."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from orchestrator.tasks.models import Task, TaskStatus

logger = logging.getLogger(__name__)


class TaskManager:
    """Manager for task creation, storage, and retrieval."""

    def __init__(self, config: dict) -> None:
        """
        Initialize task manager.

        Args:
            config: Task configuration
        """
        self.config = config
        self.tasks: dict[str, Task] = {}
        self.max_pending_tasks = config.get("max_pending_tasks", 100)

    async def create_task(self, task: Task) -> Task:
        """
        Create a new task.

        Args:
            task: Task to create

        Returns:
            Created task
        """
        pending_count = len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING])
        if pending_count >= self.max_pending_tasks:
            raise RuntimeError(
                f"Max pending tasks limit reached ({self.max_pending_tasks})"
            )

        self.tasks[task.id] = task
        logger.info(f"Created task: {task.id} - {task.title}")

        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """
        Get a task by ID.

        Args:
            task_id: Task ID

        Returns:
            Task or None if not found
        """
        return self.tasks.get(task_id)

    async def update_task(self, task_id: str, updates: dict) -> Task:
        """
        Update a task.

        Args:
            task_id: Task ID
            updates: Dictionary of fields to update

        Returns:
            Updated task

        Raises:
            KeyError: If task not found
        """
        task = self.tasks.get(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")

        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()

        if task.status == TaskStatus.COMPLETED and not task.completed_at:
            task.completed_at = datetime.utcnow()

        logger.debug(f"Updated task: {task_id}")

        return task

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task.

        Args:
            task_id: Task ID

        Returns:
            True if deleted, False if not found
        """
        if task_id in self.tasks:
            del self.tasks[task_id]
            logger.info(f"Deleted task: {task_id}")
            return True
        return False

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        parent_id: Optional[str] = None,
    ) -> list[Task]:
        """
        List tasks with optional filters.

        Args:
            status: Filter by status
            parent_id: Filter by parent task ID

        Returns:
            List of tasks
        """
        tasks = list(self.tasks.values())

        if status:
            tasks = [t for t in tasks if t.status == status]

        if parent_id is not None:
            tasks = [t for t in tasks if t.parent_id == parent_id]

        return tasks

    async def get_next_executable_task(self) -> Optional[Task]:
        """
        Get the next task that can be executed (Phase 3 implementation).

        A task is executable if:
        1. Status is PENDING
        2. All dependencies (depends_on) are COMPLETED
        3. If it has subtasks, all subtasks are COMPLETED
        4. Parent task (if exists) is IN_PROGRESS

        Returns:
            Next executable task or None (sorted by priority)
        """
        pending_tasks = await self.list_tasks(status=TaskStatus.PENDING)

        if not pending_tasks:
            return None

        # Filter for executable tasks
        executable_tasks = []
        for task in pending_tasks:
            if await self._is_task_executable(task):
                executable_tasks.append(task)

        if not executable_tasks:
            return None

        # Sort by priority (CRITICAL > HIGH > MEDIUM > LOW)
        from orchestrator.tasks.models import TaskPriority

        priority_order = {
            TaskPriority.CRITICAL: 0,
            TaskPriority.HIGH: 1,
            TaskPriority.MEDIUM: 2,
            TaskPriority.LOW: 3,
        }

        executable_tasks.sort(key=lambda t: priority_order.get(t.priority, 999))

        return executable_tasks[0]

    async def _is_task_executable(self, task: Task) -> bool:
        """
        Check if a task is ready to be executed.

        Args:
            task: Task to check

        Returns:
            True if executable, False otherwise
        """
        # 1. Check dependencies - all must be COMPLETED
        for dep_id in task.depends_on:
            dep_task = await self.get_task(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False

        # 2. Check subtasks - all must be COMPLETED
        for subtask_id in task.subtasks:
            subtask = await self.get_task(subtask_id)
            if not subtask or subtask.status != TaskStatus.COMPLETED:
                return False

        # 3. Check parent - must be IN_PROGRESS if parent exists
        if task.parent_id:
            parent = await self.get_task(task.parent_id)
            if not parent or parent.status not in [TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]:
                return False

        return True

    async def get_execution_order(self, task_ids: list[str]) -> list[Task]:
        """
        Get tasks in dependency-safe execution order using topological sort.

        Uses Kahn's algorithm for topological sorting.

        Args:
            task_ids: List of task IDs to order

        Returns:
            List of tasks in execution order

        Raises:
            ValueError: If dependency cycle detected
        """
        # Build in-degree map (number of dependencies for each task)
        in_degree: dict[str, int] = {}
        task_map: dict[str, Task] = {}

        for task_id in task_ids:
            task = await self.get_task(task_id)
            if task:
                task_map[task_id] = task
                in_degree[task_id] = len(task.depends_on)

        # Queue of tasks with no dependencies
        queue = [tid for tid in task_ids if in_degree.get(tid, 0) == 0]
        result = []

        while queue:
            # Process task with no remaining dependencies
            task_id = queue.pop(0)
            task = task_map.get(task_id)
            if not task:
                continue

            result.append(task)

            # Reduce in-degree for blocked tasks
            for blocked_id in task.blocks:
                if blocked_id in in_degree:
                    in_degree[blocked_id] -= 1
                    if in_degree[blocked_id] == 0:
                        queue.append(blocked_id)

        # Check if all tasks were processed (cycle detection)
        if len(result) != len([t for t in task_map.values()]):
            raise ValueError("Dependency cycle detected in task graph")

        return result

    async def save_state(self, path: Optional[Path] = None) -> None:
        """
        Save task state to file.

        Args:
            path: Optional path to save to, defaults to config
        """
        if path is None:
            persistence_config = self.config.get("persistence", {})
            if not persistence_config.get("enabled", True):
                logger.debug("Persistence disabled, skipping save")
                return

            state_file = persistence_config.get("state_file", "./.orchestrator/state.json")
            path = Path(state_file)

        path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "tasks": {
                task_id: task.model_dump(mode="json")
                for task_id, task in self.tasks.items()
            }
        }

        try:
            with open(path, "w") as f:
                json.dump(state, f, indent=2)

            logger.info(f"Saved task state to {path}")

        except Exception as e:
            logger.error(f"Error saving task state: {e}", exc_info=True)

    async def load_state(self, path: Optional[Path] = None) -> None:
        """
        Load task state from file.

        Args:
            path: Optional path to load from, defaults to config
        """
        if path is None:
            persistence_config = self.config.get("persistence", {})
            if not persistence_config.get("enabled", True):
                logger.debug("Persistence disabled, skipping load")
                return

            state_file = persistence_config.get("state_file", "./.orchestrator/state.json")
            path = Path(state_file)

        if not path.exists():
            logger.debug(f"State file does not exist: {path}")
            return

        try:
            with open(path, "r") as f:
                state = json.load(f)

            if "tasks" in state:
                for task_id, task_data in state["tasks"].items():
                    task = Task(**task_data)
                    self.tasks[task_id] = task

            logger.info(f"Loaded {len(self.tasks)} tasks from {path}")

        except Exception as e:
            logger.error(f"Error loading task state: {e}", exc_info=True)

    async def create_subtask(
        self,
        parent_id: str,
        title: str,
        description: Optional[str] = None,
        priority: Optional["TaskPriority"] = None,
        **kwargs,
    ) -> Task:
        """
        Create a subtask under a parent task.

        Args:
            parent_id: Parent task ID
            title: Subtask title
            description: Subtask description
            priority: Task priority
            **kwargs: Additional task fields

        Returns:
            Created subtask

        Raises:
            KeyError: If parent task not found
            RuntimeError: If max depth exceeded
        """
        # Validate parent exists
        parent = await self.get_task(parent_id)
        if not parent:
            raise KeyError(f"Parent task not found: {parent_id}")

        # Check depth limit
        max_depth = self.config.get("max_depth", 5)
        depth = await self._get_task_depth(parent_id)
        if depth >= max_depth:
            raise RuntimeError(
                f"Max task depth ({max_depth}) exceeded. Cannot create subtask under {parent_id}"
            )

        # Check subtask count limit
        max_subtasks = self.config.get("max_subtasks_per_task", 20)
        if len(parent.subtasks) >= max_subtasks:
            raise RuntimeError(
                f"Max subtasks per task ({max_subtasks}) exceeded for {parent_id}"
            )

        # Create subtask
        from orchestrator.tasks.models import TaskPriority

        subtask = Task(
            title=title,
            description=description,
            parent_id=parent_id,
            priority=priority or TaskPriority.MEDIUM,
            **kwargs,
        )

        # Add to task manager
        await self.create_task(subtask)

        # Update parent's subtasks list
        parent.subtasks.append(subtask.id)
        parent.updated_at = datetime.utcnow()

        logger.info(f"Created subtask {subtask.id} under parent {parent_id}")

        return subtask

    async def _get_task_depth(self, task_id: str) -> int:
        """
        Get the depth of a task in the hierarchy.

        Args:
            task_id: Task ID

        Returns:
            Depth (0 for root tasks, 1 for direct children, etc.)
        """
        task = await self.get_task(task_id)
        if not task or not task.parent_id:
            return 0

        return 1 + await self._get_task_depth(task.parent_id)

    async def add_dependency(self, task_id: str, depends_on_id: str) -> None:
        """
        Add a dependency: task_id depends on depends_on_id.

        This means task_id cannot start until depends_on_id is COMPLETED.

        Args:
            task_id: Task that has the dependency
            depends_on_id: Task that must complete first

        Raises:
            KeyError: If either task not found
            ValueError: If dependency would create a cycle
        """
        # Validate both tasks exist
        task = await self.get_task(task_id)
        depends_on_task = await self.get_task(depends_on_id)

        if not task:
            raise KeyError(f"Task not found: {task_id}")
        if not depends_on_task:
            raise KeyError(f"Dependency task not found: {depends_on_id}")

        # Check for self-dependency
        if task_id == depends_on_id:
            raise ValueError("Task cannot depend on itself")

        # Check for cycles
        if self._has_dependency_cycle(task_id, depends_on_id):
            raise ValueError(
                f"Adding dependency {task_id} -> {depends_on_id} would create a cycle"
            )

        # Add dependency
        if depends_on_id not in task.depends_on:
            task.depends_on.append(depends_on_id)
            task.updated_at = datetime.utcnow()

        # Add to blocks list
        if task_id not in depends_on_task.blocks:
            depends_on_task.blocks.append(task_id)
            depends_on_task.updated_at = datetime.utcnow()

        # Auto-block task if dependency not completed
        auto_block = self.config.get("auto_block_on_dependency", True)
        if auto_block and depends_on_task.status != TaskStatus.COMPLETED:
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.BLOCKED
                logger.info(
                    f"Task {task_id} auto-blocked (waiting for {depends_on_id})"
                )

        logger.info(f"Added dependency: {task_id} depends on {depends_on_id}")

    async def remove_dependency(self, task_id: str, depends_on_id: str) -> None:
        """
        Remove a dependency relationship.

        Args:
            task_id: Task that has the dependency
            depends_on_id: Task to remove from dependencies

        Raises:
            KeyError: If either task not found
        """
        task = await self.get_task(task_id)
        depends_on_task = await self.get_task(depends_on_id)

        if not task:
            raise KeyError(f"Task not found: {task_id}")
        if not depends_on_task:
            raise KeyError(f"Dependency task not found: {depends_on_id}")

        # Remove dependency
        if depends_on_id in task.depends_on:
            task.depends_on.remove(depends_on_id)
            task.updated_at = datetime.utcnow()

        # Remove from blocks list
        if task_id in depends_on_task.blocks:
            depends_on_task.blocks.remove(task_id)
            depends_on_task.updated_at = datetime.utcnow()

        logger.info(f"Removed dependency: {task_id} no longer depends on {depends_on_id}")

    def _has_dependency_cycle(self, task_id: str, new_dependency_id: str) -> bool:
        """
        Check if adding a dependency would create a cycle.

        Uses DFS to check if there's a path from new_dependency_id back to task_id.
        If such a path exists, adding task_id -> new_dependency_id creates a cycle.

        Args:
            task_id: Task that would get the new dependency
            new_dependency_id: Task to add as dependency

        Returns:
            True if cycle would be created, False otherwise
        """
        visited = set()
        return self._has_cycle_dfs(new_dependency_id, task_id, visited)

    def _has_cycle_dfs(self, start: str, target: str, visited: set) -> bool:
        """
        DFS to check if path exists from start to target.

        Args:
            start: Starting task ID
            target: Target task ID
            visited: Set of visited task IDs

        Returns:
            True if path exists, False otherwise
        """
        if start == target:
            return True

        if start in visited:
            return False

        visited.add(start)

        task = self.tasks.get(start)
        if not task:
            return False

        # Check all tasks that start depends on
        for dep_id in task.depends_on:
            if self._has_cycle_dfs(dep_id, target, visited):
                return True

        return False

    async def get_dependencies(self, task_id: str) -> dict[str, list[Task]]:
        """
        Get all dependency relationships for a task.

        Args:
            task_id: Task ID

        Returns:
            Dictionary with dependency information:
            {
                "depends_on": [list of tasks this task depends on],
                "blocks": [list of tasks blocked by this task],
                "subtasks": [list of child tasks],
                "parent": parent task or None
            }

        Raises:
            KeyError: If task not found
        """
        task = await self.get_task(task_id)
        if not task:
            raise KeyError(f"Task not found: {task_id}")

        result = {
            "depends_on": [],
            "blocks": [],
            "subtasks": [],
            "parent": None,
        }

        # Get depends_on tasks
        for dep_id in task.depends_on:
            dep_task = await self.get_task(dep_id)
            if dep_task:
                result["depends_on"].append(dep_task)

        # Get blocked tasks
        for blocked_id in task.blocks:
            blocked_task = await self.get_task(blocked_id)
            if blocked_task:
                result["blocks"].append(blocked_task)

        # Get subtasks
        for subtask_id in task.subtasks:
            subtask = await self.get_task(subtask_id)
            if subtask:
                result["subtasks"].append(subtask)

        # Get parent
        if task.parent_id:
            result["parent"] = await self.get_task(task.parent_id)

        return result
