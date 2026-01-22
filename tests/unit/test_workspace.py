"""Unit tests for workspace module (Phase 5B)."""

import json
import tempfile
from collections import deque
from datetime import datetime
from pathlib import Path

import pytest

from orchestrator.workspace.state import (
    Message,
    TaskSummary,
    WorkspaceManager,
    WorkspaceState,
)
from orchestrator.workspace.lifecycle import WorkspaceLifecycleManager


class TestMessage:
    """Test Message model."""

    def test_create_message(self):
        """Test creating a message."""
        msg = Message(
            role="user",
            content="Hello, world!",
            timestamp=datetime.now()
        )

        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert isinstance(msg.timestamp, datetime)

    def test_message_with_tool_content(self):
        """Test message with tool use content."""
        msg = Message(
            role="assistant",
            content=[{"type": "tool_use", "name": "bash"}],
            timestamp=datetime.now()
        )

        assert msg.role == "assistant"
        assert isinstance(msg.content, list)
        assert msg.content[0]["type"] == "tool_use"


class TestTaskSummary:
    """Test TaskSummary model."""

    def test_create_task_summary(self):
        """Test creating a task summary."""
        summary = TaskSummary(
            task_id="task_123",
            task_description="Test task",
            timestamp=datetime.now(),
            summary="Task completed successfully",
            key_results=["Result 1", "Result 2"],
            tools_used=["bash", "file_read"],
            status="COMPLETED"
        )

        assert summary.task_id == "task_123"
        assert summary.task_description == "Test task"
        assert summary.summary == "Task completed successfully"
        assert len(summary.key_results) == 2
        assert len(summary.tools_used) == 2
        assert summary.status == "COMPLETED"


class TestWorkspaceState:
    """Test WorkspaceState model."""

    def test_create_workspace_state(self):
        """Test creating a workspace state."""
        workspace = WorkspaceState(
            session_id="test_session",
            created_at=datetime.now(),
            last_updated=datetime.now(),
            workspace_conversation=[],
            task_summaries=deque(maxlen=10),
            user_preferences={}
        )

        assert workspace.session_id == "test_session"
        assert len(workspace.workspace_conversation) == 0
        assert len(workspace.task_summaries) == 0
        assert len(workspace.user_preferences) == 0

    def test_add_user_message(self):
        """Test adding user message."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        workspace.add_user_message("Hello!")

        assert len(workspace.workspace_conversation) == 1
        assert workspace.workspace_conversation[0].role == "user"
        assert workspace.workspace_conversation[0].content == "Hello!"

    def test_add_assistant_message(self):
        """Test adding assistant message."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        workspace.add_assistant_message("Hi there!")

        assert len(workspace.workspace_conversation) == 1
        assert workspace.workspace_conversation[0].role == "assistant"
        assert workspace.workspace_conversation[0].content == "Hi there!"

    def test_add_task_summary(self):
        """Test adding task summary."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        summary = TaskSummary(
            task_id="task_1",
            task_description="Test task",
            timestamp=datetime.now(),
            summary="Completed",
            key_results=[],
            tools_used=[],
            status="COMPLETED"
        )

        workspace.add_task_summary(summary)

        assert len(workspace.task_summaries) == 1
        assert workspace.task_summaries[0].task_id == "task_1"

    def test_task_summaries_maxlen(self):
        """Test that task_summaries deque respects maxlen."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        # Add 15 summaries (maxlen is 10)
        for i in range(15):
            summary = TaskSummary(
                task_id=f"task_{i}",
                task_description=f"Task {i}",
                timestamp=datetime.now(),
                summary=f"Summary {i}",
                key_results=[],
                tools_used=[],
                status="COMPLETED"
            )
            workspace.add_task_summary(summary)

        # Should only keep last 10
        assert len(workspace.task_summaries) == 10
        assert workspace.task_summaries[0].task_id == "task_5"
        assert workspace.task_summaries[-1].task_id == "task_14"

    def test_get_recent_context(self):
        """Test getting recent conversation context."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        # Add 30 messages
        for i in range(30):
            role = "user" if i % 2 == 0 else "assistant"
            workspace.workspace_conversation.append(
                Message(role=role, content=f"Message {i}", timestamp=datetime.now())
            )

        # Get recent 10 messages
        recent = workspace.get_recent_context(max_messages=10)

        assert len(recent) == 10
        assert recent[0].content == "Message 20"
        assert recent[-1].content == "Message 29"

    def test_search_summaries(self):
        """Test keyword search in task summaries."""
        workspace = WorkspaceState(
            session_id="test",
            created_at=datetime.now(),
            last_updated=datetime.now()
        )

        # Add summaries with different keywords
        summaries_data = [
            ("task_1", "Fix authentication bug", "Fixed login validation"),
            ("task_2", "Update database schema", "Added user table"),
            ("task_3", "Improve authentication flow", "Enhanced security"),
        ]

        for task_id, desc, summary in summaries_data:
            ts = TaskSummary(
                task_id=task_id,
                task_description=desc,
                timestamp=datetime.now(),
                summary=summary,
                key_results=[],
                tools_used=[],
                status="COMPLETED"
            )
            workspace.add_task_summary(ts)

        # Search for "authentication"
        results = workspace.search_summaries(["authentication"])

        assert len(results) == 2
        assert results[0].task_id in ["task_1", "task_3"]
        assert results[1].task_id in ["task_1", "task_3"]

        # Search for "database"
        results = workspace.search_summaries(["database"])

        assert len(results) == 1
        assert results[0].task_id == "task_2"


class TestWorkspaceManager:
    """Test WorkspaceManager."""

    def test_load_or_create_new_workspace(self):
        """Test creating a new workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            workspace = manager.load_or_create("test_session")

            assert workspace.session_id == "test_session"
            assert len(workspace.workspace_conversation) == 0
            assert len(workspace.task_summaries) == 0

    def test_save_and_load_workspace(self):
        """Test saving and loading workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            # Create and save workspace
            workspace = manager.load_or_create("test_session")
            workspace.add_user_message("Hello!")
            workspace.add_assistant_message("Hi!")

            summary = TaskSummary(
                task_id="task_1",
                task_description="Test",
                timestamp=datetime.now(),
                summary="Done",
                key_results=["R1"],
                tools_used=["bash"],
                status="COMPLETED"
            )
            workspace.add_task_summary(summary)

            manager.save(workspace)

            # Load workspace
            loaded = manager.load_or_create("test_session")

            assert loaded.session_id == "test_session"
            assert len(loaded.workspace_conversation) == 2
            assert loaded.workspace_conversation[0].role == "user"
            assert loaded.workspace_conversation[0].content == "Hello!"
            assert loaded.workspace_conversation[1].role == "assistant"
            assert loaded.workspace_conversation[1].content == "Hi!"
            assert len(loaded.task_summaries) == 1
            assert loaded.task_summaries[0].task_id == "task_1"

    def test_serialization(self):
        """Test workspace serialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            workspace = manager.load_or_create("test")
            workspace.add_user_message("Test message")

            # Serialize
            data = manager._serialize(workspace)

            assert data["session_id"] == "test"
            assert "created_at" in data
            assert "workspace_conversation" in data
            assert len(data["workspace_conversation"]) == 1
            assert data["workspace_conversation"][0]["role"] == "user"
            assert data["workspace_conversation"][0]["content"] == "Test message"

    def test_deserialization(self):
        """Test workspace deserialization."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)

            # Create test data
            now = datetime.now()
            data = {
                "session_id": "test",
                "created_at": now.isoformat(),
                "last_updated": now.isoformat(),
                "workspace_conversation": [
                    {
                        "role": "user",
                        "content": "Hello",
                        "timestamp": now.isoformat()
                    }
                ],
                "task_summaries": [
                    {
                        "task_id": "task_1",
                        "task_description": "Test",
                        "timestamp": now.isoformat(),
                        "summary": "Done",
                        "key_results": ["R1"],
                        "tools_used": ["bash"],
                        "status": "COMPLETED"
                    }
                ],
                "user_preferences": {"theme": "dark"}
            }

            # Deserialize
            workspace = manager._deserialize(data)

            assert workspace.session_id == "test"
            assert len(workspace.workspace_conversation) == 1
            assert workspace.workspace_conversation[0].role == "user"
            assert len(workspace.task_summaries) == 1
            assert workspace.task_summaries[0].task_id == "task_1"
            assert workspace.user_preferences == {"theme": "dark"}

    def test_workspace_file_created(self):
        """Test that workspace file is created in correct location."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            workspace = manager.load_or_create("test_session")
            manager.save(workspace)

            workspace_file = Path(tmpdir) / "test_session.json"
            assert workspace_file.exists()

            # Verify JSON content
            with open(workspace_file) as f:
                data = json.load(f)
                assert data["session_id"] == "test_session"


class TestWorkspaceLifecycleManager:
    """Test WorkspaceLifecycleManager."""

    @pytest.mark.asyncio
    async def test_compress_workspace(self):
        """Test workspace conversation compression."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            lifecycle = WorkspaceLifecycleManager(manager, None)

            workspace = manager.load_or_create("test")

            # Add 110 messages (exceeds 100 threshold)
            for i in range(110):
                role = "user" if i % 2 == 0 else "assistant"
                workspace.workspace_conversation.append(
                    Message(role=role, content=f"Message {i}", timestamp=datetime.now())
                )

            # Compress
            await lifecycle.compress_workspace(workspace)

            # Should have 1 summary message + 60 recent messages = 61 total
            assert len(workspace.workspace_conversation) == 61
            # First message should be compression summary
            assert "[Compressed" in workspace.workspace_conversation[0].content
            assert workspace.workspace_conversation[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_no_compression_if_under_threshold(self):
        """Test that compression doesn't happen if under threshold."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            lifecycle = WorkspaceLifecycleManager(manager, None)

            workspace = manager.load_or_create("test")

            # Add 50 messages (under 100 threshold)
            for i in range(50):
                role = "user" if i % 2 == 0 else "assistant"
                workspace.workspace_conversation.append(
                    Message(role=role, content=f"Message {i}", timestamp=datetime.now())
                )

            # Compress
            await lifecycle.compress_workspace(workspace)

            # Should remain unchanged
            assert len(workspace.workspace_conversation) == 50

    def test_cleanup_old_workspaces(self):
        """Test cleanup of old workspace files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = WorkspaceManager(tmpdir)
            lifecycle = WorkspaceLifecycleManager(manager, None)

            # Create workspace files
            workspace1 = manager.load_or_create("recent")
            workspace2 = manager.load_or_create("old")

            manager.save(workspace1)
            manager.save(workspace2)

            # Get file path for old workspace
            old_file = Path(tmpdir) / "old.json"

            # Modify timestamp to make it old (simulate old file)
            import os
            import time

            # Set modification time to 400 days ago
            old_time = time.time() - (400 * 24 * 60 * 60)
            os.utime(old_file, (old_time, old_time))

            # Cleanup workspaces older than 365 days
            count = lifecycle.cleanup_old_workspaces(days=365)

            # Should have deleted 1 workspace
            assert count == 1

            # Verify files
            assert not old_file.exists()
            assert (Path(tmpdir) / "recent.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
