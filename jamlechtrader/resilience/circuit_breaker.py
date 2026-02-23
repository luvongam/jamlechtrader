"""Circuit breaker pattern for protecting against cascading failures."""

from __future__ import annotations

import functools
import threading
import time
from enum import Enum
from typing import Any, Callable

from loguru import logger


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpen(Exception):
    """Raised when the circuit breaker is open and calls are rejected."""


class CircuitBreaker:
    """Thread-safe circuit breaker with CLOSED → OPEN → HALF_OPEN states."""

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._half_open_calls = 0
        self._lock = threading.Lock()
        self._on_state_change: list[Callable[[CircuitState, CircuitState], None]] = []

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._transition(CircuitState.HALF_OPEN)
            return self._state

    def on_state_change(self, callback: Callable[[CircuitState, CircuitState], None]) -> None:
        self._on_state_change.append(callback)

    def _transition(self, new_state: CircuitState) -> None:
        old_state = self._state
        self._state = new_state
        if new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
        logger.info(f"Circuit breaker '{self.name}': {old_state.value} → {new_state.value}")
        for cb in self._on_state_change:
            try:
                cb(old_state, new_state)
            except Exception:
                pass

    def record_success(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._transition(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = 0

    def record_failure(self) -> None:
        with self._lock:
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.failure_threshold:
                    self._transition(CircuitState.OPEN)

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                return self._half_open_calls < self.half_open_max_calls
        return False

    def __call__(self, func: Callable) -> Callable:
        """Use as a decorator: @circuit_breaker"""

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not self.allow_request():
                raise CircuitBreakerOpen(
                    f"Circuit breaker '{self.name}' is {self.state.value}"
                )
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except CircuitBreakerOpen:
                raise
            except Exception:
                self.record_failure()
                raise

        return wrapper
