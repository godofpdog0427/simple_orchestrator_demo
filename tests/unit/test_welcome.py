"""Unit tests for welcome screen."""

import pytest
from io import StringIO

from rich.console import Console

from orchestrator.cli.welcome import WelcomeScreen
from orchestrator.modes.models import ExecutionMode


class TestWelcomeScreen:
    """Tests for welcome screen builder."""

    @pytest.fixture
    def console(self):
        """Create test console."""
        return Console(file=StringIO(), width=80, legacy_windows=False)

    @pytest.fixture
    def welcome(self, console):
        """Create welcome screen builder."""
        return WelcomeScreen(console)

    def test_build_greeting_with_username(self, welcome):
        """Test greeting with username."""
        greeting = welcome._build_greeting("Yi")
        assert "Yi" in greeting
        assert "👋" in greeting

    def test_build_greeting_without_username(self, welcome):
        """Test greeting without username."""
        greeting = welcome._build_greeting(None)
        assert "Welcome to Orchestrator" in greeting

    def test_mode_colors(self, welcome):
        """Test mode color mapping."""
        assert welcome.MODE_COLORS[ExecutionMode.ASK] == "cyan"
        assert welcome.MODE_COLORS[ExecutionMode.PLAN] == "yellow"
        assert welcome.MODE_COLORS[ExecutionMode.EXECUTE] == "green"

    def test_get_mode_guidelines_ask(self, welcome):
        """Test ASK mode guidelines."""
        guidelines = welcome._get_mode_guidelines(ExecutionMode.ASK)
        assert "ASK Mode" in guidelines
        assert "research" in guidelines.lower()
        assert "✓" in guidelines
        assert "✗" in guidelines

    def test_get_mode_guidelines_plan(self, welcome):
        """Test PLAN mode guidelines."""
        guidelines = welcome._get_mode_guidelines(ExecutionMode.PLAN)
        assert "PLAN Mode" in guidelines
        assert "task decomposition" in guidelines.lower() or "decomposition" in guidelines.lower()

    def test_get_mode_guidelines_execute(self, welcome):
        """Test EXECUTE mode guidelines."""
        guidelines = welcome._get_mode_guidelines(ExecutionMode.EXECUTE)
        assert "EXECUTE Mode" in guidelines
        assert "all tools available" in guidelines.lower() or "tools available" in guidelines.lower()

    def test_display_welcome_basic(self, welcome, console):
        """Test basic welcome display."""
        welcome.display_welcome(ExecutionMode.ASK)
        output = console.file.getvalue()
        assert "Welcome to Orchestrator" in output
        assert "ASK" in output

    def test_display_welcome_with_username(self, welcome, console):
        """Test welcome display with username."""
        welcome.display_welcome(ExecutionMode.ASK, username="Yi")
        output = console.file.getvalue()
        assert "Yi" in output or "Welcome back" in output

    def test_display_welcome_with_session(self, welcome, console):
        """Test welcome display with session name."""
        welcome.display_welcome(
            ExecutionMode.PLAN,
            session_name="test-session"
        )
        output = console.file.getvalue()
        assert "test-session" in output

    def test_display_welcome_with_task_progress(self, welcome, console):
        """Test welcome display with task progress."""
        welcome.display_welcome(
            ExecutionMode.EXECUTE,
            task_progress=(3, 7)
        )
        output = console.file.getvalue()
        assert "3" in output and "7" in output

    def test_all_modes_have_guidelines(self, welcome):
        """Test all execution modes have guidelines."""
        for mode in ExecutionMode:
            guidelines = welcome._get_mode_guidelines(mode)
            assert len(guidelines) > 0
            assert guidelines.strip() != ""

    def test_display_welcome_three_columns(self, welcome):
        """Test welcome display has three columns with seal fact."""
        # Use wider console to see all three columns
        from io import StringIO
        wide_console = Console(file=StringIO(), width=150, legacy_windows=False)
        welcome_wide = WelcomeScreen(wide_console)

        welcome_wide.display_welcome(ExecutionMode.PLAN)
        output = wide_console.file.getvalue()

        # Should contain seal fact header
        assert "🌊 Did you know?" in output or "Did you know" in output

        # Should contain mode guidelines
        assert "Mode Guidelines" in output or "PLAN Mode" in output

        # Should contain seal emoji in fact
        assert "🦭" in output
