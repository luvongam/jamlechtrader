"""Integration tests for smartmoneyconcepts package integration."""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from jamlechtrader.analytics.enhanced_smc import SMCAnalyzer
from jamlechtrader.analytics.smart_money import SmartMoneyAnalyzer
from jamlechtrader.core.events import MarketEvent
from jamlechtrader.core.models import Bar
from jamlechtrader.portfolio.risk import RiskLimits, create_risk_manager
from jamlechtrader.portfolio.smart_money_risk import SmartMoneyRiskManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_bars_df(sample_bars) -> pd.DataFrame:
    """Convert sample_bars to a DataFrame suitable for SMC analysis."""
    rows = []
    for bar in sample_bars:
        rows.append({
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        })
    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex([bar.timestamp for bar in sample_bars])
    return df


@pytest.fixture
def large_bars_df() -> pd.DataFrame:
    """Generate a larger OHLCV dataset with clear swing structure."""
    np.random.seed(42)
    n = 200
    base_time = datetime(2023, 1, 1)
    # Trending price series with swings
    prices = [1.05]
    for i in range(1, n):
        trend = 0.0002 * np.sin(i / 20)
        noise = np.random.normal(0, 0.001)
        prices.append(prices[-1] + trend + noise)

    rows = []
    for i, close in enumerate(prices):
        high = close + abs(np.random.normal(0, 0.001))
        low = close - abs(np.random.normal(0, 0.001))
        open_price = prices[i - 1] if i > 0 else close
        rows.append({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 100 + np.random.randint(0, 200),
        })

    df = pd.DataFrame(rows)
    df.index = pd.DatetimeIndex([base_time + timedelta(hours=i) for i in range(n)])
    return df


@pytest.fixture
def smc_analyzer():
    """SMCAnalyzer with small swing length suitable for test data."""
    return SMCAnalyzer(swing_length=5)


@pytest.fixture
def smc_risk_manager():
    """SmartMoneyRiskManager with default limits."""
    limits = RiskLimits()
    return SmartMoneyRiskManager(limits=limits, smc_lookback=50)


# ---------------------------------------------------------------------------
# SMCAnalyzer adapter tests
# ---------------------------------------------------------------------------


class TestSMCAnalyzerAdapter:
    """Verify SMCAnalyzer methods return expected columns from the package."""

    def test_swing_highs_lows_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.swing_highs_lows(sample_bars_df)
        assert "HighLow" in result.columns
        assert "Level" in result.columns
        assert len(result) == len(sample_bars_df)

    def test_swing_highs_lows_values(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.swing_highs_lows(sample_bars_df)
        valid = result["HighLow"].dropna()
        # Should only contain 1 (high) and -1 (low)
        assert set(valid.unique()).issubset({1, -1})

    def test_bos_choch_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.bos_choch(sample_bars_df)
        assert "BOS" in result.columns
        assert "CHOCH" in result.columns
        assert "Level" in result.columns
        assert "BrokenIndex" in result.columns

    def test_order_blocks_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.order_blocks(sample_bars_df)
        assert "OB" in result.columns
        assert "Top" in result.columns
        assert "Bottom" in result.columns
        assert "OBVolume" in result.columns
        assert "Percentage" in result.columns

    def test_fair_value_gaps_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.fair_value_gaps(sample_bars_df)
        assert "FVG" in result.columns
        assert "Top" in result.columns
        assert "Bottom" in result.columns
        assert "MitigatedIndex" in result.columns

    def test_liquidity_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.liquidity(sample_bars_df)
        assert "Liquidity" in result.columns
        assert "Level" in result.columns
        assert "End" in result.columns
        assert "Swept" in result.columns

    def test_retracements_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.retracements(sample_bars_df)
        assert "Direction" in result.columns
        assert "CurrentRetracement%" in result.columns
        assert "DeepestRetracement%" in result.columns

    def test_previous_high_low_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.previous_high_low(sample_bars_df)
        assert "PreviousHigh" in result.columns
        assert "PreviousLow" in result.columns

    def test_sessions_columns(self, smc_analyzer, sample_bars_df):
        result = smc_analyzer.sessions(sample_bars_df, session="London")
        assert "Active" in result.columns
        assert "High" in result.columns
        assert "Low" in result.columns

    def test_result_index_matches_input(self, smc_analyzer, sample_bars_df):
        """All results should preserve the original DataFrame index."""
        for method in [
            smc_analyzer.swing_highs_lows,
            smc_analyzer.fair_value_gaps,
            smc_analyzer.order_blocks,
            smc_analyzer.liquidity,
            smc_analyzer.retracements,
        ]:
            result = method(sample_bars_df)
            assert result.index.equals(sample_bars_df.index), f"{method.__name__} index mismatch"

    def test_works_with_larger_dataset(self, large_bars_df):
        analyzer = SMCAnalyzer(swing_length=10)
        # All methods should run without error
        swings = analyzer.swing_highs_lows(large_bars_df)
        assert len(swings) == len(large_bars_df)

        bos = analyzer.bos_choch(large_bars_df)
        assert len(bos) == len(large_bars_df)

        ob = analyzer.order_blocks(large_bars_df)
        assert len(ob) == len(large_bars_df)

        fvg = analyzer.fair_value_gaps(large_bars_df)
        assert len(fvg) == len(large_bars_df)

        liq = analyzer.liquidity(large_bars_df)
        assert len(liq) == len(large_bars_df)

        ret = analyzer.retracements(large_bars_df)
        assert len(ret) == len(large_bars_df)


# ---------------------------------------------------------------------------
# SmartMoneyAnalyzer tests
# ---------------------------------------------------------------------------


class TestSmartMoneyAnalyzer:
    """Verify SmartMoneyAnalyzer enriched analysis."""

    def test_analyze_returns_enriched_fields(self, sample_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=20)
        result = analyzer.analyze(sample_bars_df)

        assert "market_structure" in result
        assert "risk_score" in result
        assert "bias" in result
        assert "retracement_pct" in result
        assert "mitigated_fvg_count" in result
        assert "swept_liquidity_count" in result
        assert "ob_volume_weighted_score" in result

    def test_analyze_risk_score_range(self, sample_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=20)
        result = analyzer.analyze(sample_bars_df)
        assert 0 <= result["risk_score"] <= 100

    def test_analyze_retracement_is_number(self, sample_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=20)
        result = analyzer.analyze(sample_bars_df)
        assert isinstance(result["retracement_pct"], float)

    def test_analyze_counts_are_ints(self, sample_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=20)
        result = analyzer.analyze(sample_bars_df)
        assert isinstance(result["mitigated_fvg_count"], int)
        assert isinstance(result["swept_liquidity_count"], int)

    def test_analyze_too_few_bars(self):
        df = pd.DataFrame({
            "open": [1.0], "high": [1.1], "low": [0.9], "close": [1.05], "volume": [100]
        })
        analyzer = SmartMoneyAnalyzer(lookback=50)
        assert analyzer.analyze(df) == {}

    def test_get_entry_zones(self, sample_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=20)
        analyzer.analyze(sample_bars_df)
        zones = analyzer.get_entry_zones(sample_bars_df)
        assert "bullish_zones" in zones
        assert "bearish_zones" in zones
        assert isinstance(zones["bullish_zones"], list)
        assert isinstance(zones["bearish_zones"], list)

    def test_entry_zones_have_enriched_fields(self, large_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=50)
        analyzer.analyze(large_bars_df)
        zones = analyzer.get_entry_zones(large_bars_df)
        for zone in zones["bullish_zones"] + zones["bearish_zones"]:
            assert "price" in zone
            assert "strength" in zone
            assert "volume" in zone
            assert "percentage" in zone

    def test_order_block_dataclass_fields(self, large_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=50)
        analyzer.analyze(large_bars_df)
        for ob in analyzer.order_blocks:
            assert hasattr(ob, "top")
            assert hasattr(ob, "bottom")
            assert hasattr(ob, "volume")
            assert hasattr(ob, "percentage")

    def test_fvg_dataclass_fields(self, large_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=50)
        analyzer.analyze(large_bars_df)
        for fvg in analyzer.fvgs:
            assert hasattr(fvg, "mitigated_index")

    def test_liquidity_zone_dataclass_fields(self, large_bars_df):
        analyzer = SmartMoneyAnalyzer(lookback=50)
        analyzer.analyze(large_bars_df)
        for zone in analyzer.liquidity_zones:
            assert hasattr(zone, "level")
            assert hasattr(zone, "end")
            assert hasattr(zone, "swept")


# ---------------------------------------------------------------------------
# SmartMoneyRiskManager tests
# ---------------------------------------------------------------------------


class TestSmartMoneyRiskManager:
    """Verify SmartMoneyRiskManager enhanced risk decisions."""

    def test_assess_trade_risk_returns_enhanced_fields(self, smc_risk_manager, sample_bars_df):
        result = smc_risk_manager.assess_trade_risk(sample_bars_df, "BUY", 1.05)
        assert "risk_score" in result
        assert "should_trade" in result
        assert "mitigation_status" in result
        assert "retracement_warning" in result
        assert "liquidity_swept" in result
        assert "ob_strength" in result

    def test_assess_trade_risk_score_range(self, smc_risk_manager, sample_bars_df):
        result = smc_risk_manager.assess_trade_risk(sample_bars_df, "BUY", 1.05)
        assert 0 <= result["risk_score"] <= 100

    def test_check_fvg_mitigation_returns_bool(self, smc_risk_manager, sample_bars_df):
        result = smc_risk_manager.check_fvg_mitigation(sample_bars_df, "BUY", 1.05)
        assert isinstance(result, bool)

    def test_check_liquidity_sweep_safety_returns_dict(self, smc_risk_manager, sample_bars_df):
        result = smc_risk_manager.check_liquidity_sweep_safety(sample_bars_df, "BUY", 1.05)
        assert "safe" in result
        assert "unswept_zones" in result
        assert "nearest_price" in result
        assert "recommendation" in result
        assert isinstance(result["safe"], bool)
        assert isinstance(result["unswept_zones"], list)

    def test_optimal_stop_loss_buy(self, smc_risk_manager, sample_bars_df):
        stop = smc_risk_manager.calculate_optimal_stop_loss(sample_bars_df, "BUY", 1.06)
        assert stop < 1.06  # Stop should be below entry for BUY

    def test_optimal_stop_loss_sell(self, smc_risk_manager, sample_bars_df):
        stop = smc_risk_manager.calculate_optimal_stop_loss(sample_bars_df, "SELL", 1.05)
        assert stop > 1.05  # Stop should be above entry for SELL

    def test_optimal_take_profit_buy(self, smc_risk_manager, sample_bars_df):
        tp = smc_risk_manager.calculate_optimal_take_profit(sample_bars_df, "BUY", 1.05)
        assert tp > 1.05  # TP should be above entry for BUY

    def test_optimal_take_profit_sell(self, smc_risk_manager, sample_bars_df):
        tp = smc_risk_manager.calculate_optimal_take_profit(sample_bars_df, "SELL", 1.06)
        assert tp < 1.06  # TP should be below entry for SELL

    def test_factory_creates_smart_money_manager(self):
        rm = create_risk_manager(smart_money=True)
        assert isinstance(rm, SmartMoneyRiskManager)

    def test_factory_with_smc_lookback(self):
        rm = create_risk_manager(smart_money=True, smc_lookback=100)
        assert isinstance(rm, SmartMoneyRiskManager)
        assert rm.smc_analyzer.lookback == 100

    def test_bias_alignment_affects_position_size(self, smc_risk_manager, large_bars_df):
        buy_result = smc_risk_manager.assess_trade_risk(large_bars_df, "BUY", 1.05)
        sell_result = smc_risk_manager.assess_trade_risk(large_bars_df, "SELL", 1.05)
        # At least one should have a different multiplier based on bias
        assert buy_result["position_size_multiplier"] != 1.0 or sell_result["position_size_multiplier"] != 1.0 or \
               buy_result["bias"] == "neutral"


# ---------------------------------------------------------------------------
# Strategy integration tests
# ---------------------------------------------------------------------------


class TestStrategyIntegration:
    """Verify strategies run without errors using the enriched SMC data."""

    def test_smart_money_strategy_runs(self, sample_bars):
        from jamlechtrader.strategy.examples.smart_money import SmartMoneyStrategy

        strategy = SmartMoneyStrategy(lookback=20)
        for bar in sample_bars:
            event = MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
            signals = strategy.on_bar(event)
            assert isinstance(signals, list)

    def test_advanced_smc_strategy_runs(self, sample_bars):
        from jamlechtrader.strategy.examples.advanced_smc import AdvancedSmartMoneyStrategy

        strategy = AdvancedSmartMoneyStrategy(swing_length=5)
        for bar in sample_bars:
            event = MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
            signals = strategy.on_bar(event)
            assert isinstance(signals, list)

    def test_smart_money_strategy_signal_has_strength(self, sample_bars):
        from jamlechtrader.strategy.examples.smart_money import SmartMoneyStrategy

        strategy = SmartMoneyStrategy(lookback=20, risk_threshold=100.0)
        all_signals = []
        for bar in sample_bars:
            event = MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
            all_signals.extend(strategy.on_bar(event))
        for signal in all_signals:
            assert signal.strength >= 0

    def test_advanced_smc_strategy_signal_has_strength(self, sample_bars):
        from jamlechtrader.strategy.examples.advanced_smc import AdvancedSmartMoneyStrategy

        strategy = AdvancedSmartMoneyStrategy(swing_length=5, ob_min_percentage=0)
        all_signals = []
        for bar in sample_bars:
            event = MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
            all_signals.extend(strategy.on_bar(event))
        for signal in all_signals:
            assert signal.strength >= 0


# ---------------------------------------------------------------------------
# Export / import tests
# ---------------------------------------------------------------------------


class TestExports:
    """Verify module exports are correct."""

    def test_portfolio_exports_smart_money_risk_manager(self):
        from jamlechtrader.portfolio import SmartMoneyRiskManager
        assert SmartMoneyRiskManager is not None

    def test_create_risk_manager_in_exports(self):
        from jamlechtrader.portfolio import create_risk_manager
        assert callable(create_risk_manager)
