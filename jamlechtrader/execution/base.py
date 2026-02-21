"""Abstract execution handler."""

from abc import ABC, abstractmethod

from jamlechtrader.core.events import FillEvent, OrderEvent


class AbstractExecutionHandler(ABC):
    """Base class for all execution handlers."""

    @abstractmethod
    def execute_order(self, order: OrderEvent) -> FillEvent | None:
        """Execute an order and return a fill event, or None if rejected."""
