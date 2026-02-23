"""Real-time P&L monitoring with configurable alert thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Callable

from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.notifications import NotificationManager


class AlertLevel(str, Enum):
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    PROFIT_TARGET = "PROFIT_TARGET"


@dataclass
class PnLThresholds:
    warning_pct: float = -2.0
    critical_pct: float = -5.0
    profit_target_pct: float = 3.0


class PnLMonitor:
    """Monitors real-time P&L and fires alerts at configured thresholds."""

    def __init__(
        self,
        initial_equity: float,
        thresholds: PnLThresholds | None = None,
        notification_manager: NotificationManager | None = None,
    ) -> None:
        self._initial_equity = initial_equity
        self._peak_equity = initial_equity
        self.thresholds = thresholds or PnLThresholds()
        self._notification_manager = notification_manager
        self._callbacks: list[Callable[[AlertLevel, float, str], None]] = []
        self._alerts_fired: set[AlertLevel] = set()

    def on_alert(self, callback: Callable[[AlertLevel, float, str], None]) -> None:
        self._callbacks.append(callback)

    def update(self, current_equity: float) -> AlertLevel | None:
        """Update with current equity and check thresholds. Returns alert level if triggered."""
        self._peak_equity = max(self._peak_equity, current_equity)

        if self._initial_equity <= 0:
            return None

        pnl_pct = ((current_equity - self._initial_equity) / self._initial_equity) * 100
        dd_pct = ((self._peak_equity - current_equity) / self._peak_equity * 100) if self._peak_equity > 0 else 0

        alert = None

        if pnl_pct <= self.thresholds.critical_pct and AlertLevel.CRITICAL not in self._alerts_fired:
            alert = AlertLevel.CRITICAL
            msg = f"CRITICAL: P&L at {pnl_pct:.2f}%, drawdown {dd_pct:.2f}%"
        elif pnl_pct <= self.thresholds.warning_pct and AlertLevel.WARNING not in self._alerts_fired:
            alert = AlertLevel.WARNING
            msg = f"WARNING: P&L at {pnl_pct:.2f}%, drawdown {dd_pct:.2f}%"
        elif pnl_pct >= self.thresholds.profit_target_pct and AlertLevel.PROFIT_TARGET not in self._alerts_fired:
            alert = AlertLevel.PROFIT_TARGET
            msg = f"PROFIT TARGET: P&L at {pnl_pct:.2f}%"

        if alert is not None:
            self._alerts_fired.add(alert)
            logger.info(f"PnL alert: {msg}")
            for cb in self._callbacks:
                try:
                    cb(alert, pnl_pct, msg)
                except Exception as e:
                    logger.error(f"PnL alert callback error: {e}")

            if self._notification_manager:
                self._notification_manager.notify_error(msg)

        return alert

    def reset(self, equity: float) -> None:
        """Reset monitoring with new baseline equity."""
        self._initial_equity = equity
        self._peak_equity = equity
        self._alerts_fired.clear()

    @property
    def alerts_fired(self) -> set[AlertLevel]:
        return self._alerts_fired.copy()
