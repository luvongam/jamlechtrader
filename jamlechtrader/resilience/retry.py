"""Pre-configured retry decorators using tenacity."""

from __future__ import annotations

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from loguru import logger


def _log_retry(retry_state: RetryCallState) -> None:
    logger.warning(
        f"Retry attempt {retry_state.attempt_number} for "
        f"{retry_state.fn.__name__ if retry_state.fn else '?'}: "
        f"{retry_state.outcome.exception() if retry_state.outcome else 'unknown'}"
    )


mt5_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    before_sleep=_log_retry,
    reraise=True,
)

order_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=10),
    before_sleep=_log_retry,
    reraise=True,
)
