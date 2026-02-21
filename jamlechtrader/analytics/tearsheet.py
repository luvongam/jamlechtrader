"""Generate quantstats tearsheet from backtest results."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from loguru import logger

from jamlechtrader.core.models import PortfolioSnapshot


def generate_tearsheet(
    equity_curve: list[PortfolioSnapshot],
    output_path: str = "tearsheet.html",
    benchmark: str = "SPY",
) -> Path:
    """Generate an HTML tearsheet using quantstats."""
    try:
        import quantstats as qs
    except ImportError:
        logger.error("quantstats not installed. Run: pip install quantstats")
        raise

    equities = pd.Series(
        {s.timestamp: s.equity for s in equity_curve}
    )
    equities.index = pd.to_datetime(equities.index)
    returns = equities.pct_change().dropna()

    qs.reports.html(
        returns,
        benchmark=benchmark,
        output=output_path,
        title="JamlechTrader Backtest",
    )

    path = Path(output_path)
    logger.info(f"Tearsheet saved to {path.absolute()}")
    return path
