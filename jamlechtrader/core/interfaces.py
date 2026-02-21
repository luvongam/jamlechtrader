"""Abstract base classes for pluggable components."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from jamlechtrader.core.events import FillEvent, MarketEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import Bar, PortfolioSnapshot


class DataHandler(ABC):
    """Provides market data as bars or ticks."""

    @abstractmethod
    def get_bars(self) -> Iterator[Bar]:
        """Yield bars one at a time."""

    @abstractmethod
    def has_next(self) -> bool:
        """Check if more data is available."""


class Strategy(ABC):
    """Trading strategy interface."""

    @abstractmethod
    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        """Process a bar and return any signals."""

    def on_tick(self, event: MarketEvent) -> list[SignalEvent]:
        """Process a tick and return any signals. Override for tick strategies."""
        return []

    def on_start(self) -> None:
        """Called when the engine starts."""

    def on_stop(self) -> None:
        """Called when the engine stops."""


class ExecutionHandler(ABC):
    """Handles order execution (simulated or live)."""

    @abstractmethod
    def execute_order(self, order: OrderEvent) -> FillEvent | None:
        """Execute an order and return a fill, or None if rejected."""


class RiskManager(ABC):
    """Validates orders against risk rules before execution."""

    @abstractmethod
    def check_order(self, order: OrderEvent, portfolio: PortfolioSnapshot) -> OrderEvent | None:
        """Return the (possibly modified) order, or None to reject."""
