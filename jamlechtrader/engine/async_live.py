"""Async live trading engine — concurrent event processing with asyncio."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from jamlechtrader.core.async_events import AsyncEventBus
from jamlechtrader.core.enums import Timeframe
from jamlechtrader.core.events import MarketEvent
from jamlechtrader.mt5.async_wrapper import AsyncMT5
from jamlechtrader.mt5.connection import MT5Connection
from jamlechtrader.mt5.data import MT5Data
from jamlechtrader.mt5.executor import MT5Executor
from jamlechtrader.portfolio.portfolio import Portfolio
from jamlechtrader.portfolio.risk import RiskManager
from jamlechtrader.portfolio.sizing import PositionSizer
from jamlechtrader.resilience.dead_letter_queue import DeadLetterQueue
from jamlechtrader.strategy.base import AbstractStrategy

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jamlechtrader.audit.logger import AuditLogger


class AsyncLiveEngine:
    """Async live trading engine using concurrent asyncio tasks.

    Runs concurrent tasks for: event processing, market data polling,
    and health monitoring. The existing sync ``LiveEngine`` is untouched.
    """

    def __init__(
        self,
        connection: MT5Connection,
        strategy: AbstractStrategy,
        symbol: str,
        timeframe: Timeframe,
        portfolio: Portfolio | None = None,
        risk_manager: RiskManager | None = None,
        sizer: PositionSizer | None = None,
        db_session: AsyncSession | None = None,
        audit_logger: AuditLogger | None = None,
        mt5_data: MT5Data | None = None,
        mt5_executor: MT5Executor | None = None,
    ) -> None:
        self.connection = connection
        self.strategy = strategy
        self.symbol = symbol
        self.timeframe = timeframe
        self.portfolio = portfolio or Portfolio()
        self.risk_manager = risk_manager or RiskManager()
        self.sizer = sizer or PositionSizer()
        self._db_session = db_session
        self._audit_logger = audit_logger

        self._async_mt5 = AsyncMT5(connection, mt5_executor or MT5Executor(), mt5_data or MT5Data())
        self._event_bus = AsyncEventBus()
        self._dead_letter_queue = DeadLetterQueue()
        self._running = False
        self._last_bar_time: datetime | None = None

    async def run(self) -> None:
        """Start the async live trading engine."""
        if not self.connection.is_connected:
            connected = await self._async_mt5.connect()
            if not connected:
                raise RuntimeError("Failed to connect to MT5")

        self._running = True
        self.strategy.on_start()
        logger.info(f"ASYNC LIVE engine started: {self.symbol} {self.timeframe.value}")

        if self._audit_logger:
            await self._audit_logger.log_system_event("ASYNC_ENGINE_STARTED", {
                "symbol": self.symbol, "timeframe": self.timeframe.value
            })

        try:
            await asyncio.gather(
                self._event_bus.process_events(),
                self._market_data_loop(),
                self._health_check_loop(),
            )
        except asyncio.CancelledError:
            logger.info("Async live engine cancelled")
        finally:
            self._event_bus.stop()
            self.strategy.on_stop()
            self._async_mt5.shutdown()
            logger.info("Async live engine stopped")

    async def _market_data_loop(self) -> None:
        """Poll for new bars and process signals."""
        while self._running:
            try:
                connected = await self._async_mt5.is_connected()
                if not connected:
                    logger.warning("MT5 not connected, waiting...")
                    await asyncio.sleep(5)
                    continue

                bars = await self._async_mt5.get_latest_bars(
                    self.symbol, self.timeframe, count=1
                )
                if not bars:
                    await asyncio.sleep(1)
                    continue

                current_bar = bars[-1]

                if (
                    self._last_bar_time
                    and current_bar.timestamp <= self._last_bar_time
                ):
                    await asyncio.sleep(1)
                    continue

                self._last_bar_time = current_bar.timestamp
                logger.debug(f"New bar: {current_bar.timestamp}")

                self.portfolio.update_market_price(self.symbol, current_bar.close)

                market_event = MarketEvent(
                    symbol=self.symbol,
                    timestamp=current_bar.timestamp,
                    data=current_bar,
                )
                await self._event_bus.publish(market_event)

                signals = self.strategy.on_bar(market_event)

                for signal in signals:
                    quantity = self.sizer.calculate(
                        equity=self.portfolio.equity, bar=current_bar
                    )
                    order = self.portfolio.generate_order(signal, quantity)
                    if order is None:
                        continue

                    snapshot = self.portfolio.take_snapshot(current_bar.timestamp)
                    checked_order = self.risk_manager.check_order(order, snapshot)
                    if checked_order is None:
                        continue

                    from jamlechtrader.core.models import Order

                    order_model = Order(
                        symbol=checked_order.symbol,
                        side=checked_order.side,
                        quantity=checked_order.quantity,
                        price=checked_order.price,
                        stop_loss=checked_order.stop_loss,
                        take_profit=checked_order.take_profit,
                    )

                    fill = await self._async_mt5.send_order(order_model)
                    if fill is not None:
                        from jamlechtrader.core.events import FillEvent

                        fill_event = FillEvent(
                            symbol=fill.symbol,
                            side=fill.side,
                            quantity=fill.quantity,
                            price=fill.price,
                            order_id=fill.order_id,
                        )
                        self.portfolio.on_fill(fill_event)
                        logger.info(
                            f"ASYNC FILL: {fill.side.value} {fill.quantity} "
                            f"{fill.symbol} @ {fill.price}"
                        )
                    else:
                        self._dead_letter_queue.add(
                            {
                                "symbol": checked_order.symbol,
                                "side": checked_order.side.value,
                                "quantity": checked_order.quantity,
                            },
                            "Async execution returned no fill",
                        )

                self.portfolio.take_snapshot(current_bar.timestamp)
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Market data loop error: {e}")
                await asyncio.sleep(5)

    async def _health_check_loop(self) -> None:
        """Periodic health check and auto-reconnect."""
        while self._running:
            try:
                connected = await self._async_mt5.is_connected()
                if not connected:
                    logger.warning("Health check: MT5 disconnected, reconnecting...")
                    await self._async_mt5.connect()
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(5)

    def stop(self) -> None:
        self._running = False
        self._event_bus.stop()

    @property
    def dead_letter_queue(self) -> DeadLetterQueue:
        return self._dead_letter_queue
