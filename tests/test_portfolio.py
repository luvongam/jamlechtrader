"""Tests for portfolio tracking and risk management."""

from datetime import datetime

import pytest

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import PortfolioSnapshot, Position
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskManager
from jamlechtrader.portfolio.sizing import PositionSizer


class TestPortfolio:
    def test_initial_state(self):
        p = Portfolio(initial_cash=10000.0)
        assert p.cash == 10000.0
        assert p.equity == 10000.0
        assert len(p.positions) == 0
        assert p.drawdown == 0.0

    def test_open_position(self):
        p = Portfolio(initial_cash=10000.0)
        fill = FillEvent(
            symbol="EURUSD",
            side=OrderSide.BUY,
            quantity=0.01,
            price=1.0500,
            commission=0.07,
        )
        p.on_fill(fill)
        assert "EURUSD" in p.positions
        assert p.positions["EURUSD"].side == OrderSide.BUY
        assert p.positions["EURUSD"].quantity == 0.01

    def test_close_position_pnl(self):
        p = Portfolio(initial_cash=10000.0)

        # Open
        p.on_fill(FillEvent(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.01,
            price=1.0500, commission=0.07,
        ))

        # Close
        p.on_fill(FillEvent(
            symbol="EURUSD", side=OrderSide.SELL, quantity=0.01,
            price=1.0600, commission=0.07,
        ))

        assert "EURUSD" not in p.positions
        assert len(p.closed_trades) == 1
        assert p.closed_trades[0]["pnl"] == pytest.approx(0.0100 * 0.01, abs=1e-8)

    def test_generate_order_new_position(self):
        p = Portfolio()
        signal = SignalEvent(symbol="EURUSD", side=OrderSide.BUY)
        order = p.generate_order(signal, quantity=0.01)
        assert order is not None
        assert order.symbol == "EURUSD"
        assert order.side == OrderSide.BUY

    def test_generate_order_same_direction_skips(self):
        p = Portfolio()
        p.positions["EURUSD"] = Position(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, entry_price=1.05
        )
        signal = SignalEvent(symbol="EURUSD", side=OrderSide.BUY)
        order = p.generate_order(signal, quantity=0.01)
        assert order is None

    def test_generate_order_opposite_direction_closes(self):
        p = Portfolio()
        p.positions["EURUSD"] = Position(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, entry_price=1.05
        )
        signal = SignalEvent(symbol="EURUSD", side=OrderSide.SELL)
        order = p.generate_order(signal, quantity=0.01)
        assert order is not None
        assert order.side == OrderSide.SELL  # Close the buy

    def test_snapshot(self):
        p = Portfolio(initial_cash=10000.0)
        snap = p.take_snapshot()
        assert snap.cash == 10000.0
        assert snap.equity == 10000.0

    def test_reset(self):
        p = Portfolio(initial_cash=10000.0)
        p.on_fill(FillEvent(
            symbol="EURUSD", side=OrderSide.BUY, quantity=0.01, price=1.0500
        ))
        p.reset()
        assert p.cash == 10000.0
        assert len(p.positions) == 0


class TestRiskManager:
    def _make_snapshot(self, equity=10000.0, n_positions=0):
        positions = [
            Position(symbol=f"SYM{i}", side=OrderSide.BUY, quantity=0.01, entry_price=1.0)
            for i in range(n_positions)
        ]
        return PortfolioSnapshot(
            cash=equity, equity=equity, positions=positions
        )

    def test_order_passes(self):
        from jamlechtrader.portfolio.risk import RiskLimits
        rm = RiskManager(limits=RiskLimits(max_position_size=1.0, max_open_positions=5))
        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)
        snap = self._make_snapshot()
        result = rm.check_order(order, snap)
        assert result is not None

    def test_max_positions_blocks(self):
        from jamlechtrader.portfolio.risk import RiskLimits
        rm = RiskManager(limits=RiskLimits(max_open_positions=2))
        order = OrderEvent(symbol="NEWPAIR", side=OrderSide.BUY, quantity=0.01)
        snap = self._make_snapshot(n_positions=2)
        result = rm.check_order(order, snap)
        assert result is None

    def test_clamps_oversize(self):
        from jamlechtrader.portfolio.risk import RiskLimits
        rm = RiskManager(limits=RiskLimits(max_position_size=0.5))
        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=1.0)
        snap = self._make_snapshot()
        result = rm.check_order(order, snap)
        assert result is not None
        assert result.quantity == 0.5

    def test_daily_drawdown_halt(self):
        from jamlechtrader.portfolio.risk import RiskLimits
        rm = RiskManager(limits=RiskLimits(max_daily_drawdown_pct=5.0))
        order = OrderEvent(symbol="EURUSD", side=OrderSide.BUY, quantity=0.01)

        # First call sets baseline
        snap1 = self._make_snapshot(equity=10000.0)
        rm.check_order(order, snap1)

        # Equity drops 6%
        snap2 = self._make_snapshot(equity=9400.0)
        result = rm.check_order(order, snap2)
        assert result is None
        assert rm.is_halted


class TestPositionSizer:
    def test_fixed(self):
        sizer = PositionSizer(method="fixed", fixed_lot=0.05)
        size = sizer.calculate(equity=10000.0)
        assert size == 0.05

    def test_risk_pct(self):
        sizer = PositionSizer(method="risk_pct", risk_pct=1.0)
        # 1% of 10000 = 100, stop distance 0.0050, pip value 10
        size = sizer.calculate(equity=10000.0, stop_distance=0.0050, pip_value=10.0)
        expected = 100.0 / (0.0050 * 10.0)  # = 2000
        # Clamped to max_lot=100.0
        assert size == 100.0

    def test_risk_pct_small_account(self):
        sizer = PositionSizer(method="risk_pct", risk_pct=1.0)
        size = sizer.calculate(equity=500.0, stop_distance=0.0050, pip_value=10.0)
        expected = 5.0 / (0.0050 * 10.0)  # = 100
        assert size == 100.0

    def test_atr_sizing(self):
        sizer = PositionSizer(method="atr", risk_pct=1.0, atr_multiplier=1.5)
        size = sizer.calculate(
            equity=10000.0, atr_value=0.0030, pip_value=10.0
        )
        # risk = 100, stop = 0.0030 * 1.5 = 0.0045, lots = 100 / (0.0045 * 10) = 2222
        # clamped to 100
        assert size == 100.0

    def test_no_stop_distance_falls_back(self):
        sizer = PositionSizer(method="risk_pct", fixed_lot=0.02)
        size = sizer.calculate(equity=10000.0, stop_distance=None)
        assert size == 0.02
