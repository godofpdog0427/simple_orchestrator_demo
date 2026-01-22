"""Workspace lifecycle management for compression and cleanup."""

import logging
from datetime import datetime
from pathlib import Path

from orchestrator.workspace.state import Message, WorkspaceManager, WorkspaceState
from orchestrator.workspace.summarizer import TaskSummarizer

logger = logging.getLogger(__name__)


class WorkspaceLifecycleManager:
    """Manages workspace compression and cleanup."""

    def __init__(
        self, workspace_manager: WorkspaceManager, summarizer: TaskSummarizer | None = None
    ):
        self.workspace_manager = workspace_manager
        self.summarizer = summarizer

    async def compress_workspace(self, workspace: WorkspaceState) -> None:
        """
        Compress old workspace conversation.

        If conversation > 100 messages, compress oldest 50 messages into a summary.
        """
        if len(workspace.workspace_conversation) <= 100:
            return  # No compression needed

        old_messages = workspace.workspace_conversation[:50]
        recent_messages = workspace.workspace_conversation[50:]

        # Generate summary of old conversation
        conversation_text = "\n".join(
            [
                f"{msg.role}: {msg.content if isinstance(msg.content, str) else '[Tool use]'}"
                for msg in old_messages
            ]
        )

        # For now, use simple text summary (no LLM)
        # TODO: Enhance with LLM-based summarization if summarizer available
        summary = f"[Compressed {len(old_messages)} messages from session]"

        # Replace old messages with summary message
        workspace.workspace_conversation = [
            Message(
                role="assistant",
                content=f"[Conversation summary: {summary}]",
                timestamp=old_messages[0].timestamp,
            )
        ] + recent_messages

        logger.info(
            f"Compressed workspace {workspace.session_id}: {len(old_messages)} → 1 message"
        )

    def cleanup_old_workspaces(self, days: int = 365) -> int:
        """
        Delete workspace files older than N days.

        Args:
            days: Delete workspaces older than this many days

        Returns:
            Number of workspaces deleted
        """
        count = 0
        now = datetime.now().timestamp()

        for workspace_file in self.workspace_manager.workspace_dir.glob("*.json"):
            try:
                stat = workspace_file.stat()
                age_days = (now - stat.st_mtime) / 86400

                if age_days > days:
                    workspace_file.unlink()
                    logger.info(f"Deleted old workspace: {workspace_file.name} (age: {age_days:.1f} days)")
                    count += 1
            except Exception as e:
                logger.error(f"Error deleting workspace {workspace_file.name}: {e}")

        return count
