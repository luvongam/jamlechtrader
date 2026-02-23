"""Graceful shutdown handling for SIGINT/SIGTERM."""

from __future__ import annotations

import signal
import threading
from typing import Callable

from loguru import logger


class GracefulShutdown:
    """Handles graceful shutdown on SIGINT/SIGTERM.

    Runs registered callbacks in order: save state → close positions →
    close connections → flush logs.
    """

    def __init__(self) -> None:
        self._callbacks: list[tuple[str, Callable[[], None]]] = []
        self._shutdown_event = threading.Event()
        self._shutting_down = False

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def register(self, name: str, callback: Callable[[], None]) -> None:
        """Register a shutdown callback. Callbacks run in registration order."""
        self._callbacks.append((name, callback))

    def install_signal_handlers(self) -> None:
        """Install SIGINT and SIGTERM handlers."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)
        logger.debug("Graceful shutdown signal handlers installed")

    def _handle_signal(self, signum: int, frame) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        self._shutting_down = True
        self._shutdown_event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until shutdown signal received. Returns True if signaled."""
        return self._shutdown_event.wait(timeout=timeout)

    def execute(self) -> None:
        """Run all registered shutdown callbacks in order."""
        self._shutting_down = True
        logger.info(f"Executing {len(self._callbacks)} shutdown callbacks...")
        for name, callback in self._callbacks:
            try:
                logger.debug(f"Running shutdown callback: {name}")
                callback()
            except Exception as e:
                logger.error(f"Shutdown callback '{name}' failed: {e}")
        logger.info("Graceful shutdown complete")
