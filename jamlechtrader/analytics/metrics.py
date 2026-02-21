"""Performance metrics: Sharpe, Sortino, max drawdown, win rate, etc."""

from __future__ import annotations

import numpy as np
import pandas as pd

from jamlechtrader.core.models import PortfolioSnapshot


def calculate_metrics(
    equity_curve: list[PortfolioSnapshot],
    closed_trades: list[dict],
    risk_free_rate: float = 0.0,
) -> dict:
    """Calculate comprehensive performance metrics from backtest results."""
    if not equity_curve:
        return {}

    equities = pd.Series([s.equity for s in equity_curve])
    returns = equities.pct_change().dropna()

    metrics: dict = {}

    # Basic
    metrics["initial_equity"] = equities.iloc[0]
    metrics["final_equity"] = equities.iloc[-1]
    metrics["total_return_pct"] = (equities.iloc[-1] / equities.iloc[0] - 1) * 100
    metrics["total_trades"] = len(closed_trades)

    if returns.empty:
        return metrics

    # Annualized return (assume daily equity snapshots as approximation)
    n_periods = len(returns)
    if n_periods > 1:
        total_return = equities.iloc[-1] / equities.iloc[0]
        metrics["cagr"] = (total_return ** (252 / n_periods) - 1) * 100
    else:
        metrics["cagr"] = 0.0

    # Sharpe ratio (annualized)
    if returns.std() > 0:
        excess = returns.mean() - risk_free_rate / 252
        metrics["sharpe_ratio"] = (excess / returns.std()) * np.sqrt(252)
    else:
        metrics["sharpe_ratio"] = 0.0

    # Sortino ratio
    downside = returns[returns < 0]
    if len(downside) > 0 and downside.std() > 0:
        metrics["sortino_ratio"] = (
            (returns.mean() - risk_free_rate / 252) / downside.std()
        ) * np.sqrt(252)
    else:
        metrics["sortino_ratio"] = 0.0

    # Max drawdown
    peak = equities.expanding().max()
    drawdowns = (equities - peak) / peak
    metrics["max_drawdown_pct"] = abs(drawdowns.min()) * 100

    # Calmar ratio
    if metrics["max_drawdown_pct"] > 0:
        metrics["calmar_ratio"] = metrics["cagr"] / metrics["max_drawdown_pct"]
    else:
        metrics["calmar_ratio"] = 0.0

    # Trade statistics
    if closed_trades:
        pnls = [t["pnl"] for t in closed_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        metrics["win_rate"] = len(wins) / len(pnls) * 100 if pnls else 0.0
        metrics["avg_win"] = np.mean(wins) if wins else 0.0
        metrics["avg_loss"] = np.mean(losses) if losses else 0.0
        metrics["profit_factor"] = (
            abs(sum(wins) / sum(losses)) if losses and sum(losses) != 0 else float("inf")
        )
        metrics["avg_win_loss_ratio"] = (
            abs(metrics["avg_win"] / metrics["avg_loss"])
            if metrics["avg_loss"] != 0
            else float("inf")
        )
        metrics["expectancy"] = np.mean(pnls) if pnls else 0.0
        metrics["total_pnl"] = sum(pnls)
    else:
        metrics["win_rate"] = 0.0
        metrics["profit_factor"] = 0.0
        metrics["expectancy"] = 0.0
        metrics["total_pnl"] = 0.0

    return metrics


def format_metrics(metrics: dict) -> str:
    """Format metrics dict as a readable string."""
    lines = ["=" * 50, "  PERFORMANCE METRICS", "=" * 50]
    fmt = {
        "initial_equity": ("Initial Equity", "${:,.2f}"),
        "final_equity": ("Final Equity", "${:,.2f}"),
        "total_return_pct": ("Total Return", "{:.2f}%"),
        "cagr": ("CAGR", "{:.2f}%"),
        "sharpe_ratio": ("Sharpe Ratio", "{:.3f}"),
        "sortino_ratio": ("Sortino Ratio", "{:.3f}"),
        "calmar_ratio": ("Calmar Ratio", "{:.3f}"),
        "max_drawdown_pct": ("Max Drawdown", "{:.2f}%"),
        "total_trades": ("Total Trades", "{}"),
        "win_rate": ("Win Rate", "{:.1f}%"),
        "profit_factor": ("Profit Factor", "{:.2f}"),
        "avg_win_loss_ratio": ("Avg Win/Loss", "{:.2f}"),
        "expectancy": ("Expectancy", "${:.2f}"),
        "total_pnl": ("Total P&L", "${:,.2f}"),
    }
    for key, (label, pattern) in fmt.items():
        if key in metrics:
            val = metrics[key]
            lines.append(f"  {label:<20s} {pattern.format(val)}")
    lines.append("=" * 50)
    return "\n".join(lines)
