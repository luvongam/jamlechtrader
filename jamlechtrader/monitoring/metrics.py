"""Prometheus metrics for trading observability."""

from __future__ import annotations

from typing import TYPE_CHECKING

from prometheus_client import Counter, Gauge, Histogram

if TYPE_CHECKING:
    from jamlechtrader.core.models import Fill, PortfolioSnapshot

# Counters
ORDERS_SUBMITTED = Counter(
    "jamlechtrader_orders_submitted_total", "Total orders submitted", ["symbol"]
)
ORDERS_FILLED = Counter(
    "jamlechtrader_orders_filled_total", "Total orders filled", ["symbol"]
)
ORDERS_REJECTED = Counter(
    "jamlechtrader_orders_rejected_total", "Total orders rejected", ["symbol", "reason"]
)
MT5_RECONNECTS = Counter(
    "jamlechtrader_mt5_reconnects_total", "Total MT5 reconnections"
)

# Gauges
EQUITY = Gauge("jamlechtrader_equity", "Current portfolio equity")
CASH = Gauge("jamlechtrader_cash", "Current cash balance")
UNREALIZED_PNL = Gauge("jamlechtrader_unrealized_pnl", "Unrealized P&L")
REALIZED_PNL = Gauge("jamlechtrader_realized_pnl", "Realized P&L")
OPEN_POSITIONS = Gauge("jamlechtrader_open_positions", "Number of open positions")
DRAWDOWN_PCT = Gauge("jamlechtrader_drawdown_pct", "Current drawdown percentage")
POSITION_QUANTITY = Gauge(
    "jamlechtrader_position_quantity", "Position quantity per symbol", ["symbol"]
)
MT5_CONNECTED = Gauge("jamlechtrader_mt5_connected", "MT5 connection status (1=connected)")

# Histograms
ORDER_LATENCY = Histogram(
    "jamlechtrader_order_latency_seconds",
    "Order execution latency",
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)
FILL_SLIPPAGE = Histogram(
    "jamlechtrader_fill_slippage_pips",
    "Fill slippage in pips",
    buckets=[0, 0.5, 1, 2, 3, 5, 10],
)


class TradingMetrics:
    """Helper class for updating Prometheus metrics."""

    def update_portfolio(self, snapshot: PortfolioSnapshot) -> None:
        """Update portfolio-level gauges from a snapshot."""
        EQUITY.set(snapshot.equity)
        CASH.set(snapshot.cash)
        UNREALIZED_PNL.set(snapshot.unrealized_pnl)
        REALIZED_PNL.set(snapshot.realized_pnl)
        DRAWDOWN_PCT.set(snapshot.drawdown * 100)
        OPEN_POSITIONS.set(len(snapshot.positions))

        for pos in snapshot.positions:
            POSITION_QUANTITY.labels(symbol=pos.symbol).set(pos.quantity)

    def record_fill(
        self,
        symbol: str,
        latency_seconds: float = 0.0,
        slippage_pips: float = 0.0,
    ) -> None:
        """Record a fill with latency and slippage."""
        ORDERS_FILLED.labels(symbol=symbol).inc()
        if latency_seconds > 0:
            ORDER_LATENCY.observe(latency_seconds)
        FILL_SLIPPAGE.observe(slippage_pips)

    def record_submission(self, symbol: str) -> None:
        ORDERS_SUBMITTED.labels(symbol=symbol).inc()

    def record_rejection(self, symbol: str, reason: str = "unknown") -> None:
        ORDERS_REJECTED.labels(symbol=symbol, reason=reason).inc()

    def set_mt5_connected(self, connected: bool) -> None:
        MT5_CONNECTED.set(1 if connected else 0)

    def record_reconnect(self) -> None:
        MT5_RECONNECTS.inc()
