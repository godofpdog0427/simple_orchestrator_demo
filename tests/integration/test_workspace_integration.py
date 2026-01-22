"""Integration tests for workspace module with real LLM (Phase 5B)."""

import os
import tempfile
from datetime import datetime

import pytest

from orchestrator.llm.client import LLMClient
from orchestrator.tasks.models import Task, TaskStatus
from orchestrator.workspace.lifecycle import WorkspaceLifecycleManager
from orchestrator.workspace.state import TaskSummary, WorkspaceManager, WorkspaceState
from orchestrator.workspace.summarizer import TaskSummarizer


@pytest.fixture
def llm_client():
    """Create LLM client for testing."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")

    config = {
        "llm": {
            "provider": "anthropic",
            "anthropic": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 500,
                "temperature": 0.3,
                "api_key_env": "ANTHROPIC_API_KEY",
            }
        }
    }

    return LLMClient(config)


@pytest.fixture
def temp_workspace_dir():
    """Create temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


class TestTaskSummarizerIntegration:
    """Integration tests for TaskSummarizer with real LLM."""

    @pytest.mark.asyncio
    async def test_generate_summary(self, llm_client):
        """Test generating summary with real LLM."""
        summarizer = TaskSummarizer(llm_client)

        # Create mock task
        task = Task(
            id="task_123",
            title="Fix authentication bug",
            description="Fix the login validation bug that allows empty passwords",
            status=TaskStatus.COMPLETED
        )

        # Create mock conversation
        conversation = [
            {
                "role": "user",
                "content": "Fix the login validation bug"
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll fix the login validation to reject empty passwords."},
                    {"type": "tool_use", "id": "tool_1", "name": "file_read", "input": {"path": "auth.py"}},
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_1", "content": "def login(username, password):\n    if not username:\n        return False\n    return True"}
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I see the bug - password validation is missing. Let me fix it."},
                    {"type": "tool_use", "id": "tool_2", "name": "file_write", "input": {"path": "auth.py", "content": "..."}},
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool_2", "content": "File written successfully"}
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Fixed! Added password length validation."}
                ]
            }
        ]

        # Generate summary
        summary = await summarizer.generate_summary(task, conversation)

        # Verify summary
        assert isinstance(summary, str)
        assert len(summary) > 10  # Should be meaningful
        assert len(summary) < 500  # Should be concise

        # Summary should mention key aspects
        # (Note: LLM responses can vary, so we check for general quality)
        print(f"Generated summary: {summary}")

    @pytest.mark.asyncio
    async def test_extract_tools_used(self, llm_client):
        """Test extracting tools from conversation."""
        summarizer = TaskSummarizer(llm_client)

        conversation = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Let me read the file."},
                    {"type": "tool_use", "id": "1", "name": "file_read", "input": {}},
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "2", "name": "bash", "input": {}},
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "3", "name": "file_write", "input": {}},
                ]
            }
        ]

        tools = summarizer._extract_tools_used(conversation)

        assert "file_read" in tools
        assert "bash" in tools
        assert "file_write" in tools
        assert len(tools) == 3

    @pytest.mark.asyncio
    async def test_extract_reasoning(self, llm_client):
        """Test extracting reasoning from conversation."""
        summarizer = TaskSummarizer(llm_client)

        conversation = [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "First, I'll analyze the problem."},
                    {"type": "tool_use", "id": "1", "name": "file_read", "input": {}},
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Now I'll implement the fix."},
                ]
            },
            {
                "role": "assistant",
                "content": "Finally, I'll verify the solution."  # String content
            }
        ]

        reasoning = summarizer._extract_reasoning(conversation)

        assert "First, I'll analyze the problem." in reasoning
        assert "Now I'll implement the fix." in reasoning
        assert "Finally, I'll verify the solution." in reasoning


class TestWorkspaceIntegration:
    """Integration tests for complete workspace workflow."""

    @pytest.mark.asyncio
    async def test_full_workspace_workflow(self, llm_client, temp_workspace_dir):
        """Test complete workflow: create task, summarize, persist, load."""
        # Initialize components
        manager = WorkspaceManager(temp_workspace_dir)
        summarizer = TaskSummarizer(llm_client)
        workspace = manager.load_or_create("test_session")

        # Simulate task execution
        task = Task(
            id="task_1",
            title="Add user authentication",
            description="Implement JWT-based authentication for the API",
            status=TaskStatus.COMPLETED
        )

        conversation = [
            {"role": "user", "content": "Implement JWT authentication"},
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "I'll create an authentication module with JWT tokens."},
                    {"type": "tool_use", "id": "1", "name": "file_write", "input": {"path": "auth.py"}},
                ]
            },
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "1", "content": "File created"}
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Authentication module created successfully."}
                ]
            }
        ]

        # Generate summary
        summary_text = await summarizer.generate_summary(task, conversation)
        tools_used = summarizer._extract_tools_used(conversation)

        # Create task summary
        task_summary = TaskSummary(
            task_id=task.id,
            task_description=task.description,
            timestamp=datetime.now(),
            summary=summary_text,
            key_results=["Authentication module created"],
            tools_used=tools_used,
            status="COMPLETED"
        )

        # Add to workspace
        workspace.add_task_summary(task_summary)
        workspace.add_user_message("Implement JWT authentication")
        workspace.add_assistant_message("Authentication module created successfully")

        # Save workspace
        manager.save(workspace)

        # Load workspace in new instance
        loaded_workspace = manager.load_or_create("test_session")

        # Verify persistence
        assert loaded_workspace.session_id == "test_session"
        assert len(loaded_workspace.task_summaries) == 1
        assert loaded_workspace.task_summaries[0].task_id == "task_1"
        assert len(loaded_workspace.workspace_conversation) == 2

        # Verify summary quality
        summary = loaded_workspace.task_summaries[0]
        assert len(summary.summary) > 10
        assert "file_write" in summary.tools_used

    @pytest.mark.asyncio
    async def test_context_injection(self, llm_client, temp_workspace_dir):
        """Test that workspace context is properly formatted for injection."""
        manager = WorkspaceManager(temp_workspace_dir)
        workspace = manager.load_or_create("test_session")

        # Add multiple task summaries
        for i in range(5):
            summary = TaskSummary(
                task_id=f"task_{i}",
                task_description=f"Task {i}: Database migration step {i}",
                timestamp=datetime.now(),
                summary=f"Completed migration step {i}",
                key_results=[f"Result {i}"],
                tools_used=["bash"],
                status="COMPLETED"
            )
            workspace.add_task_summary(summary)

        # Add conversation
        workspace.add_user_message("Migrate the database")
        workspace.add_assistant_message("Starting migration process")

        # Get recent context (simulates what orchestrator does)
        recent_summaries = list(workspace.task_summaries)[-3:]
        recent_conversation = workspace.get_recent_context(max_messages=2)

        # Verify
        assert len(recent_summaries) == 3
        assert recent_summaries[0].task_id == "task_2"
        assert len(recent_conversation) == 2

        # Test keyword search
        results = workspace.search_summaries(["database", "migration"])
        assert len(results) == 5  # All tasks match

    @pytest.mark.asyncio
    async def test_workspace_compression(self, llm_client, temp_workspace_dir):
        """Test workspace compression with lifecycle manager."""
        manager = WorkspaceManager(temp_workspace_dir)
        lifecycle = WorkspaceLifecycleManager(manager, None)
        workspace = manager.load_or_create("test_session")

        # Add 110 messages to trigger compression
        for i in range(110):
            role = "user" if i % 2 == 0 else "assistant"
            if role == "user":
                workspace.add_user_message(f"Message {i}")
            else:
                workspace.add_assistant_message(f"Response {i}")

        # Compress
        await lifecycle.compress_workspace(workspace)

        # Verify compression
        assert len(workspace.workspace_conversation) < 110
        assert "[Compressed" in workspace.workspace_conversation[0].content

        # Save and reload
        manager.save(workspace)
        loaded = manager.load_or_create("test_session")

        # Verify persistence of compressed workspace
        assert len(loaded.workspace_conversation) < 110


class TestWorkspaceCLIIntegration:
    """Integration tests for workspace CLI commands."""

    def test_workspace_list_empty(self, temp_workspace_dir):
        """Test listing workspaces when none exist."""
        manager = WorkspaceManager(temp_workspace_dir)

        # List should be empty
        workspaces = list(manager.workspace_dir.glob("*.json"))
        assert len(workspaces) == 0

    def test_workspace_lifecycle(self, temp_workspace_dir):
        """Test complete workspace lifecycle: create, save, list, delete."""
        manager = WorkspaceManager(temp_workspace_dir)

        # Create workspaces
        ws1 = manager.load_or_create("session_1")
        ws2 = manager.load_or_create("session_2")

        ws1.add_user_message("Test 1")
        ws2.add_user_message("Test 2")

        manager.save(ws1)
        manager.save(ws2)

        # List workspaces
        workspaces = list(manager.workspace_dir.glob("*.json"))
        assert len(workspaces) == 2

        # Delete one
        (manager.workspace_dir / "session_1.json").unlink()

        # Verify deletion
        workspaces = list(manager.workspace_dir.glob("*.json"))
        assert len(workspaces) == 1
        assert not (manager.workspace_dir / "session_1.json").exists()
        assert (manager.workspace_dir / "session_2.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
