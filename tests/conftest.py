"""Shared test fixtures."""

# Install MT5 mock before any jamlechtrader imports
from tests.mt5_mock import install as _install_mt5_mock

_install_mt5_mock()

from datetime import datetime, timedelta

import pytest

from jamlechtrader.core.enums import OrderSide
from jamlechtrader.core.events import FillEvent, MarketEvent, OrderEvent, SignalEvent
from jamlechtrader.core.models import Bar, Position, Tick


@pytest.fixture
def sample_bars() -> list[Bar]:
    """Generate sample OHLCV bars for testing."""
    bars = []
    base_time = datetime(2023, 1, 1)
    # Generate a simple uptrend followed by a downtrend
    prices = [
        1.0500, 1.0510, 1.0520, 1.0515, 1.0530, 1.0545, 1.0560, 1.0550,
        1.0570, 1.0580, 1.0590, 1.0600, 1.0610, 1.0605, 1.0620, 1.0630,
        1.0640, 1.0635, 1.0620, 1.0610, 1.0600, 1.0590, 1.0580, 1.0570,
        1.0560, 1.0550, 1.0540, 1.0530, 1.0520, 1.0510, 1.0500, 1.0490,
        1.0480, 1.0470, 1.0475, 1.0480, 1.0490, 1.0500, 1.0510, 1.0520,
        1.0530, 1.0540, 1.0550, 1.0545, 1.0560, 1.0570, 1.0580, 1.0575,
        1.0590, 1.0600,
    ]
    for i, close in enumerate(prices):
        high = close + 0.0010
        low = close - 0.0010
        open_price = prices[i - 1] if i > 0 else close
        bars.append(
            Bar(
                symbol="EURUSD",
                timestamp=base_time + timedelta(hours=i),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=100.0,
                spread=2,
                tick_volume=100.0,
            )
        )
    return bars


@pytest.fixture
def sample_tick() -> Tick:
    return Tick(
        symbol="EURUSD",
        timestamp=datetime(2023, 6, 1, 12, 0),
        bid=1.0850,
        ask=1.0852,
    )


@pytest.fixture
def sample_position() -> Position:
    return Position(
        symbol="EURUSD",
        side=OrderSide.BUY,
        quantity=0.01,
        entry_price=1.0800,
        current_price=1.0850,
    )


# --- Phase 7 additions ---

@pytest.fixture
def enhanced_mt5_mock():
    """Provide a configurable MT5 mock server."""
    from tests.mt5_mock_enhanced import MT5MockConfig, MT5MockServer

    server = MT5MockServer()
    server.install()
    return server


@pytest.fixture
def enhanced_mt5_mock_with_failures():
    """MT5 mock with 20% failure rate for chaos testing."""
    from tests.mt5_mock_enhanced import MT5MockConfig, MT5MockServer

    config = MT5MockConfig(failure_rate=0.2, latency_ms=(1, 10))
    server = MT5MockServer(config)
    server.install()
    return server


@pytest.fixture
def portfolio():
    """Fresh portfolio with 10k cash."""
    from jamlechtrader.portfolio.portfolio import Portfolio
    return Portfolio(initial_cash=10_000.0)


@pytest.fixture
def risk_manager():
    """Default risk manager."""
    from jamlechtrader.portfolio.risk import RiskManager
    return RiskManager()


@pytest.fixture
def enterprise_risk_manager():
    """Enterprise risk manager with tight limits for testing."""
    from jamlechtrader.portfolio.enterprise_risk import EnterpriseRiskLimits, EnterpriseRiskManager
    limits = EnterpriseRiskLimits(
        max_open_positions=3,
        max_daily_drawdown_pct=5.0,
        per_symbol_max_position={"EURUSD": 1.0, "GBPUSD": 0.5},
        kill_switch_consecutive_losses=5,
    )
    return EnterpriseRiskManager(limits=limits)


@pytest.fixture
def order_manager():
    """Fresh order manager without executor."""
    from jamlechtrader.oms.order_manager import OrderManager
    return OrderManager()
