"""Unit tests for activity indicator components."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from rich.console import Console

from orchestrator.display_activity import ActivityIndicator, ToolActivityIndicator


class TestActivityIndicator:
    """Test ActivityIndicator class."""

    def test_init_default_values(self):
        """Test default initialization values."""
        indicator = ActivityIndicator()
        assert indicator.spinner_name == "dots"
        assert indicator.style == "cyan"
        assert indicator.enabled is True
        assert indicator.is_running is False

    def test_init_custom_values(self):
        """Test custom initialization values."""
        console = Console()
        indicator = ActivityIndicator(
            console=console,
            spinner_name="line",
            style="green",
            enabled=False,
        )
        assert indicator.console is console
        assert indicator.spinner_name == "line"
        assert indicator.style == "green"
        assert indicator.enabled is False

    def test_init_invalid_spinner_name(self):
        """Test fallback to default spinner for invalid name."""
        indicator = ActivityIndicator(spinner_name="invalid_spinner")
        # Should fallback to "dots"
        assert indicator.spinner_name == "dots"

    def test_spinner_styles_list(self):
        """Test that SPINNER_STYLES is defined."""
        assert "dots" in ActivityIndicator.SPINNER_STYLES
        assert "line" in ActivityIndicator.SPINNER_STYLES
        assert "arc" in ActivityIndicator.SPINNER_STYLES
        assert "circle" in ActivityIndicator.SPINNER_STYLES

    @pytest.mark.asyncio
    async def test_show_disabled(self):
        """Test show() does nothing when disabled."""
        indicator = ActivityIndicator(enabled=False)

        async with indicator.show("Test message"):
            # Should not have started Live
            assert indicator._live is None
            assert indicator.is_running is False

    @pytest.mark.asyncio
    async def test_show_context_manager(self):
        """Test show() as async context manager."""
        indicator = ActivityIndicator(enabled=True)

        # Mock the Live object
        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            async with indicator.show("Test message"):
                # Verify Live was started
                mock_live.start.assert_called_once()
                assert indicator.is_running is True

            # Verify Live was stopped
            mock_live.stop.assert_called_once()
            assert indicator.is_running is False

    def test_show_sync_disabled(self):
        """Test show_sync() does nothing when disabled."""
        indicator = ActivityIndicator(enabled=False)

        with indicator.show_sync("Test message"):
            assert indicator._live is None
            assert indicator.is_running is False

    def test_show_sync_context_manager(self):
        """Test show_sync() as sync context manager."""
        indicator = ActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            with indicator.show_sync("Test message"):
                mock_live.start.assert_called_once()
                assert indicator.is_running is True

            mock_live.stop.assert_called_once()
            assert indicator.is_running is False

    def test_start_stop_manual_control(self):
        """Test manual start/stop control."""
        indicator = ActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            indicator.start("Test message")
            mock_live.start.assert_called_once()
            assert indicator.is_running is True

            indicator.stop()
            mock_live.stop.assert_called_once()
            assert indicator.is_running is False

    def test_start_disabled(self):
        """Test start() does nothing when disabled."""
        indicator = ActivityIndicator(enabled=False)
        indicator.start("Test message")
        assert indicator._live is None
        assert indicator.is_running is False

    def test_start_already_running_updates_message(self):
        """Test start() updates message when already running."""
        indicator = ActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            indicator.start("First message")
            assert indicator._message == "First message"

            # Start again should update message
            indicator.start("Second message")
            # Should have called update on the existing live
            assert indicator._message == "Second message"

            indicator.stop()

    def test_update_message_while_running(self):
        """Test update_message() while indicator is running."""
        indicator = ActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            indicator.start("Initial message")
            indicator.update_message("Updated message")

            assert indicator._message == "Updated message"
            mock_live.update.assert_called()

            indicator.stop()

    def test_update_message_not_running(self):
        """Test update_message() does nothing when not running."""
        indicator = ActivityIndicator(enabled=True)
        indicator.update_message("Should not update")
        # Should not raise, just do nothing
        assert indicator._message == ""


class TestToolActivityIndicator:
    """Test ToolActivityIndicator class."""

    def test_inherits_from_activity_indicator(self):
        """Test that ToolActivityIndicator inherits from ActivityIndicator."""
        indicator = ToolActivityIndicator()
        assert isinstance(indicator, ActivityIndicator)

    def test_format_tool_message_bash(self):
        """Test message formatting for bash tool."""
        indicator = ToolActivityIndicator()

        # Short command
        msg = indicator.format_tool_message("bash", {"command": "ls -la"})
        assert msg == "Running: ls -la"

        # Long command (truncated)
        long_cmd = "echo " + "x" * 100
        msg = indicator.format_tool_message("bash", {"command": long_cmd})
        assert len(msg) <= 50  # Should be truncated
        assert "..." in msg

    def test_format_tool_message_file_read(self):
        """Test message formatting for file_read tool."""
        indicator = ToolActivityIndicator()

        msg = indicator.format_tool_message(
            "file_read", {"path": "/home/user/project/file.py"}
        )
        assert msg == "Reading: file.py"

    def test_format_tool_message_file_write(self):
        """Test message formatting for file_write tool."""
        indicator = ToolActivityIndicator()

        msg = indicator.format_tool_message(
            "file_write", {"path": "/tmp/output.txt"}
        )
        assert msg == "Writing: output.txt"

    def test_format_tool_message_web_fetch(self):
        """Test message formatting for web_fetch tool."""
        indicator = ToolActivityIndicator()

        msg = indicator.format_tool_message(
            "web_fetch", {"url": "https://example.com/api/data"}
        )
        assert msg == "Fetching: example.com"

    def test_format_tool_message_unknown_tool(self):
        """Test message formatting for unknown tool."""
        indicator = ToolActivityIndicator()

        msg = indicator.format_tool_message("unknown_tool", {})
        assert msg == "Executing unknown_tool..."

    def test_format_tool_message_no_args(self):
        """Test message formatting with no arguments."""
        indicator = ToolActivityIndicator()

        msg = indicator.format_tool_message("bash", None)
        assert msg == "Executing bash..."

    @pytest.mark.asyncio
    async def test_show_tool_context_manager(self):
        """Test show_tool() as async context manager."""
        indicator = ToolActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live

            async with indicator.show_tool("bash", "Running command"):
                mock_live.start.assert_called_once()
                assert indicator.is_running is True

            mock_live.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_show_tool_with_timeout(self):
        """Test show_tool() with timeout parameter."""
        indicator = ToolActivityIndicator(enabled=True)

        with patch("orchestrator.display_activity.Live") as mock_live_class:
            mock_live = MagicMock()
            mock_live_class.return_value = mock_live
            with patch.object(indicator, "show") as mock_show:
                mock_show.return_value.__aenter__ = AsyncMock()
                mock_show.return_value.__aexit__ = AsyncMock()

                async with indicator.show_tool("bash", timeout=30):
                    # Verify message includes timeout
                    call_args = mock_show.call_args[0][0]
                    assert "timeout: 30s" in call_args


class TestStreamingDisplayManagerActivity:
    """Test activity indicator integration in StreamingDisplayManager."""

    def test_init_with_activity_settings(self):
        """Test StreamingDisplayManager initialization with activity settings."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(
            activity_enabled=True,
            spinner_style="line",
            spinner_color="green",
        )

        assert display._activity_enabled is True
        assert display._activity_indicator.spinner_name == "line"
        assert display._activity_indicator.style == "green"

    def test_init_activity_disabled(self):
        """Test StreamingDisplayManager with activity disabled."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(activity_enabled=False)
        assert display._activity_enabled is False
        assert display._activity_indicator.enabled is False

    @pytest.mark.asyncio
    async def test_show_activity_disabled(self):
        """Test show_activity() when activity is disabled."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(activity_enabled=False)

        async with display.show_activity("Test"):
            # Should not start any indicator
            assert not display._activity_indicator.is_running

    @pytest.mark.asyncio
    async def test_show_tool_activity(self):
        """Test show_tool_activity() context manager."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(activity_enabled=True)

        with patch.object(
            display._activity_indicator, "show"
        ) as mock_show:
            mock_show.return_value.__aenter__ = AsyncMock()
            mock_show.return_value.__aexit__ = AsyncMock()

            async with display.show_tool_activity("bash", {"command": "ls"}):
                mock_show.assert_called_once()

    def test_start_stop_activity(self):
        """Test manual start/stop activity methods."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(activity_enabled=True)

        with patch.object(display._activity_indicator, "start") as mock_start:
            display.start_activity("Test message")
            mock_start.assert_called_once_with("Test message")

        with patch.object(display._activity_indicator, "stop") as mock_stop:
            display.stop_activity()
            mock_stop.assert_called_once()

    def test_update_activity_message(self):
        """Test update_activity_message() method."""
        from orchestrator.display_stream import StreamingDisplayManager

        display = StreamingDisplayManager(activity_enabled=True)

        # Not running - should not call update
        display.update_activity_message("New message")

        # Simulate running
        display._activity_indicator._running = True
        with patch.object(
            display._activity_indicator, "update_message"
        ) as mock_update:
            display.update_activity_message("New message")
            mock_update.assert_called_once_with("New message")
