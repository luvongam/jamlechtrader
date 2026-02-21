"""Application constants."""

from typing import Final

# Application metadata
APP_NAME: Final[str] = "JamlechTrader"
APP_VERSION: Final[str] = "0.1.0"

# Trading constants
DEFAULT_RISK_PER_TRADE: Final[float] = 0.02  # 2%
DEFAULT_MAX_DRAWDOWN: Final[float] = 0.05  # 5%
DEFAULT_MAX_POSITIONS: Final[int] = 5
MIN_RISK_REWARD_RATIO: Final[float] = 1.5

# SMC constants
SMC_ENTRY_TOLERANCE: Final[float] = 0.005  # 0.5%
SMC_RISK_THRESHOLD: Final[float] = 60.0
SMC_DEFAULT_LOOKBACK: Final[int] = 50

# Timeouts and intervals
CONNECTION_TIMEOUT: Final[int] = 30
RETRY_ATTEMPTS: Final[int] = 3
HEARTBEAT_INTERVAL: Final[int] = 60
