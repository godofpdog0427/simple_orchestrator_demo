"""Unit tests for HITL approval whitelist (Phase 6D)."""

import pytest
from datetime import datetime
from collections import deque

from orchestrator.hooks.builtin.hitl import HITLHook
from orchestrator.workspace.state import WorkspaceState


class TestHITLWhitelist:
    """Tests for HITL whitelist functionality."""

    @pytest.fixture
    def workspace(self):
        """Create test workspace."""
        return WorkspaceState(
            session_id="test-session",
            created_at=datetime.now(),
            last_updated=datetime.now(),
            workspace_conversation=[],
            task_summaries=deque(maxlen=10),
            user_preferences={}
        )

    @pytest.fixture
    def hitl_hook(self, workspace):
        """Create HITLHook with workspace."""
        config = {
            "timeout": 300,
            "auto_approve_safe_tools": True,
            "prompt_format": "standard"
        }
        return HITLHook(config, workspace=workspace)

    @pytest.fixture
    def hitl_hook_no_workspace(self):
        """Create HITLHook without workspace."""
        config = {
            "timeout": 300,
            "auto_approve_safe_tools": True,
            "prompt_format": "standard"
        }
        return HITLHook(config, workspace=None)

    def test_is_whitelisted_empty(self, hitl_hook):
        """Test whitelist check with empty preferences."""
        assert hitl_hook._is_whitelisted("bash") is False
        assert hitl_hook._is_whitelisted("file_write") is False

    def test_is_whitelisted_no_workspace(self, hitl_hook_no_workspace):
        """Test whitelist check without workspace returns False."""
        assert hitl_hook_no_workspace._is_whitelisted("bash") is False

    def test_add_to_whitelist(self, hitl_hook, workspace):
        """Test adding tool to whitelist."""
        hitl_hook._add_to_whitelist("bash")

        # Verify structure
        assert "approval_whitelist" in workspace.user_preferences
        whitelist = workspace.user_preferences["approval_whitelist"]
        assert "tools" in whitelist
        tools = whitelist["tools"]
        assert len(tools) == 1
        assert tools[0]["tool_name"] == "bash"
        assert tools[0]["match_type"] == "tool_name_only"
        assert "approved_at" in tools[0]

    def test_add_to_whitelist_no_workspace(self, hitl_hook_no_workspace, capsys):
        """Test adding to whitelist without workspace logs warning."""
        hitl_hook_no_workspace._add_to_whitelist("bash")
        # Should not crash, just log warning
        # (logger.warning doesn't show in capsys, but function should complete)

    def test_is_whitelisted_after_add(self, hitl_hook):
        """Test whitelist check after adding."""
        hitl_hook._add_to_whitelist("bash")
        assert hitl_hook._is_whitelisted("bash") is True
        assert hitl_hook._is_whitelisted("file_write") is False

    def test_add_duplicate_prevented(self, hitl_hook, workspace):
        """Test that adding duplicate entries is prevented."""
        hitl_hook._add_to_whitelist("bash")
        hitl_hook._add_to_whitelist("bash")

        tools = workspace.user_preferences["approval_whitelist"]["tools"]
        assert len(tools) == 1  # No duplicate

    def test_multiple_tools_whitelisted(self, hitl_hook):
        """Test whitelisting multiple tools."""
        hitl_hook._add_to_whitelist("bash")
        hitl_hook._add_to_whitelist("file_write")
        hitl_hook._add_to_whitelist("file_delete")

        assert hitl_hook._is_whitelisted("bash") is True
        assert hitl_hook._is_whitelisted("file_write") is True
        assert hitl_hook._is_whitelisted("file_delete") is True
        assert hitl_hook._is_whitelisted("other_tool") is False

    def test_whitelist_structure(self, hitl_hook, workspace):
        """Test correct whitelist data structure."""
        hitl_hook._add_to_whitelist("bash")

        whitelist = workspace.user_preferences["approval_whitelist"]
        tools = whitelist["tools"]

        # Check structure of first entry
        entry = tools[0]
        assert "tool_name" in entry
        assert "approved_at" in entry
        assert "match_type" in entry

        # Check approved_at is valid ISO format
        datetime.fromisoformat(entry["approved_at"])  # Should not raise

    def test_whitelist_initialization(self, hitl_hook, workspace):
        """Test whitelist is properly initialized if not exists."""
        # Ensure no whitelist exists
        assert "approval_whitelist" not in workspace.user_preferences

        # Add tool
        hitl_hook._add_to_whitelist("bash")

        # Check structure was initialized
        assert "approval_whitelist" in workspace.user_preferences
        assert "tools" in workspace.user_preferences["approval_whitelist"]
        assert isinstance(workspace.user_preferences["approval_whitelist"]["tools"], list)

    def test_whitelist_across_multiple_adds(self, hitl_hook, workspace):
        """Test whitelist grows correctly with multiple adds."""
        tools_to_add = ["bash", "file_write", "file_delete", "web_fetch"]

        for tool in tools_to_add:
            hitl_hook._add_to_whitelist(tool)

        whitelist = workspace.user_preferences["approval_whitelist"]["tools"]
        assert len(whitelist) == len(tools_to_add)

        # Verify all tools are present
        whitelisted_names = {entry["tool_name"] for entry in whitelist}
        assert whitelisted_names == set(tools_to_add)

    def test_workspace_reference(self, workspace):
        """Test workspace can be set after initialization."""
        config = {"timeout": 300}
        hook = HITLHook(config, workspace=None)

        # Initially no workspace
        assert hook.workspace is None
        assert hook._is_whitelisted("bash") is False

        # Set workspace
        hook.workspace = workspace
        assert hook.workspace is workspace

        # Now can use whitelist
        hook._add_to_whitelist("bash")
        assert hook._is_whitelisted("bash") is True
