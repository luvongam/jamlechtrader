"""Mock MetaTrader5 module for testing on non-Windows platforms."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

# Create a mock MT5 module with all the constants we use
mock_mt5 = MagicMock(spec=[])

# Timeframe constants
mock_mt5.TIMEFRAME_M1 = 1
mock_mt5.TIMEFRAME_M2 = 2
mock_mt5.TIMEFRAME_M3 = 3
mock_mt5.TIMEFRAME_M4 = 4
mock_mt5.TIMEFRAME_M5 = 5
mock_mt5.TIMEFRAME_M6 = 6
mock_mt5.TIMEFRAME_M10 = 10
mock_mt5.TIMEFRAME_M12 = 12
mock_mt5.TIMEFRAME_M15 = 15
mock_mt5.TIMEFRAME_M20 = 20
mock_mt5.TIMEFRAME_M30 = 30
mock_mt5.TIMEFRAME_H1 = 16385
mock_mt5.TIMEFRAME_H2 = 16386
mock_mt5.TIMEFRAME_H3 = 16387
mock_mt5.TIMEFRAME_H4 = 16388
mock_mt5.TIMEFRAME_H6 = 16390
mock_mt5.TIMEFRAME_H8 = 16392
mock_mt5.TIMEFRAME_H12 = 16396
mock_mt5.TIMEFRAME_D1 = 16408
mock_mt5.TIMEFRAME_W1 = 32769
mock_mt5.TIMEFRAME_MN1 = 49153

# Order type constants
mock_mt5.ORDER_TYPE_BUY = 0
mock_mt5.ORDER_TYPE_SELL = 1
mock_mt5.ORDER_TYPE_BUY_LIMIT = 2
mock_mt5.ORDER_TYPE_SELL_LIMIT = 3
mock_mt5.ORDER_TYPE_BUY_STOP = 4
mock_mt5.ORDER_TYPE_SELL_STOP = 5
mock_mt5.ORDER_TYPE_BUY_STOP_LIMIT = 6
mock_mt5.ORDER_TYPE_SELL_STOP_LIMIT = 7

# Trade action constants
mock_mt5.TRADE_ACTION_DEAL = 1
mock_mt5.TRADE_ACTION_PENDING = 5
mock_mt5.TRADE_ACTION_SLTP = 6

# Return codes
mock_mt5.TRADE_RETCODE_DONE = 10009
mock_mt5.RES_S_OK = 1

# Order time constants
mock_mt5.ORDER_TIME_GTC = 0

# Filling constants
mock_mt5.ORDER_FILLING_IOC = 1

# Position type constants
mock_mt5.POSITION_TYPE_BUY = 0
mock_mt5.POSITION_TYPE_SELL = 1

# Tick flags
mock_mt5.COPY_TICKS_ALL = 1

# Functions (return None by default via MagicMock)
mock_mt5.initialize = MagicMock(return_value=True)
mock_mt5.login = MagicMock(return_value=True)
mock_mt5.shutdown = MagicMock()
mock_mt5.last_error = MagicMock(return_value=(0, "OK"))
mock_mt5.account_info = MagicMock(return_value=None)
mock_mt5.terminal_info = MagicMock(return_value=None)
mock_mt5.symbol_info = MagicMock(return_value=None)
mock_mt5.symbol_info_tick = MagicMock(return_value=None)
mock_mt5.symbol_select = MagicMock(return_value=True)
mock_mt5.symbols_get = MagicMock(return_value=None)
mock_mt5.copy_rates_range = MagicMock(return_value=None)
mock_mt5.copy_rates_from_pos = MagicMock(return_value=None)
mock_mt5.copy_ticks_range = MagicMock(return_value=None)
mock_mt5.order_send = MagicMock(return_value=None)
mock_mt5.positions_get = MagicMock(return_value=None)
mock_mt5.orders_get = MagicMock(return_value=None)


def install():
    """Install the mock MT5 module into sys.modules if not already present."""
    if "MetaTrader5" not in sys.modules:
        sys.modules["MetaTrader5"] = mock_mt5
