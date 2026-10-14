"""Health check system for database and engine status."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0


@dataclass
class HealthCheckResult:
    status: HealthStatus
    components: list[ComponentHealth] = field(default_factory=list)
    uptime_seconds: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "latency_ms": c.latency_ms,
                }
                for c in self.components
            ],
        }


class HealthChecker:
    """Checks health of database and engine."""

    def __init__(self) -> None:
        self._start_time = datetime.now(tz=UTC)
        self._db_connected = False
        self._engine_running = False

    def set_db_status(self, connected: bool) -> None:
        self._db_connected = connected

    def set_engine_status(self, running: bool) -> None:
        self._engine_running = running

    def check(self) -> HealthCheckResult:
        components = []

        # Database
        db_status = HealthStatus.HEALTHY if self._db_connected else HealthStatus.DEGRADED
        components.append(ComponentHealth(
            name="database",
            status=db_status,
            message="Connected" if self._db_connected else "Unavailable",
        ))

        # Engine
        engine_status = HealthStatus.HEALTHY if self._engine_running else HealthStatus.UNHEALTHY
        components.append(ComponentHealth(
            name="engine",
            status=engine_status,
            message="Running" if self._engine_running else "Stopped",
        ))

        # Overall status
        statuses = [c.status for c in components]
        if HealthStatus.UNHEALTHY in statuses:
            overall = HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        uptime = (datetime.now(tz=UTC) - self._start_time).total_seconds()

        return HealthCheckResult(
            status=overall,
            components=components,
            uptime_seconds=uptime,
        )
