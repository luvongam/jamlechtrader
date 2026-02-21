"""Portfolio tracking: positions, cash, equity, P&L."""

from __future__ import annotations

from datetime import UTC, datetime

from loguru import logger

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import Position, PortfolioSnapshot


class Portfolio:
    """Tracks open positions, cash balance, and performance."""

    def __init__(self, initial_cash: float = 10_000.0) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}  # symbol → Position
        self.closed_trades: list[dict] = []
        self.equity_curve: list[PortfolioSnapshot] = []
        self._peak_equity = initial_cash
        self.realized_pnl = 0.0

    @property
    def equity(self) -> float:
        unrealized = sum(p.unrealized_pnl for p in self.positions.values())
        return self.cash + unrealized

    @property
    def unrealized_pnl(self) -> float:
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def drawdown(self) -> float:
        if self._peak_equity <= 0:
            return 0.0
        return (self._peak_equity - self.equity) / self._peak_equity

    def generate_order(
        self, signal: SignalEvent, quantity: float
    ) -> OrderEvent | None:
        """Convert a signal into an order event, handling position flipping."""
        symbol = signal.symbol

        # If we have an existing position in the opposite direction, close it first
        if symbol in self.positions:
            existing = self.positions[symbol]
            if existing.side != signal.side:
                # Close existing — the engine will handle this fill,
                # then the new signal will open a fresh position
                return OrderEvent(
                    symbol=symbol,
                    side=OrderSide.SELL if existing.side == OrderSide.BUY else OrderSide.BUY,
                    quantity=existing.quantity,
                    timestamp=signal.timestamp,
                )
            else:
                # Same direction — skip (already positioned)
                return None

        return OrderEvent(
            symbol=symbol,
            side=signal.side,
            quantity=quantity,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            timestamp=signal.timestamp,
        )

    def on_fill(self, fill: FillEvent) -> None:
        """Update portfolio state on a fill."""
        symbol = fill.symbol

        if symbol in self.positions:
            pos = self.positions[symbol]
            if pos.side != fill.side:
                # Closing (or partially closing) a position
                pnl = self._calculate_pnl(pos, fill.price)
                self.realized_pnl += pnl
                self.cash += pnl + (pos.entry_price * pos.quantity)
                self.closed_trades.append({
                    "symbol": symbol,
                    "side": pos.side.value,
                    "entry_price": pos.entry_price,
                    "exit_price": fill.price,
                    "quantity": pos.quantity,
                    "pnl": pnl,
                    "commission": fill.commission,
                    "entry_time": pos.open_time,
                    "exit_time": fill.timestamp,
                })
                del self.positions[symbol]
                logger.debug(f"Closed {symbol} PnL={pnl:.2f}")
            else:
                # Adding to position (average up/down)
                total_qty = pos.quantity + fill.quantity
                pos.entry_price = (
                    (pos.entry_price * pos.quantity + fill.price * fill.quantity)
                    / total_qty
                )
                pos.quantity = total_qty
                self.cash -= fill.price * fill.quantity + fill.commission
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                side=fill.side,
                quantity=fill.quantity,
                entry_price=fill.price,
                current_price=fill.price,
                open_time=fill.timestamp,
            )
            self.cash -= fill.price * fill.quantity + fill.commission
            logger.debug(f"Opened {fill.side.value} {symbol} @ {fill.price}")

    def update_market_price(self, symbol: str, price: float) -> None:
        """Update current price and unrealized P&L for a position."""
        if symbol in self.positions:
            self.positions[symbol].update_pnl(price)

    def take_snapshot(self, timestamp: datetime | None = None) -> PortfolioSnapshot:
        """Record current portfolio state."""
        ts = timestamp or datetime.now(tz=UTC)
        eq = self.equity
        self._peak_equity = max(self._peak_equity, eq)

        snapshot = PortfolioSnapshot(
            timestamp=ts,
            cash=self.cash,
            equity=eq,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            positions=list(self.positions.values()),
            drawdown=self.drawdown,
        )
        self.equity_curve.append(snapshot)
        return snapshot

    def _calculate_pnl(self, position: Position, exit_price: float) -> float:
        if position.side == OrderSide.BUY:
            return (exit_price - position.entry_price) * position.quantity
        else:
            return (position.entry_price - exit_price) * position.quantity

    def reset(self) -> None:
        self.cash = self.initial_cash
        self.positions.clear()
        self.closed_trades.clear()
        self.equity_curve.clear()
        self._peak_equity = self.initial_cash
        self.realized_pnl = 0.0
