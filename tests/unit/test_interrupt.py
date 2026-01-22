"""Unit tests for the interrupt controller module."""

import asyncio
import pytest

from orchestrator.core.interrupt import (
    InterruptController,
    InterruptType,
    InterruptReason,
    InterruptState,
    get_interrupt_controller,
    set_interrupt_controller,
    clear_interrupt_controller,
)


class TestInterruptType:
    """Test InterruptType enum."""

    def test_interrupt_types(self):
        """Test all interrupt types are defined correctly."""
        assert InterruptType.NONE.value == "none"
        assert InterruptType.SOFT.value == "soft"
        assert InterruptType.HARD.value == "hard"


class TestInterruptReason:
    """Test InterruptReason enum."""

    def test_interrupt_reasons(self):
        """Test all interrupt reasons are defined correctly."""
        assert InterruptReason.USER_REQUEST.value == "user_request"
        assert InterruptReason.TIMEOUT.value == "timeout"
        assert InterruptReason.ERROR.value == "error"
        assert InterruptReason.SHUTDOWN.value == "shutdown"


class TestInterruptState:
    """Test InterruptState dataclass."""

    def test_default_state(self):
        """Test default interrupt state."""
        state = InterruptState()
        assert state.requested is False
        assert state.interrupt_type == InterruptType.NONE
        assert state.reason == InterruptReason.USER_REQUEST
        assert state.message is None
        assert state.timestamp is None

    def test_custom_state(self):
        """Test custom interrupt state."""
        state = InterruptState(
            requested=True,
            interrupt_type=InterruptType.SOFT,
            reason=InterruptReason.TIMEOUT,
            message="Test message",
            timestamp=123.456,
        )
        assert state.requested is True
        assert state.interrupt_type == InterruptType.SOFT
        assert state.reason == InterruptReason.TIMEOUT
        assert state.message == "Test message"
        assert state.timestamp == 123.456


class TestInterruptController:
    """Test InterruptController class."""

    @pytest.fixture
    def controller(self):
        """Create a fresh interrupt controller for each test."""
        return InterruptController()

    @pytest.mark.asyncio
    async def test_initial_state(self, controller):
        """Test controller starts in non-interrupted state."""
        assert controller.is_interrupted is False
        assert controller.interrupt_type == InterruptType.NONE
        assert controller.interrupt_count == 0
        assert controller.check_interrupt() is None

    @pytest.mark.asyncio
    async def test_request_interrupt_soft(self, controller):
        """Test requesting a soft interrupt."""
        await controller.request_interrupt(
            interrupt_type=InterruptType.SOFT,
            reason=InterruptReason.USER_REQUEST,
            message="Test interrupt",
        )

        assert controller.is_interrupted is True
        assert controller.interrupt_type == InterruptType.SOFT
        assert controller.interrupt_count == 1

        state = controller.check_interrupt()
        assert state is not None
        assert state.requested is True
        assert state.interrupt_type == InterruptType.SOFT
        assert state.reason == InterruptReason.USER_REQUEST
        assert state.message == "Test interrupt"
        assert state.timestamp is not None

    @pytest.mark.asyncio
    async def test_request_interrupt_hard(self, controller):
        """Test requesting a hard interrupt."""
        await controller.request_interrupt(interrupt_type=InterruptType.HARD)

        assert controller.is_interrupted is True
        assert controller.interrupt_type == InterruptType.HARD

    @pytest.mark.asyncio
    async def test_interrupt_escalation(self, controller):
        """Test soft interrupt escalates to hard after limit."""
        # Request soft interrupts up to the limit
        for _ in range(2):
            await controller.request_interrupt(interrupt_type=InterruptType.SOFT)

        assert controller.interrupt_type == InterruptType.SOFT
        assert controller.interrupt_count == 2

        # Third request should escalate to hard
        await controller.request_interrupt(interrupt_type=InterruptType.SOFT)

        assert controller.interrupt_type == InterruptType.HARD
        assert controller.interrupt_count == 3

    @pytest.mark.asyncio
    async def test_interrupt_escalation_custom_limit(self):
        """Test custom soft interrupt limit."""
        controller = InterruptController(soft_interrupt_limit=1)

        # First request - should be soft
        await controller.request_interrupt(interrupt_type=InterruptType.SOFT)
        assert controller.interrupt_type == InterruptType.SOFT

        # Second request - should escalate to hard
        await controller.request_interrupt(interrupt_type=InterruptType.SOFT)
        assert controller.interrupt_type == InterruptType.HARD

    @pytest.mark.asyncio
    async def test_reset(self, controller):
        """Test reset clears interrupt state."""
        # Request an interrupt
        await controller.request_interrupt(interrupt_type=InterruptType.SOFT)
        assert controller.is_interrupted is True
        assert controller.interrupt_count == 1

        # Reset
        await controller.reset()

        assert controller.is_interrupted is False
        assert controller.interrupt_type == InterruptType.NONE
        assert controller.interrupt_count == 0
        assert controller.check_interrupt() is None

    def test_reset_sync(self, controller):
        """Test synchronous reset."""
        controller.request_interrupt_sync(interrupt_type=InterruptType.SOFT)
        assert controller.is_interrupted is True

        controller.reset_sync()

        assert controller.is_interrupted is False
        assert controller.interrupt_count == 0

    def test_request_interrupt_sync(self, controller):
        """Test synchronous interrupt request."""
        controller.request_interrupt_sync(
            interrupt_type=InterruptType.SOFT,
            reason=InterruptReason.USER_REQUEST,
            message="Sync interrupt",
        )

        assert controller.is_interrupted is True
        assert controller.interrupt_type == InterruptType.SOFT

        state = controller.check_interrupt()
        assert state is not None
        assert state.message == "Sync interrupt"

    def test_sync_interrupt_escalation(self, controller):
        """Test sync interrupt also escalates."""
        for _ in range(3):
            controller.request_interrupt_sync(interrupt_type=InterruptType.SOFT)

        assert controller.interrupt_type == InterruptType.HARD

    @pytest.mark.asyncio
    async def test_callback_notification(self, controller):
        """Test callbacks are notified on interrupt."""
        callback_states = []

        def sync_callback(state):
            callback_states.append(("sync", state))

        async def async_callback(state):
            callback_states.append(("async", state))

        controller.register_callback(sync_callback)
        controller.register_callback(async_callback)

        await controller.request_interrupt(
            interrupt_type=InterruptType.SOFT,
            message="Callback test",
        )

        # Both callbacks should have been called
        assert len(callback_states) == 2

        # Check sync callback
        assert callback_states[0][0] == "sync"
        assert callback_states[0][1].message == "Callback test"

        # Check async callback
        assert callback_states[1][0] == "async"
        assert callback_states[1][1].message == "Callback test"

    def test_sync_callback_only(self, controller):
        """Test sync interrupt only calls sync callbacks."""
        callback_states = []

        def sync_callback(state):
            callback_states.append(("sync", state))

        async def async_callback(state):
            callback_states.append(("async", state))

        controller.register_callback(sync_callback)
        controller.register_callback(async_callback)

        controller.request_interrupt_sync(interrupt_type=InterruptType.SOFT)

        # Only sync callback should have been called
        assert len(callback_states) == 1
        assert callback_states[0][0] == "sync"

    def test_unregister_callback(self, controller):
        """Test unregistering callbacks."""
        callback_called = False

        def callback(state):
            nonlocal callback_called
            callback_called = True

        controller.register_callback(callback)
        controller.unregister_callback(callback)

        controller.request_interrupt_sync()

        assert callback_called is False

    @pytest.mark.asyncio
    async def test_wait_for_interrupt_with_interrupt(self, controller):
        """Test waiting for interrupt when one is requested."""
        # Request interrupt in a separate task
        async def request_later():
            await asyncio.sleep(0.05)
            await controller.request_interrupt()

        asyncio.create_task(request_later())

        # Wait for interrupt
        result = await controller.wait_for_interrupt(timeout=1.0)
        assert result is True
        assert controller.is_interrupted is True

    @pytest.mark.asyncio
    async def test_wait_for_interrupt_timeout(self, controller):
        """Test wait times out when no interrupt."""
        result = await controller.wait_for_interrupt(timeout=0.1)
        assert result is False
        assert controller.is_interrupted is False

    @pytest.mark.asyncio
    async def test_callback_error_handling(self, controller):
        """Test that callback errors don't prevent interrupt."""
        def failing_callback(state):
            raise ValueError("Callback error")

        called = []
        def working_callback(state):
            called.append(True)

        controller.register_callback(failing_callback)
        controller.register_callback(working_callback)

        # Should not raise, and second callback should still be called
        await controller.request_interrupt()

        assert controller.is_interrupted is True
        assert len(called) == 1


class TestGlobalInterruptController:
    """Test global interrupt controller functions."""

    def setup_method(self):
        """Clear global controller before each test."""
        clear_interrupt_controller()

    def teardown_method(self):
        """Clear global controller after each test."""
        clear_interrupt_controller()

    def test_get_creates_instance(self):
        """Test get_interrupt_controller creates instance if none exists."""
        controller = get_interrupt_controller()
        assert controller is not None
        assert isinstance(controller, InterruptController)

    def test_get_returns_same_instance(self):
        """Test get_interrupt_controller returns same instance."""
        controller1 = get_interrupt_controller()
        controller2 = get_interrupt_controller()
        assert controller1 is controller2

    def test_set_interrupt_controller(self):
        """Test setting a custom controller."""
        custom_controller = InterruptController(soft_interrupt_limit=5)
        set_interrupt_controller(custom_controller)

        retrieved = get_interrupt_controller()
        assert retrieved is custom_controller
        assert retrieved._soft_interrupt_limit == 5

    def test_clear_interrupt_controller(self):
        """Test clearing the global controller."""
        _ = get_interrupt_controller()  # Create one
        clear_interrupt_controller()

        # Next get should create a new one
        new_controller = get_interrupt_controller()
        assert new_controller is not None
