"""Pydantic v2 domain models for the trading platform."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field

from jamlechtrader.core.enums import OrderSide, OrderStatus, OrderType, TimeInForce


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class Bar(BaseModel):
    """OHLCV bar."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    spread: int = 0
    tick_volume: float = 0


class Tick(BaseModel):
    """Single price tick."""

    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float = 0.0
    volume: float = 0.0


class Order(BaseModel):
    """Order representation."""

    id: str = ""
    symbol: str
    side: OrderSide
    order_type: OrderType = OrderType.MARKET
    quantity: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    time_in_force: TimeInForce = TimeInForce.GTC
    status: OrderStatus = OrderStatus.PENDING
    timestamp: datetime = Field(default_factory=_utcnow)
    comment: str = ""
    client_order_id: str = ""
    tags: dict[str, str] = Field(default_factory=dict)


class Fill(BaseModel):
    """Executed fill."""

    id: str = ""
    order_id: str = ""
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    commission: float = 0.0
    slippage: float = 0.0
    timestamp: datetime = Field(default_factory=_utcnow)


class Position(BaseModel):
    """Open position."""

    symbol: str
    side: OrderSide
    quantity: float
    entry_price: float
    current_price: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_time: datetime = Field(default_factory=_utcnow)
    ticket: int = 0

    def update_pnl(self, current_price: float) -> None:
        self.current_price = current_price
        if self.side == OrderSide.BUY:
            self.unrealized_pnl = (current_price - self.entry_price) * self.quantity
        else:
            self.unrealized_pnl = (self.entry_price - current_price) * self.quantity


class PortfolioSnapshot(BaseModel):
    """Point-in-time portfolio state."""

    timestamp: datetime = Field(default_factory=_utcnow)
    cash: float
    equity: float
    margin_used: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    positions: list[Position] = Field(default_factory=list)
    drawdown: float = 0.0
