"""Value-at-Risk (VaR) calculation using historical, parametric, and CVaR methods."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.core.models import PortfolioSnapshot


class VaRCalculator:
    """Value-at-Risk calculator supporting multiple methods."""

    def __init__(self, returns: np.ndarray | None = None, window: int = 252) -> None:
        self._returns = returns if returns is not None else np.array([])
        self._window = window

    def update_returns(self, returns: np.ndarray) -> None:
        """Update the return series used for calculations."""
        self._returns = returns

    def add_return(self, daily_return: float) -> None:
        """Append a single return observation."""
        self._returns = np.append(self._returns, daily_return)
        if len(self._returns) > self._window:
            self._returns = self._returns[-self._window:]

    def historical_var(self, confidence: float = 0.95) -> float:
        """Historical simulation VaR as a positive percentage."""
        if len(self._returns) < 10:
            return 0.0
        percentile = (1 - confidence) * 100
        var = -np.percentile(self._returns, percentile)
        return max(var * 100, 0.0)

    def parametric_var(self, confidence: float = 0.95) -> float:
        """Parametric (Gaussian) VaR as a positive percentage."""
        if len(self._returns) < 10:
            return 0.0
        from scipy.stats import norm

        mu = np.mean(self._returns)
        sigma = np.std(self._returns, ddof=1)
        z = norm.ppf(1 - confidence)
        var = -(mu + z * sigma)
        return max(var * 100, 0.0)

    def cvar(self, confidence: float = 0.95) -> float:
        """Conditional VaR (Expected Shortfall) as a positive percentage."""
        if len(self._returns) < 10:
            return 0.0
        percentile = (1 - confidence) * 100
        threshold = np.percentile(self._returns, percentile)
        tail_losses = self._returns[self._returns <= threshold]
        if len(tail_losses) == 0:
            return 0.0
        es = -np.mean(tail_losses)
        return max(es * 100, 0.0)

    def portfolio_var(
        self,
        portfolio: PortfolioSnapshot,
        confidence: float = 0.95,
    ) -> float:
        """Portfolio-level VaR considering current positions.

        Falls back to historical VaR on the stored return series.
        """
        if len(self._returns) < 10:
            return 0.0
        return self.historical_var(confidence)
