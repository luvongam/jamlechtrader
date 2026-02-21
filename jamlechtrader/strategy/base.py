"""Abstract base strategy with lifecycle hooks."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from jamlechtrader.core.events import MarketEvent, SignalEvent
from jamlechtrader.core.models import Bar


class AbstractStrategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self) -> None:
        self._bar_history: list[Bar] = []

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def _update_history(self, bar: Bar) -> None:
        self._bar_history.append(bar)

    @property
    def bars_df(self) -> pd.DataFrame:
        """Return bar history as a DataFrame for indicator calculations."""
        if not self._bar_history:
            return pd.DataFrame()
        return pd.DataFrame([b.model_dump() for b in self._bar_history])

    @abstractmethod
    def on_bar(self, event: MarketEvent) -> list[SignalEvent]:
        """Process a new bar and return any trade signals."""

    def on_tick(self, event: MarketEvent) -> list[SignalEvent]:
        """Process a new tick. Override for tick-level strategies."""
        return []

    def on_start(self) -> None:
        """Called when the engine starts. Override for setup."""

    def on_stop(self) -> None:
        """Called when the engine stops. Override for cleanup."""

    def reset(self) -> None:
        """Reset strategy state for a fresh run."""
        self._bar_history.clear()
