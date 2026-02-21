"""MT5 compatibility shim for non-Windows platforms.

When MetaTrader5 is not installable (Linux/macOS), this module patches
sys.modules with a mock that provides all the constants and stub functions
the codebase relies on.  This allows CLI commands like ``backtest`` —
which never touch the live MT5 terminal — to run inside a container.
"""

from __future__ import annotations

import sys
from types import ModuleType
from unittest.mock import MagicMock


def _build_mock() -> ModuleType:
    """Create a mock MetaTrader5 module with all required constants."""
    mock = MagicMock(spec=[])

    # Timeframe constants
    mock.TIMEFRAME_M1 = 1
    mock.TIMEFRAME_M2 = 2
    mock.TIMEFRAME_M3 = 3
    mock.TIMEFRAME_M4 = 4
    mock.TIMEFRAME_M5 = 5
    mock.TIMEFRAME_M6 = 6
    mock.TIMEFRAME_M10 = 10
    mock.TIMEFRAME_M12 = 12
    mock.TIMEFRAME_M15 = 15
    mock.TIMEFRAME_M20 = 20
    mock.TIMEFRAME_M30 = 30
    mock.TIMEFRAME_H1 = 16385
    mock.TIMEFRAME_H2 = 16386
    mock.TIMEFRAME_H3 = 16387
    mock.TIMEFRAME_H4 = 16388
    mock.TIMEFRAME_H6 = 16390
    mock.TIMEFRAME_H8 = 16392
    mock.TIMEFRAME_H12 = 16396
    mock.TIMEFRAME_D1 = 16408
    mock.TIMEFRAME_W1 = 32769
    mock.TIMEFRAME_MN1 = 49153

    # Order type constants
    mock.ORDER_TYPE_BUY = 0
    mock.ORDER_TYPE_SELL = 1
    mock.ORDER_TYPE_BUY_LIMIT = 2
    mock.ORDER_TYPE_SELL_LIMIT = 3
    mock.ORDER_TYPE_BUY_STOP = 4
    mock.ORDER_TYPE_SELL_STOP = 5
    mock.ORDER_TYPE_BUY_STOP_LIMIT = 6
    mock.ORDER_TYPE_SELL_STOP_LIMIT = 7

    # Trade action constants
    mock.TRADE_ACTION_DEAL = 1
    mock.TRADE_ACTION_PENDING = 5
    mock.TRADE_ACTION_SLTP = 6

    # Return codes
    mock.TRADE_RETCODE_DONE = 10009
    mock.RES_S_OK = 1

    # Order time constants
    mock.ORDER_TIME_GTC = 0

    # Filling constants
    mock.ORDER_FILLING_IOC = 1

    # Position type constants
    mock.POSITION_TYPE_BUY = 0
    mock.POSITION_TYPE_SELL = 1

    # Tick flags
    mock.COPY_TICKS_ALL = 1

    # Stub functions (return safe defaults)
    mock.initialize = MagicMock(return_value=True)
    mock.login = MagicMock(return_value=True)
    mock.shutdown = MagicMock()
    mock.last_error = MagicMock(return_value=(0, "OK"))
    mock.account_info = MagicMock(return_value=None)
    mock.terminal_info = MagicMock(return_value=None)
    mock.symbol_info = MagicMock(return_value=None)
    mock.symbol_info_tick = MagicMock(return_value=None)
    mock.symbol_select = MagicMock(return_value=True)
    mock.symbols_get = MagicMock(return_value=None)
    mock.copy_rates_range = MagicMock(return_value=None)
    mock.copy_rates_from_pos = MagicMock(return_value=None)
    mock.copy_ticks_range = MagicMock(return_value=None)
    mock.order_send = MagicMock(return_value=None)
    mock.positions_get = MagicMock(return_value=None)
    mock.orders_get = MagicMock(return_value=None)

    return mock


def ensure_mt5() -> None:
    """Ensure ``import MetaTrader5`` succeeds.

    On Windows with MT5 installed this is a no-op.  On Linux/macOS the
    real package cannot be installed, so we inject a mock into
    ``sys.modules`` that provides every constant and function the
    codebase references.
    """
    try:
        import MetaTrader5  # noqa: F401
    except ImportError:
        sys.modules["MetaTrader5"] = _build_mock()
