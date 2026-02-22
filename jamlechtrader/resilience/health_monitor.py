"""Background health monitoring for MT5 connection with auto-reconnect."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Callable

from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.mt5.connection import MT5Connection
    from jamlechtrader.resilience.circuit_breaker import CircuitBreaker


class ConnectionHealthMonitor:
    """Background thread that polls MT5 connection health and auto-reconnects."""

    def __init__(
        self,
        connection: MT5Connection,
        poll_interval: float = 5.0,
        circuit_breaker: CircuitBreaker | None = None,
    ) -> None:
        self._connection = connection
        self._poll_interval = poll_interval
        self._circuit_breaker = circuit_breaker
        self._running = False
        self._thread: threading.Thread | None = None
        self._on_disconnect: list[Callable[[], None]] = []
        self._on_reconnect: list[Callable[[], None]] = []
        self._was_connected = True
        self._reconnect_count = 0

    def on_disconnect(self, callback: Callable[[], None]) -> None:
        self._on_disconnect.append(callback)

    def on_reconnect(self, callback: Callable[[], None]) -> None:
        self._on_reconnect.append(callback)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="health-monitor")
        self._thread.start()
        logger.info("Connection health monitor started")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=self._poll_interval + 1)
            self._thread = None
        logger.info("Connection health monitor stopped")

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    def _monitor_loop(self) -> None:
        while self._running:
            try:
                connected = self._connection.is_connected
                if connected:
                    if not self._was_connected:
                        self._reconnect_count += 1
                        logger.info(f"MT5 reconnected (reconnect #{self._reconnect_count})")
                        for cb in self._on_reconnect:
                            try:
                                cb()
                            except Exception as e:
                                logger.error(f"Reconnect callback error: {e}")
                        if self._circuit_breaker:
                            self._circuit_breaker.record_success()
                    self._was_connected = True
                else:
                    if self._was_connected:
                        logger.warning("MT5 connection lost, attempting reconnect...")
                        for cb in self._on_disconnect:
                            try:
                                cb()
                            except Exception as e:
                                logger.error(f"Disconnect callback error: {e}")
                    self._was_connected = False
                    if self._circuit_breaker:
                        self._circuit_breaker.record_failure()
                    self._try_reconnect()
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

            time.sleep(self._poll_interval)

    def _try_reconnect(self) -> None:
        try:
            self._connection.disconnect()
            if self._connection.connect():
                logger.info("MT5 reconnection successful")
            else:
                logger.warning("MT5 reconnection failed, will retry...")
        except Exception as e:
            logger.error(f"Reconnection error: {e}")
