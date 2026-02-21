"""Enterprise performance metrics for quantitative trading."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from jamlechtrader.core.models import Trade


@dataclass(frozen=True)
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_duration: int
    win_rate: float
    profit_factor: float
    avg_win: float
    avg_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_trade_duration: float
    expectancy: float
    risk_reward_ratio: float


class PerformanceAnalyzer:
    """Analyze trading performance with institutional metrics."""

    @staticmethod
    def calculate_returns(equity_curve: pd.Series) -> pd.Series:
        """Calculate returns from equity curve."""
        return equity_curve.pct_change().fillna(0)

    @staticmethod
    def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) == 0 or returns.std() == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / 252
        return np.sqrt(252) * excess_returns.mean() / returns.std()

    @staticmethod
    def sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(returns) == 0:
            return 0.0
        excess_returns = returns - risk_free_rate / 252
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        return np.sqrt(252) * excess_returns.mean() / downside_returns.std()

    @staticmethod
    def max_drawdown(equity_curve: pd.Series) -> tuple[float, int]:
        """Calculate maximum drawdown and duration."""
        if len(equity_curve) == 0:
            return 0.0, 0
        
        cummax = equity_curve.cummax()
        drawdown = (equity_curve - cummax) / cummax
        max_dd = drawdown.min()
        
        # Calculate duration
        is_drawdown = drawdown < 0
        drawdown_periods = is_drawdown.astype(int).groupby(
            (is_drawdown != is_drawdown.shift()).cumsum()
        ).sum()
        max_duration = drawdown_periods.max() if len(drawdown_periods) > 0 else 0
        
        return abs(max_dd), int(max_duration)

    @staticmethod
    def calmar_ratio(returns: pd.Series, max_dd: float) -> float:
        """Calculate Calmar ratio."""
        if max_dd == 0:
            return 0.0
        annual_return = (1 + returns.mean()) ** 252 - 1
        return annual_return / max_dd

    @staticmethod
    def analyze_trades(trades: list[Trade]) -> dict:
        """Analyze trade statistics."""
        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "risk_reward_ratio": 0.0,
            }
        
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl < 0]
        
        total_wins = sum(t.pnl for t in winning)
        total_losses = abs(sum(t.pnl for t in losing))
        
        return {
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(trades) if trades else 0.0,
            "avg_win": total_wins / len(winning) if winning else 0.0,
            "avg_loss": total_losses / len(losing) if losing else 0.0,
            "profit_factor": total_wins / total_losses if total_losses > 0 else 0.0,
            "expectancy": sum(t.pnl for t in trades) / len(trades),
            "risk_reward_ratio": (total_wins / len(winning)) / (total_losses / len(losing))
            if winning and losing else 0.0,
        }

    @classmethod
    def calculate_metrics(
        cls,
        equity_curve: pd.Series,
        trades: list[Trade],
        risk_free_rate: float = 0.02
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        returns = cls.calculate_returns(equity_curve)
        max_dd, max_dd_duration = cls.max_drawdown(equity_curve)
        trade_stats = cls.analyze_trades(trades)
        
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) if len(equity_curve) > 0 else 0.0
        annualized_return = (1 + total_return) ** (252 / len(equity_curve)) - 1 if len(equity_curve) > 0 else 0.0
        
        return PerformanceMetrics(
            total_return=total_return,
            annualized_return=annualized_return,
            sharpe_ratio=cls.sharpe_ratio(returns, risk_free_rate),
            sortino_ratio=cls.sortino_ratio(returns, risk_free_rate),
            calmar_ratio=cls.calmar_ratio(returns, max_dd),
            max_drawdown=max_dd,
            max_drawdown_duration=max_dd_duration,
            win_rate=trade_stats["win_rate"],
            profit_factor=trade_stats["profit_factor"],
            avg_win=trade_stats["avg_win"],
            avg_loss=trade_stats["avg_loss"],
            total_trades=trade_stats["total_trades"],
            winning_trades=trade_stats["winning_trades"],
            losing_trades=trade_stats["losing_trades"],
            avg_trade_duration=0.0,  # TODO: Calculate from trade timestamps
            expectancy=trade_stats["expectancy"],
            risk_reward_ratio=trade_stats["risk_reward_ratio"],
        )

    @staticmethod
    def format_metrics(metrics: PerformanceMetrics) -> str:
        """Format metrics for display."""
        return f"""
Performance Metrics
{'=' * 50}
Total Return:        {metrics.total_return:>10.2%}
Annualized Return:   {metrics.annualized_return:>10.2%}
Sharpe Ratio:        {metrics.sharpe_ratio:>10.2f}
Sortino Ratio:       {metrics.sortino_ratio:>10.2f}
Calmar Ratio:        {metrics.calmar_ratio:>10.2f}
Max Drawdown:        {metrics.max_drawdown:>10.2%}
Max DD Duration:     {metrics.max_drawdown_duration:>10} bars

Trade Statistics
{'=' * 50}
Total Trades:        {metrics.total_trades:>10}
Winning Trades:      {metrics.winning_trades:>10}
Losing Trades:       {metrics.losing_trades:>10}
Win Rate:            {metrics.win_rate:>10.2%}
Profit Factor:       {metrics.profit_factor:>10.2f}
Avg Win:             {metrics.avg_win:>10.2f}
Avg Loss:            {metrics.avg_loss:>10.2f}
Expectancy:          {metrics.expectancy:>10.2f}
Risk/Reward:         {metrics.risk_reward_ratio:>10.2f}
"""
