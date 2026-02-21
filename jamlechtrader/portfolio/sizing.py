"""Position sizing methods: fixed lot, percentage risk, ATR-based."""

from __future__ import annotations

from jamlechtrader.core.models import Bar


class PositionSizer:
    """Calculates position size based on different methods."""

    def __init__(
        self,
        method: str = "fixed",
        fixed_lot: float = 0.01,
        risk_pct: float = 1.0,
        atr_multiplier: float = 1.5,
    ) -> None:
        self.method = method
        self.fixed_lot = fixed_lot
        self.risk_pct = risk_pct
        self.atr_multiplier = atr_multiplier

    def calculate(
        self,
        equity: float,
        bar: Bar | None = None,
        stop_distance: float | None = None,
        atr_value: float | None = None,
        pip_value: float = 10.0,
        min_lot: float = 0.01,
        max_lot: float = 100.0,
        lot_step: float = 0.01,
    ) -> float:
        """Calculate position size."""
        if self.method == "fixed":
            size = self.fixed_lot

        elif self.method == "risk_pct":
            if stop_distance is None or stop_distance <= 0:
                return self.fixed_lot
            risk_amount = equity * (self.risk_pct / 100.0)
            size = risk_amount / (stop_distance * pip_value)

        elif self.method == "atr":
            if atr_value is None or atr_value <= 0:
                return self.fixed_lot
            stop_dist = atr_value * self.atr_multiplier
            risk_amount = equity * (self.risk_pct / 100.0)
            size = risk_amount / (stop_dist * pip_value)

        else:
            size = self.fixed_lot

        # Round to lot step and clamp
        size = max(min_lot, min(max_lot, size))
        size = round(size / lot_step) * lot_step
        return round(size, 8)
