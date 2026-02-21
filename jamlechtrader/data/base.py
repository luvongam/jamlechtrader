"""Abstract base for data handlers."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from jamlechtrader.core.events import MarketEvent
from jamlechtrader.core.models import Bar


class AbstractDataHandler(ABC):
    """Base class for all data providers."""

    @abstractmethod
    def load(self) -> None:
        """Load / prepare data."""

    @abstractmethod
    def bars(self) -> Iterator[Bar]:
        """Yield bars sequentially."""

    @abstractmethod
    def has_next(self) -> bool:
        """Return True if more bars are available."""

    def emit_market_events(self) -> Iterator[MarketEvent]:
        """Yield MarketEvents wrapping each bar."""
        for bar in self.bars():
            yield MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
