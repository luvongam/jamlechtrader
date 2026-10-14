"""Custom exceptions for JamlechTrader."""


class JamlechTraderError(Exception):
    """Base exception for all JamlechTrader errors."""


class ConfigurationError(JamlechTraderError):
    """Configuration or settings error."""


class ConnectionError(JamlechTraderError):
    """Broker connection error."""


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


class InvalidTransitionError(JamlechTraderError):
    """Invalid order state transition."""


class OrderNotFoundError(JamlechTraderError):
    """Order not found in the OMS."""


class AmendmentError(JamlechTraderError):
    """Order amendment failure."""
