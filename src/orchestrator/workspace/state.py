"""Workspace state models and persistence manager."""

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Single message in conversation."""

    role: str  # "user" or "assistant"
    content: str | list[dict]  # Text or tool use blocks
    timestamp: datetime


@dataclass
class TaskSummary:
    """Compressed summary of completed task."""

    task_id: str
    task_description: str
    timestamp: datetime
    summary: str  # LLM-generated 2-3 sentence summary
    key_results: list[str]
    tools_used: list[str]
    status: str  # COMPLETED, FAILED


@dataclass
class WorkspaceState:
    """Persistent state for an orchestrator session."""

    session_id: str
    created_at: datetime
    last_updated: datetime

    # Conversation history (accumulates across tasks)
    workspace_conversation: list[Message] = field(default_factory=list)

    # Recent task summaries (rolling window)
    task_summaries: deque = field(default_factory=lambda: deque(maxlen=10))

    # User preferences (extracted over time)
    user_preferences: dict[str, Any] = field(default_factory=dict)

    def add_user_message(self, content: str) -> None:
        """Add user message to workspace conversation."""
        self.workspace_conversation.append(
            Message(role="user", content=content, timestamp=datetime.now())
        )

    def add_assistant_message(self, content: str) -> None:
        """Add assistant response to workspace conversation."""
        self.workspace_conversation.append(
            Message(role="assistant", content=content, timestamp=datetime.now())
        )

    def add_task_summary(self, summary: TaskSummary) -> None:
        """Add completed task summary."""
        self.task_summaries.append(summary)

    def get_recent_context(self, max_messages: int = 20) -> list[Message]:
        """Get recent conversation history for context injection."""
        return list(self.workspace_conversation)[-max_messages:]

    def search_summaries(self, keywords: list[str]) -> list[TaskSummary]:
        """Simple keyword search in task summaries."""
        results = []
        for summary in self.task_summaries:
            text = f"{summary.task_description} {summary.summary}".lower()
            if any(kw.lower() in text for kw in keywords):
                results.append(summary)
        return results


class WorkspaceManager:
    """Manages workspace state persistence."""

    def __init__(self, workspace_dir: str = ".orchestrator/workspace"):
        self.workspace_dir = Path(workspace_dir)
        self.workspace_dir.mkdir(parents=True, exist_ok=True)

    def load_or_create(self, session_id: str) -> WorkspaceState:
        """Load existing workspace or create new one."""
        workspace_file = self.workspace_dir / f"{session_id}.json"

        if workspace_file.exists():
            with open(workspace_file) as f:
                data = json.load(f)
                return self._deserialize(data)
        else:
            workspace = WorkspaceState(
                session_id=session_id,
                created_at=datetime.now(),
                last_updated=datetime.now(),
                workspace_conversation=[],
                task_summaries=deque(maxlen=10),
                user_preferences={},
            )
            logger.info(f"Created new workspace: {session_id}")
            return workspace

    def save(self, workspace: WorkspaceState) -> None:
        """Persist workspace state to disk."""
        workspace.last_updated = datetime.now()
        workspace_file = self.workspace_dir / f"{workspace.session_id}.json"

        with open(workspace_file, "w") as f:
            json.dump(self._serialize(workspace), f, indent=2)

        logger.debug(f"Saved workspace: {workspace.session_id}")

    def _serialize(self, workspace: WorkspaceState) -> dict:
        """Convert workspace to JSON-serializable dict."""
        return {
            "session_id": workspace.session_id,
            "created_at": workspace.created_at.isoformat(),
            "last_updated": workspace.last_updated.isoformat(),
            "workspace_conversation": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                }
                for msg in workspace.workspace_conversation
            ],
            "task_summaries": [
                {
                    "task_id": ts.task_id,
                    "task_description": ts.task_description,
                    "timestamp": ts.timestamp.isoformat(),
                    "summary": ts.summary,
                    "key_results": ts.key_results,
                    "tools_used": ts.tools_used,
                    "status": ts.status,
                }
                for ts in workspace.task_summaries
            ],
            "user_preferences": workspace.user_preferences,
        }

    def _deserialize(self, data: dict) -> WorkspaceState:
        """Convert JSON dict to WorkspaceState."""
        # Parse messages
        messages = [
            Message(
                role=msg["role"],
                content=msg["content"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
            )
            for msg in data.get("workspace_conversation", [])
        ]

        # Parse task summaries
        summaries = deque(maxlen=10)
        for ts in data.get("task_summaries", []):
            summaries.append(
                TaskSummary(
                    task_id=ts["task_id"],
                    task_description=ts["task_description"],
                    timestamp=datetime.fromisoformat(ts["timestamp"]),
                    summary=ts["summary"],
                    key_results=ts["key_results"],
                    tools_used=ts["tools_used"],
                    status=ts["status"],
                )
            )

        return WorkspaceState(
            session_id=data["session_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            workspace_conversation=messages,
            task_summaries=summaries,
            user_preferences=data.get("user_preferences", {}),
        )

    def delete(self, session_id: str) -> bool:
        """
        Delete workspace file for session.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        workspace_file = self.workspace_dir / f"{session_id}.json"
        if workspace_file.exists():
            workspace_file.unlink()
            logger.info(f"Deleted workspace file: {session_id}")
            return True
        return False

    def exists(self, session_id: str) -> bool:
        """
        Check if workspace file exists.

        Args:
            session_id: Session UUID

        Returns:
            True if exists
        """
        workspace_file = self.workspace_dir / f"{session_id}.json"
        return workspace_file.exists()

    def get_stats(self, session_id: str) -> tuple[int, int] | None:
        """
        Get workspace statistics without loading full state.

        Args:
            session_id: Session UUID

        Returns:
            Tuple of (message_count, task_count) or None if not found
        """
        workspace_file = self.workspace_dir / f"{session_id}.json"
        if not workspace_file.exists():
            return None

        try:
            with open(workspace_file) as f:
                data = json.load(f)
            message_count = len(data.get("workspace_conversation", []))
            task_count = len(data.get("task_summaries", []))
            return (message_count, task_count)
        except Exception as e:
            logger.warning(f"Failed to get workspace stats: {e}")
            return None

    def list_workspaces(self) -> list[str]:
        """
        List all workspace session IDs.

        Returns:
            List of session UUIDs
        """
        return [
            f.stem for f in self.workspace_dir.glob("*.json")
        ]
