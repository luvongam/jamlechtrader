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
SMC_DEFAULT_SWING_LENGTH: Final[int] = 50
SMC_BOS_CLOSE_BREAK: Final[bool] = True
SMC_FVG_JOIN_CONSECUTIVE: Final[bool] = False
SMC_OB_CLOSE_MITIGATION: Final[bool] = False
SMC_LIQUIDITY_RANGE_PCT: Final[float] = 0.01
SMC_RETRACEMENT_DEEP_THRESHOLD: Final[float] = 78.6
SMC_OB_VOLUME_WEIGHT_FACTOR: Final[float] = 0.3
SMC_SWEPT_LIQUIDITY_RISK_BONUS: Final[float] = 10.0

# Timeouts and intervals
CONNECTION_TIMEOUT: Final[int] = 30
RETRY_ATTEMPTS: Final[int] = 3
HEARTBEAT_INTERVAL: Final[int] = 60

# Enterprise risk constants
DEFAULT_MAX_TOTAL_NOTIONAL: Final[float] = 1_000_000.0
DEFAULT_MAX_LEVERAGE_RATIO: Final[float] = 10.0
DEFAULT_MAX_MARGIN_UTILIZATION_PCT: Final[float] = 80.0
DEFAULT_VAR_CONFIDENCE: Final[float] = 0.95
DEFAULT_MAX_VAR_PCT: Final[float] = 5.0
KILL_SWITCH_DRAWDOWN_PCT: Final[float] = 10.0
KILL_SWITCH_MAX_LOSS: Final[float] = 50_000.0
KILL_SWITCH_CONSECUTIVE_LOSSES: Final[int] = 10
