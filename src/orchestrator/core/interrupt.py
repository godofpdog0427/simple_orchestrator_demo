"""
Interrupt controller for graceful execution cancellation.

This module provides cooperative cancellation support for the orchestrator,
allowing users to interrupt long-running operations gracefully.

Phase 7: Graceful Interrupt Mechanism
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class InterruptType(Enum):
    """Type of interrupt requested."""

    NONE = "none"
    SOFT = "soft"  # Complete current operation, then stop
    HARD = "hard"  # Cancel immediately (but still graceful)


class InterruptReason(Enum):
    """Reason for interrupt."""

    USER_REQUEST = "user_request"
    TIMEOUT = "timeout"
    ERROR = "error"
    SHUTDOWN = "shutdown"


@dataclass
class InterruptState:
    """Current interrupt state."""

    requested: bool = False
    interrupt_type: InterruptType = InterruptType.NONE
    reason: InterruptReason = InterruptReason.USER_REQUEST
    message: str | None = None
    timestamp: float | None = None


class InterruptController:
    """
    Central controller for graceful interrupt handling.

    Thread-safe and asyncio-compatible. Uses cooperative cancellation pattern.

    Usage:
        controller = InterruptController()

        # Request interrupt (from signal handler or user action)
        await controller.request_interrupt(InterruptType.SOFT)

        # Check in execution loop
        if controller.check_interrupt():
            return "Interrupted"

        # Reset for next operation
        await controller.reset()
    """

    def __init__(self, soft_interrupt_limit: int = 2):
        """
        Initialize interrupt controller.

        Args:
            soft_interrupt_limit: Number of soft interrupts before escalating to hard
        """
        self._state = InterruptState()
        self._lock = asyncio.Lock()
        self._interrupt_event = asyncio.Event()
        self._callbacks: list[Callable[[InterruptState], Any]] = []
        self._interrupt_count = 0
        self._soft_interrupt_limit = soft_interrupt_limit

    async def request_interrupt(
        self,
        interrupt_type: InterruptType = InterruptType.SOFT,
        reason: InterruptReason = InterruptReason.USER_REQUEST,
        message: str | None = None,
    ) -> None:
        """
        Request an interrupt of the current operation.

        Args:
            interrupt_type: Type of interrupt (SOFT, HARD)
            reason: Why the interrupt was requested
            message: Optional message for logging/display
        """
        async with self._lock:
            self._interrupt_count += 1

            # Escalate on repeated interrupts
            if self._interrupt_count > self._soft_interrupt_limit:
                interrupt_type = InterruptType.HARD
                message = (
                    f"Escalated to HARD interrupt after {self._interrupt_count} requests"
                )

            self._state = InterruptState(
                requested=True,
                interrupt_type=interrupt_type,
                reason=reason,
                message=message,
                timestamp=time.time(),
            )
            self._interrupt_event.set()

            logger.info(
                f"Interrupt requested: type={interrupt_type.value}, "
                f"reason={reason.value}, message={message}"
            )

        # Notify callbacks (outside lock to prevent deadlock)
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(self._state)
                else:
                    callback(self._state)
            except Exception as e:
                logger.error(f"Interrupt callback error: {e}")

    def request_interrupt_sync(
        self,
        interrupt_type: InterruptType = InterruptType.SOFT,
        reason: InterruptReason = InterruptReason.USER_REQUEST,
        message: str | None = None,
    ) -> None:
        """
        Synchronous version of request_interrupt for use in signal handlers.

        Args:
            interrupt_type: Type of interrupt (SOFT, HARD)
            reason: Why the interrupt was requested
            message: Optional message for logging/display
        """
        self._interrupt_count += 1

        # Escalate on repeated interrupts
        if self._interrupt_count > self._soft_interrupt_limit:
            interrupt_type = InterruptType.HARD
            message = (
                f"Escalated to HARD interrupt after {self._interrupt_count} requests"
            )

        self._state = InterruptState(
            requested=True,
            interrupt_type=interrupt_type,
            reason=reason,
            message=message,
            timestamp=time.time(),
        )
        self._interrupt_event.set()

        logger.info(
            f"Interrupt requested (sync): type={interrupt_type.value}, "
            f"reason={reason.value}, message={message}"
        )

        # Notify synchronous callbacks only
        for callback in self._callbacks:
            if not asyncio.iscoroutinefunction(callback):
                try:
                    callback(self._state)
                except Exception as e:
                    logger.error(f"Interrupt callback error: {e}")

    def check_interrupt(self) -> InterruptState | None:
        """
        Check if interrupt is requested (non-blocking).

        Returns:
            InterruptState if interrupt requested, None otherwise
        """
        if self._state.requested:
            return self._state
        return None

    async def wait_for_interrupt(self, timeout: float | None = None) -> bool:
        """
        Async wait for interrupt signal.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if interrupt received, False if timeout
        """
        try:
            await asyncio.wait_for(self._interrupt_event.wait(), timeout=timeout)
            return True
        except TimeoutError:
            return False

    async def reset(self) -> None:
        """Reset interrupt state for next operation."""
        async with self._lock:
            self._state = InterruptState()
            self._interrupt_event.clear()
            self._interrupt_count = 0
            logger.debug("Interrupt controller reset")

    def reset_sync(self) -> None:
        """Synchronous reset for use outside async context."""
        self._state = InterruptState()
        self._interrupt_event.clear()
        self._interrupt_count = 0
        logger.debug("Interrupt controller reset (sync)")

    def register_callback(self, callback: Callable[[InterruptState], Any]) -> None:
        """
        Register callback to be notified on interrupt.

        Args:
            callback: Function to call when interrupt is requested.
                      Can be sync or async.
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable[[InterruptState], Any]) -> None:
        """
        Unregister interrupt callback.

        Args:
            callback: Previously registered callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    @property
    def is_interrupted(self) -> bool:
        """Check if currently interrupted."""
        return self._state.requested

    @property
    def interrupt_type(self) -> InterruptType:
        """Get current interrupt type."""
        return self._state.interrupt_type

    @property
    def interrupt_count(self) -> int:
        """Get number of interrupt requests in current cycle."""
        return self._interrupt_count


# Global singleton for cross-component access
_global_interrupt_controller: InterruptController | None = None


def get_interrupt_controller() -> InterruptController:
    """Get global interrupt controller instance."""
    global _global_interrupt_controller
    if _global_interrupt_controller is None:
        _global_interrupt_controller = InterruptController()
    return _global_interrupt_controller


def set_interrupt_controller(controller: InterruptController) -> None:
    """Set global interrupt controller instance."""
    global _global_interrupt_controller
    _global_interrupt_controller = controller


def clear_interrupt_controller() -> None:
    """Clear global interrupt controller (for testing)."""
    global _global_interrupt_controller
    _global_interrupt_controller = None
