"""Unit tests for Mode Manager (Phase 6A)."""

import pytest

from orchestrator.modes.models import ExecutionMode, MODE_CONFIGS
from orchestrator.modes.manager import ModeManager


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_execution_mode_values(self):
        """Test ExecutionMode has correct values."""
        assert ExecutionMode.ASK.value == "ask"
        assert ExecutionMode.PLAN.value == "plan"
        assert ExecutionMode.EXECUTE.value == "execute"

    def test_execution_mode_from_string(self):
        """Test creating ExecutionMode from string."""
        assert ExecutionMode("ask") == ExecutionMode.ASK
        assert ExecutionMode("plan") == ExecutionMode.PLAN
        assert ExecutionMode("execute") == ExecutionMode.EXECUTE


class TestModeConfigs:
    """Tests for MODE_CONFIGS."""

    def test_all_modes_have_config(self):
        """Test all execution modes have configuration."""
        for mode in ExecutionMode:
            assert mode in MODE_CONFIGS

    def test_ask_mode_config(self):
        """Test ASK mode configuration."""
        config = MODE_CONFIGS[ExecutionMode.ASK]
        assert config.mode == ExecutionMode.ASK
        assert "file_read" in config.allowed_tools
        assert "web_fetch" in config.allowed_tools
        assert "bash" in config.allowed_tools  # Phase 6A++: bash allowed for read-only operations
        assert "todo_list" in config.allowed_tools
        assert "file_write" not in config.allowed_tools
        assert len(config.system_prompt_suffix) > 0

    def test_plan_mode_config(self):
        """Test PLAN mode configuration."""
        config = MODE_CONFIGS[ExecutionMode.PLAN]
        assert config.mode == ExecutionMode.PLAN
        assert "file_read" in config.allowed_tools
        assert "web_fetch" in config.allowed_tools
        assert "bash" not in config.allowed_tools  # Phase 6A+++: bash removed (caused infinite loops)
        assert "task_decompose" in config.allowed_tools
        assert "todo_list" not in config.allowed_tools  # Phase 6A+: Removed to avoid interference
        assert "subagent_spawn" not in config.allowed_tools
        assert len(config.system_prompt_suffix) > 0

    def test_execute_mode_config(self):
        """Test EXECUTE mode configuration."""
        config = MODE_CONFIGS[ExecutionMode.EXECUTE]
        assert config.mode == ExecutionMode.EXECUTE
        assert config.allowed_tools == []  # Empty means all allowed
        assert len(config.system_prompt_suffix) > 0


class TestModeManager:
    """Tests for ModeManager."""

    def test_initialization_default(self):
        """Test ModeManager initializes with default mode."""
        manager = ModeManager()
        assert manager.current_mode == ExecutionMode.EXECUTE

    def test_initialization_custom_mode(self):
        """Test ModeManager initializes with custom mode."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)
        assert manager.current_mode == ExecutionMode.ASK

    def test_set_mode(self):
        """Test setting execution mode."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)
        assert manager.current_mode == ExecutionMode.ASK

        manager.set_mode(ExecutionMode.PLAN)
        assert manager.current_mode == ExecutionMode.PLAN

        manager.set_mode(ExecutionMode.EXECUTE)
        assert manager.current_mode == ExecutionMode.EXECUTE

    def test_get_mode_config(self):
        """Test getting current mode configuration."""
        manager = ModeManager(initial_mode=ExecutionMode.PLAN)
        config = manager.get_mode_config()
        assert config.mode == ExecutionMode.PLAN
        assert config == MODE_CONFIGS[ExecutionMode.PLAN]

    def test_is_tool_allowed_ask_mode(self):
        """Test tool filtering in ASK mode."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)

        # Allowed tools
        assert manager.is_tool_allowed("file_read") is True
        assert manager.is_tool_allowed("web_fetch") is True
        assert manager.is_tool_allowed("bash") is True  # Phase 6A++: bash allowed for read-only operations
        assert manager.is_tool_allowed("todo_list") is True

        # Blocked tools
        assert manager.is_tool_allowed("file_write") is False
        assert manager.is_tool_allowed("file_delete") is False
        assert manager.is_tool_allowed("subagent_spawn") is False
        assert manager.is_tool_allowed("task_decompose") is False

    def test_is_tool_allowed_plan_mode(self):
        """Test tool filtering in PLAN mode."""
        manager = ModeManager(initial_mode=ExecutionMode.PLAN)

        # Allowed tools
        assert manager.is_tool_allowed("file_read") is True
        assert manager.is_tool_allowed("web_fetch") is True
        assert manager.is_tool_allowed("bash") is False  # Phase 6A+++: bash removed (caused infinite loops)
        assert manager.is_tool_allowed("task_decompose") is True

        # Blocked tools (Note: todo_list was removed from PLAN mode in Phase 6A+)
        assert manager.is_tool_allowed("file_write") is False
        assert manager.is_tool_allowed("file_delete") is False
        assert manager.is_tool_allowed("subagent_spawn") is False

    def test_is_tool_allowed_execute_mode(self):
        """Test all tools allowed in EXECUTE mode except blocked ones."""
        manager = ModeManager(initial_mode=ExecutionMode.EXECUTE)

        # Most tools should be allowed
        assert manager.is_tool_allowed("bash") is True
        assert manager.is_tool_allowed("file_read") is True
        assert manager.is_tool_allowed("file_write") is True
        assert manager.is_tool_allowed("file_delete") is True
        assert manager.is_tool_allowed("subagent_spawn") is True
        assert manager.is_tool_allowed("todo_list") is True
        assert manager.is_tool_allowed("web_fetch") is True
        assert manager.is_tool_allowed("any_custom_tool") is True

        # task_decompose should be blocked in EXECUTE mode
        assert manager.is_tool_allowed("task_decompose") is False

    def test_filter_tool_schemas_ask_mode(self):
        """Test filtering tool schemas in ASK mode."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)

        all_schemas = [
            {"name": "file_read", "description": "Read files"},
            {"name": "bash", "description": "Execute bash"},
            {"name": "web_fetch", "description": "Fetch web content"},
            {"name": "file_write", "description": "Write files"},
            {"name": "todo_list", "description": "Manage TODOs"},
        ]

        filtered = manager.filter_tool_schemas(all_schemas)

        # Should only include allowed tools (Phase 6A++: bash now allowed)
        filtered_names = {schema["name"] for schema in filtered}
        assert "file_read" in filtered_names
        assert "web_fetch" in filtered_names
        assert "todo_list" in filtered_names
        assert "bash" in filtered_names  # Phase 6A++: bash allowed for read-only operations
        assert "file_write" not in filtered_names
        assert len(filtered) == 4  # file_read, web_fetch, bash, todo_list

    def test_filter_tool_schemas_execute_mode(self):
        """Test all tools pass through in EXECUTE mode."""
        manager = ModeManager(initial_mode=ExecutionMode.EXECUTE)

        all_schemas = [
            {"name": "file_read", "description": "Read files"},
            {"name": "bash", "description": "Execute bash"},
            {"name": "file_write", "description": "Write files"},
        ]

        filtered = manager.filter_tool_schemas(all_schemas)

        # Should include all tools
        assert len(filtered) == len(all_schemas)
        assert filtered == all_schemas

    def test_get_mode_prompt_suffix(self):
        """Test getting mode-specific prompt suffix."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)
        prompt = manager.get_mode_prompt_suffix()

        # Should contain mode-specific instructions
        assert "ASK" in prompt
        assert "Read-Only" in prompt
        assert len(prompt) > 100  # Substantial instructions

    def test_mode_switching_updates_config(self):
        """Test mode switching updates configuration."""
        manager = ModeManager(initial_mode=ExecutionMode.ASK)

        # Initial state
        assert manager.current_mode == ExecutionMode.ASK
        assert manager.mode_config == MODE_CONFIGS[ExecutionMode.ASK]

        # Switch to PLAN
        manager.set_mode(ExecutionMode.PLAN)
        assert manager.current_mode == ExecutionMode.PLAN
        assert manager.mode_config == MODE_CONFIGS[ExecutionMode.PLAN]

        # Switch to EXECUTE
        manager.set_mode(ExecutionMode.EXECUTE)
        assert manager.current_mode == ExecutionMode.EXECUTE
        assert manager.mode_config == MODE_CONFIGS[ExecutionMode.EXECUTE]

    def test_set_mode_same_mode(self):
        """Test setting same mode is idempotent."""
        manager = ModeManager(initial_mode=ExecutionMode.PLAN)

        # Set to same mode
        manager.set_mode(ExecutionMode.PLAN)

        # Should remain in PLAN mode
        assert manager.current_mode == ExecutionMode.PLAN
        assert manager.mode_config == MODE_CONFIGS[ExecutionMode.PLAN]

    def test_blocked_tools_in_execute_mode(self):
        """Test that task_decompose is blocked in EXECUTE mode."""
        manager = ModeManager(initial_mode=ExecutionMode.EXECUTE)

        all_schemas = [
            {"name": "bash", "description": "Execute bash"},
            {"name": "file_read", "description": "Read files"},
            {"name": "task_decompose", "description": "Decompose tasks"},
            {"name": "todo_list", "description": "Manage TODOs"},
        ]

        filtered = manager.filter_tool_schemas(all_schemas)

        # task_decompose should be filtered out
        filtered_names = {schema["name"] for schema in filtered}
        assert "bash" in filtered_names
        assert "file_read" in filtered_names
        assert "todo_list" in filtered_names
        assert "task_decompose" not in filtered_names
        assert len(filtered) == 3  # All except task_decompose

    def test_blocked_tools_field_in_mode_config(self):
        """Test ModeConfig has blocked_tools field."""
        ask_config = MODE_CONFIGS[ExecutionMode.ASK]
        plan_config = MODE_CONFIGS[ExecutionMode.PLAN]
        execute_config = MODE_CONFIGS[ExecutionMode.EXECUTE]

        # ASK and PLAN should have no blocked tools
        assert ask_config.blocked_tools == []
        assert plan_config.blocked_tools == []

        # EXECUTE should have task_decompose blocked
        assert "task_decompose" in execute_config.blocked_tools
