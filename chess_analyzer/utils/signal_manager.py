# chess_analyzer_project/chess_analyzer/utils/signal_manager.py
"""
Manages system signal handling for graceful application shutdown.

This module provides a context manager to set up handlers for signals like
SIGINT (Ctrl+C) and SIGTERM. This ensures that original signal handlers are
always restored, even if the application exits unexpectedly.
"""
import signal
import logging
import sys
import threading
from types import FrameType
from typing import Optional, Callable, List, Union, TypeAlias

from chess_analyzer.config import settings

logger = logging.getLogger(settings.APP_NAME + ".SignalManager")

# Type alias for the complex type of a signal handler.
# A handler can be a callable, or one of two integer constants (SIG_DFL, SIG_IGN).
Handler: TypeAlias = Union[Callable[[int, Optional[FrameType]], None], int, None]


class SignalManager:
    """
    A context manager to handle system signals for graceful shutdown.

    Usage:
        shutdown_event = threading.Event()
        with SignalManager(shutdown_event):
            # Main application loop runs here
            # Poll shutdown_event.is_set() to break the loop
        # Original signal handlers are automatically restored on exit.

    When a registered signal is received, it sets the provided event and
    logs a message. A second signal will force an immediate exit.
    """

    def __init__(self, shutdown_event: threading.Event):
        """
        Initializes the SignalManager.

        Args:
            shutdown_event: A `threading.Event` instance that will be set
                            when a shutdown signal is caught.
        """
        self.shutdown_event: threading.Event = shutdown_event
        self._original_handlers: List[tuple[int, Handler]] = []
        self._double_signal_exit_code: int = 130  # Common exit code for SIGINT

    def _get_signals_to_handle(self) -> List[signal.Signals]:
        """Determines which signals to handle based on platform compatibility."""
        signals_to_handle = [signal.SIGINT]
        # SIGTERM is not available on Windows
        if hasattr(signal, "SIGTERM"):
            signals_to_handle.append(signal.SIGTERM)
        return signals_to_handle

    def __enter__(self):
        """Sets up the system signal handlers upon entering the context."""
        logger.debug("Setting up signal handlers for graceful shutdown...")
        self._original_handlers = []
        for sig in self._get_signals_to_handle():
            try:
                original_handler = signal.getsignal(sig)
                self._original_handlers.append((sig, original_handler))
                signal.signal(sig, self._signal_handler)
                logger.debug(f"Handler for {sig.name} set.")
            except (ValueError, OSError, RuntimeError) as e:
                # This can happen in restricted environments or non-main threads.
                logger.warning(
                    f"Could not set signal handler for {sig.name}: {e}",
                    exc_info=True
                )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restores the original signal handlers upon exiting the context."""
        logger.debug("Restoring original signal handlers...")
        for sig_num, handler in self._original_handlers:
            try:
                current_handler = signal.getsignal(sig_num)
                # Restore only if our handler is still active.
                if current_handler is self._signal_handler:
                    signal.signal(sig_num, handler)
                    logger.debug(f"Restored original handler for {signal.Signals(sig_num).name}.")
            except (ValueError, OSError, RuntimeError) as e:
                logger.warning(
                    f"Error restoring original handler for {signal.Signals(sig_num).name}: {e}"
                )
        logger.info("Original signal handlers restored.")

    def _signal_handler(self, signum: int, frame: Optional[FrameType]) -> None:
        """Internal handler for received signals."""
        signal_name = signal.Signals(signum).name
        if not self.shutdown_event.is_set():
            logger.warning(
                f"\nSignal {signal_name} ({signum}) received. Requesting graceful shutdown..."
            )
            logger.info("Finishing current analysis... Press Ctrl+C again to force quit.")
            self.shutdown_event.set()
        else:
            logger.critical(f"Second signal {signal_name} ({signum}) received. Forcing exit.")
            # The __exit__ method will still attempt to run on a normal sys.exit,
            # but this hard exit is for when the graceful shutdown is taking too long.
            sys.exit(self._double_signal_exit_code)