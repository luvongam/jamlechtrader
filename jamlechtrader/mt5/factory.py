"""Factory functions — return bridge or local MT5 classes based on settings."""

from __future__ import annotations

from jamlechtrader.config.settings import Settings


def create_mt5_connection(settings: Settings):
    """Return a BridgeMT5Connection when MT5_BRIDGE_URL is set, else MT5Connection."""
    if settings.mt5_bridge_url:
        from jamlechtrader.mt5.bridge_client import BridgeMT5Connection

        return BridgeMT5Connection(settings)

    from jamlechtrader.mt5.connection import MT5Connection

    return MT5Connection(settings)


def create_mt5_executor(settings: Settings):
    """Return a BridgeMT5Executor when MT5_BRIDGE_URL is set, else MT5Executor."""
    if settings.mt5_bridge_url:
        from jamlechtrader.mt5.bridge_client import BridgeMT5Executor

        return BridgeMT5Executor(settings.mt5_bridge_url)

    from jamlechtrader.mt5.executor import MT5Executor

    return MT5Executor()


def create_mt5_data(settings: Settings):
    """Return a BridgeMT5Data when MT5_BRIDGE_URL is set, else MT5Data."""
    if settings.mt5_bridge_url:
        from jamlechtrader.mt5.bridge_client import BridgeMT5Data

        return BridgeMT5Data(settings.mt5_bridge_url)

    from jamlechtrader.mt5.data import MT5Data

    return MT5Data()
