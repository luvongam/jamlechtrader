"""Custom exceptions for JamlechTrader."""


class JamlechTraderError(Exception):
    """Base exception for all JamlechTrader errors."""


class ConfigurationError(JamlechTraderError):
    """Configuration or settings error."""


class ConnectionError(JamlechTraderError):
    """MT5 or broker connection error."""


class DataError(JamlechTraderError):
    """Data retrieval or processing error."""


class ExecutionError(JamlechTraderError):
    """Order execution error."""


class RiskLimitError(JamlechTraderError):
    """Risk limit exceeded."""


class StrategyError(JamlechTraderError):
    """Strategy execution error."""


class ValidationError(JamlechTraderError):
    """Data validation error."""
