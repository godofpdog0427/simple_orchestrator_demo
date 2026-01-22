"""Built-in metrics collection hooks."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from orchestrator.hooks.base import Hook, HookContext, HookResult

logger = logging.getLogger(__name__)


class MetricsHook(Hook):
    """
    Hook that collects execution statistics.

    Tracks:
    - Task completions/failures
    - Task duration
    - Tool usage frequency
    - Tool success/failure rates

    Config options:
        output_file: Path to metrics JSON file (default: .orchestrator/metrics.json)
        collect_task_metrics: Track task metrics (default: True)
        collect_tool_metrics: Track tool metrics (default: True)
    """

    priority = 100  # Low priority, runs after other hooks

    def __init__(self, config: dict[str, Any]):
        """
        Initialize metrics hook.

        Args:
            config: Hook configuration
        """
        self.config = config
        self.output_file = config.get("output_file", ".orchestrator/metrics.json")
        self.collect_task_metrics = config.get("collect_task_metrics", True)
        self.collect_tool_metrics = config.get("collect_tool_metrics", True)

        # In-memory metrics (will be persisted to file)
        self.metrics: dict[str, Any] = {
            "tasks": {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "durations": [],  # List of (task_id, duration_seconds)
            },
            "tools": {},  # tool_name -> {calls: int, successes: int, failures: int}
            "last_updated": None,
        }

        # Ensure output directory exists
        Path(self.output_file).parent.mkdir(parents=True, exist_ok=True)

        # Load existing metrics
        self._load_metrics()

    async def execute(self, context: HookContext) -> HookResult:
        """
        Collect metrics based on event.

        Args:
            context: Hook context

        Returns:
            HookResult to continue execution
        """
        try:
            event = context.event
            data = context.data

            # Task metrics
            if self.collect_task_metrics:
                if event == "task.started":
                    self.metrics["tasks"]["total"] += 1
                    # Store start time in metadata for duration calculation
                    return HookResult(
                        action="continue", metadata={"task_start_time": datetime.now().isoformat()}
                    )

                elif event == "task.completed":
                    self.metrics["tasks"]["completed"] += 1
                    # Calculate duration if start time available
                    if "task_start_time" in context.metadata:
                        start_time = datetime.fromisoformat(context.metadata["task_start_time"])
                        duration = (datetime.now() - start_time).total_seconds()
                        task_id = data.get("task", {}).get("id", "unknown")
                        self.metrics["tasks"]["durations"].append((task_id, duration))

                elif event == "task.failed":
                    self.metrics["tasks"]["failed"] += 1

            # Tool metrics
            if self.collect_tool_metrics and event == "tool.after_execute":
                tool_name = data.get("tool_name", "unknown")
                success = data.get("success", False)

                if tool_name not in self.metrics["tools"]:
                    self.metrics["tools"][tool_name] = {"calls": 0, "successes": 0, "failures": 0}

                self.metrics["tools"][tool_name]["calls"] += 1
                if success:
                    self.metrics["tools"][tool_name]["successes"] += 1
                else:
                    self.metrics["tools"][tool_name]["failures"] += 1

            # Update timestamp and save
            self.metrics["last_updated"] = datetime.now().isoformat()
            self._save_metrics()

        except Exception as e:
            logger.error(f"Error in MetricsHook: {e}", exc_info=True)

        return HookResult(action="continue")

    def _load_metrics(self) -> None:
        """Load metrics from file if exists."""
        try:
            if Path(self.output_file).exists():
                with open(self.output_file) as f:
                    saved_metrics = json.load(f)
                    # Merge with default structure
                    self.metrics.update(saved_metrics)
                    logger.debug(f"Loaded metrics from {self.output_file}")
        except Exception as e:
            logger.warning(f"Error loading metrics: {e}")

    def _save_metrics(self) -> None:
        """Save metrics to file."""
        try:
            with open(self.output_file, "w") as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving metrics: {e}", exc_info=True)

    def get_summary(self) -> dict[str, Any]:
        """
        Get metrics summary.

        Returns:
            Summary dictionary
        """
        summary = {
            "tasks": {
                "total": self.metrics["tasks"]["total"],
                "completed": self.metrics["tasks"]["completed"],
                "failed": self.metrics["tasks"]["failed"],
                "success_rate": (
                    self.metrics["tasks"]["completed"] / self.metrics["tasks"]["total"]
                    if self.metrics["tasks"]["total"] > 0
                    else 0.0
                ),
            },
            "tools": {},
        }

        # Calculate tool statistics
        for tool_name, tool_metrics in self.metrics["tools"].items():
            calls = tool_metrics["calls"]
            successes = tool_metrics["successes"]
            summary["tools"][tool_name] = {
                "calls": calls,
                "success_rate": successes / calls if calls > 0 else 0.0,
            }

        return summary
