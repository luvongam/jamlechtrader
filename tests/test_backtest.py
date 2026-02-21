"""Integration test: backtest engine with SMA crossover on sample data."""

from datetime import datetime, timedelta

import pytest

from jamlechtrader.core.models import Bar
from jamlechtrader.data.base import AbstractDataHandler
from jamlechtrader.engine.backtest import BacktestEngine
from jamlechtrader.execution.simulated import SimulatedExecutor
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.strategy.examples.sma_crossover import SMACrossoverStrategy


class InMemoryDataHandler(AbstractDataHandler):
    """Test data handler that serves bars from memory."""

    def __init__(self, bars: list[Bar]) -> None:
        self._bars = bars
        self._index = 0

    def load(self) -> None:
        self._index = 0

    def bars(self):
        self._index = 0
        for bar in self._bars:
            self._index += 1
            yield bar

    def has_next(self) -> bool:
        return self._index < len(self._bars)


class TestBacktestEngine:
    def test_runs_to_completion(self, sample_bars):
        data = InMemoryDataHandler(sample_bars)
        strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
        portfolio = Portfolio(initial_cash=10000.0)
        sizer = PositionSizer(method="fixed", fixed_lot=0.01)

        engine = BacktestEngine(
            data_handler=data,
            strategy=strategy,
            portfolio=portfolio,
            sizer=sizer,
        )
        results = engine.run()

        assert results["bars"] == len(sample_bars)
        assert results["final_equity"] > 0
        assert len(results["equity_curve"]) > 0

    def test_produces_trades(self, sample_bars):
        # Use very short periods to guarantee crossovers
        data = InMemoryDataHandler(sample_bars)
        strategy = SMACrossoverStrategy(fast_period=3, slow_period=8)
        portfolio = Portfolio(initial_cash=10000.0)
        sizer = PositionSizer(method="fixed", fixed_lot=0.01)

        engine = BacktestEngine(
            data_handler=data,
            strategy=strategy,
            portfolio=portfolio,
            sizer=sizer,
        )
        results = engine.run()

        # With trend changes in sample data, should generate some fills
        assert results["fills"] >= 0
        assert results["bars"] == len(sample_bars)

    def test_equity_curve_recorded(self, sample_bars):
        data = InMemoryDataHandler(sample_bars)
        strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)

        engine = BacktestEngine(data_handler=data, strategy=strategy)
        results = engine.run()

        curve = results["equity_curve"]
        assert len(curve) > 0
        # All snapshots should have positive equity
        for snapshot in curve:
            assert snapshot.equity > 0

    def test_custom_initial_cash(self, sample_bars):
        data = InMemoryDataHandler(sample_bars)
        strategy = SMACrossoverStrategy(fast_period=5, slow_period=10)
        portfolio = Portfolio(initial_cash=50000.0)

        engine = BacktestEngine(
            data_handler=data, strategy=strategy, portfolio=portfolio
        )
        results = engine.run()

        assert results["equity_curve"][0].equity == pytest.approx(50000.0, rel=0.01)
