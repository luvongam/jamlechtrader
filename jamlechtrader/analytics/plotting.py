"""Plotting: equity curve, drawdown chart, trade overlay."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from loguru import logger

from jamlechtrader.core.models import PortfolioSnapshot


def plot_equity_curve(
    equity_curve: list[PortfolioSnapshot],
    title: str = "Equity Curve",
    save_path: str | None = None,
) -> None:
    """Plot equity over time."""
    timestamps = [s.timestamp for s in equity_curve]
    equities = [s.equity for s in equity_curve]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(timestamps, equities, linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        logger.info(f"Equity curve saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_drawdown(
    equity_curve: list[PortfolioSnapshot],
    title: str = "Drawdown",
    save_path: str | None = None,
) -> None:
    """Plot drawdown percentage over time."""
    equities = pd.Series(
        {s.timestamp: s.equity for s in equity_curve}
    )
    peak = equities.expanding().max()
    drawdown = (equities - peak) / peak * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.fill_between(drawdown.index, drawdown.values, 0, alpha=0.5, color="red")
    ax.set_title(title)
    ax.set_xlabel("Time")
    ax.set_ylabel("Drawdown (%)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        logger.info(f"Drawdown chart saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)


def plot_monthly_returns(
    equity_curve: list[PortfolioSnapshot],
    title: str = "Monthly Returns Heatmap",
    save_path: str | None = None,
) -> None:
    """Plot monthly returns as a heatmap."""
    equities = pd.Series(
        {s.timestamp: s.equity for s in equity_curve}
    )
    equities.index = pd.to_datetime(equities.index)
    monthly = equities.resample("ME").last().pct_change().dropna() * 100

    if monthly.empty:
        logger.warning("Not enough data for monthly returns heatmap")
        return

    # Build year × month matrix
    df = pd.DataFrame({"return": monthly})
    df["year"] = df.index.year
    df["month"] = df.index.month
    pivot = df.pivot_table(values="return", index="year", columns="month")

    month_names = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ]
    pivot.columns = [month_names[m - 1] for m in pivot.columns]

    fig, ax = plt.subplots(figsize=(12, max(3, len(pivot))))
    im = ax.imshow(pivot.values, cmap="RdYlGn", aspect="auto")

    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not pd.isna(val):
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center", fontsize=8)

    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="Return (%)")
    fig.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150)
        logger.info(f"Monthly returns saved to {save_path}")
    else:
        plt.show()
    plt.close(fig)
