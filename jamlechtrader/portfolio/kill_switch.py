"""Emergency kill switch — halt trading and optionally close all positions."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from jamlechtrader.mt5.executor import MT5Executor
    from jamlechtrader.core.models import Position


class KillSwitch:
    """Emergency trading halt with optional position liquidation.

    Once triggered, requires an authorization code to reset.
    """

    def __init__(self, executor: MT5Executor | None = None) -> None:
        self._executor = executor
        self._triggered = False
        self._trigger_time: datetime | None = None
        self._trigger_reason: str = ""
        self._reset_code: str | None = None

    @property
    def is_triggered(self) -> bool:
        return self._triggered

    @property
    def trigger_reason(self) -> str:
        return self._trigger_reason

    @property
    def trigger_time(self) -> datetime | None:
        return self._trigger_time

    def trigger(self, reason: str, close_positions: bool = False) -> str:
        """Trigger the kill switch. Returns a reset authorization code."""
        self._triggered = True
        self._trigger_time = datetime.now(tz=UTC)
        self._trigger_reason = reason
        self._reset_code = secrets.token_hex(16)

        logger.critical(f"KILL SWITCH TRIGGERED: {reason}")

        if close_positions and self._executor:
            self.close_all_positions()

        return self._reset_code

    def close_all_positions(self) -> list[str]:
        """Emergency liquidation of all open positions."""
        if self._executor is None:
            logger.error("No executor available for position liquidation")
            return []

        closed = []
        positions = self._executor.get_positions()
        for pos in positions:
            try:
                fill = self._executor.close_position(pos)
                if fill is not None:
                    closed.append(pos.symbol)
                    logger.info(f"Emergency close: {pos.symbol} @ {fill.price}")
                else:
                    logger.error(f"Failed to emergency close: {pos.symbol}")
            except Exception as e:
                logger.error(f"Emergency close error for {pos.symbol}: {e}")

        logger.info(f"Emergency liquidation complete: {len(closed)}/{len(positions)} positions closed")
        return closed

    def reset(self, authorization_code: str) -> bool:
        """Reset the kill switch. Requires the authorization code returned by trigger()."""
        if not self._triggered:
            return True

        if self._reset_code is None or authorization_code != self._reset_code:
            logger.warning("Kill switch reset failed — invalid authorization code")
            return False

        self._triggered = False
        self._trigger_time = None
        self._trigger_reason = ""
        self._reset_code = None
        logger.info("Kill switch reset successfully")
        return True
