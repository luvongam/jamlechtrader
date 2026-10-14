"""CLI entry point for JamlechTrader."""

from __future__ import annotations

from datetime import UTC, datetime

import click
from loguru import logger

from jamlechtrader.config.logging_config import setup_logging
from jamlechtrader.config.settings import get_settings
from jamlechtrader.core.enums import Timeframe

STRATEGY_MAP = {
    "sma_crossover": "jamlechtrader.strategy.examples.sma_crossover:SMACrossoverStrategy",
    "mean_reversion": "jamlechtrader.strategy.examples.mean_reversion:MeanReversionStrategy",
    "momentum": "jamlechtrader.strategy.examples.momentum:MomentumStrategy",
    "trend_following": "jamlechtrader.strategy.examples.trend_following:TrendFollowingStrategy",
    "scalping": "jamlechtrader.strategy.examples.scalping:ScalpingStrategy",
    "breakout": "jamlechtrader.strategy.examples.breakout:BreakoutStrategy",
    "smart_money": "jamlechtrader.strategy.examples.smart_money:SmartMoneyStrategy",
    "advanced_smc": "jamlechtrader.strategy.examples.advanced_smc:AdvancedSmartMoneyStrategy",
    "supply_demand": "jamlechtrader.strategy.examples.supply_demand:SupplyDemandStrategy",
}

DATA_SOURCE_CHOICES = ["yahoo", "csv"]


def _load_strategy(name: str):
    """Dynamically load a strategy class by name."""
    if name in STRATEGY_MAP:
        module_path, class_name = STRATEGY_MAP[name].rsplit(":", 1)
    elif ":" in name:
        module_path, class_name = name.rsplit(":", 1)
    else:
        raise click.BadParameter(
            f"Unknown strategy: {name}. Available: {', '.join(STRATEGY_MAP)}"
        )

    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
def cli(verbose: bool) -> None:
    """JamlechTrader — Quantitative Trading Platform."""
    setup_logging("DEBUG" if verbose else "INFO")


@cli.command()
@click.option("--strategy", "-s", required=True, help="Strategy name or module:Class")
@click.option("--symbol", default=None, help="Trading symbol (e.g. EURUSD, AAPL, BTCUSD)")
@click.option("--timeframe", "-tf", default=None, help="Timeframe (e.g. H1, M5, D1)")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
@click.option("--cash", default=10000.0, help="Initial cash")
@click.option("--lot-size", default=None, type=float, help="Fixed lot size")
@click.option("--tearsheet", is_flag=True, help="Generate HTML tearsheet")
@click.option(
    "--risk-mode",
    type=click.Choice(["basic", "enterprise", "smart_money"]),
    default="basic",
    help="Risk manager mode",
)
@click.option(
    "--data-source",
    type=click.Choice(DATA_SOURCE_CHOICES),
    default=None,
    help="Data source: yahoo (default) or csv",
)
def backtest(
    strategy: str,
    symbol: str | None,
    timeframe: str | None,
    start: str,
    end: str,
    cash: float,
    lot_size: float | None,
    tearsheet: bool,
    risk_mode: str,
    data_source: str | None,
) -> None:
    """Run a backtest on historical data (Yahoo Finance by default)."""
    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)
    lot = lot_size or settings.default_lot_size
    source = data_source or settings.default_data_source

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    strat = _load_strategy(strategy)

    from jamlechtrader.analytics.metrics import calculate_metrics, format_metrics
    from jamlechtrader.data.store import DataStore
    from jamlechtrader.engine.backtest import BacktestEngine
    from jamlechtrader.portfolio.portfolio import Portfolio
    from jamlechtrader.portfolio.risk import create_risk_manager
    from jamlechtrader.portfolio.sizing import PositionSizer

    risk_mgr = create_risk_manager(
        enterprise=(risk_mode == "enterprise"),
        smart_money=(risk_mode == "smart_money"),
    )

    # Resolve data handler based on source
    store = DataStore(settings.data_dir)
    if store.has_cache(sym, tf):
        from jamlechtrader.data.csv_provider import CSVDataProvider

        path = store._file_path(sym, tf)
        data_handler = CSVDataProvider(path, symbol=sym)
        click.echo(f"Using cached data from {path}")
    elif source == "yahoo":
        from jamlechtrader.data.yahoo_provider import YahooFinanceProvider

        data_handler = YahooFinanceProvider(sym, tf, start_dt, end_dt)
        click.echo(f"Fetching data from Yahoo Finance for {sym}...")
    else:
        click.echo(f"No cached data for {sym} {tf.value}. Use --data-source yahoo.")
        return

    portfolio = Portfolio(initial_cash=cash)
    sizer = PositionSizer(method="fixed", fixed_lot=lot)

    engine = BacktestEngine(
        data_handler=data_handler,
        strategy=strat,
        portfolio=portfolio,
        risk_manager=risk_mgr,
        sizer=sizer,
    )

    results = engine.run()

    metrics = calculate_metrics(
        results["equity_curve"], results["closed_trades"]
    )
    click.echo(format_metrics(metrics))

    if tearsheet:
        from jamlechtrader.analytics.tearsheet import generate_tearsheet

        generate_tearsheet(results["equity_curve"])
        click.echo("Tearsheet generated: tearsheet.html")


@cli.command()
@click.option("--symbol", required=True, help="Symbol to download")
@click.option("--timeframe", "-tf", default="H1", help="Timeframe")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", default=None, help="End date YYYY-MM-DD (default: today)")
def download(symbol: str, timeframe: str, start: str, end: str | None) -> None:
    """Download historical data from Yahoo Finance and cache as Parquet."""
    settings = get_settings()
    tf = Timeframe(timeframe)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now(tz=UTC)

    from jamlechtrader.data.store import DataStore

    store = DataStore(settings.data_dir)
    df = store.download(symbol, tf, start_dt, end_dt)
    click.echo(f"Downloaded {len(df)} bars for {symbol} {tf.value} from Yahoo Finance")


@cli.command(name="yahoo-live")
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--symbol", default=None, help="Trading symbol (e.g. EURUSD, AAPL, BTCUSD)")
@click.option("--timeframe", "-tf", default=None, help="Timeframe")
@click.option("--duration", default=3600, help="Duration in seconds (default 1hr)")
@click.option("--cash", default=10000.0, help="Initial cash")
@click.option(
    "--risk-mode",
    type=click.Choice(["basic", "enterprise", "smart_money"]),
    default="basic",
    help="Risk manager mode",
)
def yahoo_live(
    strategy: str,
    symbol: str | None,
    timeframe: str | None,
    duration: int,
    cash: float,
    risk_mode: str,
) -> None:
    """Run paper trading with Yahoo Finance live data."""
    import time as time_mod

    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)

    strat = _load_strategy(strategy)

    from jamlechtrader.core.events import EventBus, MarketEvent
    from jamlechtrader.data.yahoo_provider import YahooLiveFeed
    from jamlechtrader.execution.simulated import SimulatedExecutor
    from jamlechtrader.portfolio.portfolio import Portfolio
    from jamlechtrader.portfolio.risk import create_risk_manager
    from jamlechtrader.portfolio.sizing import PositionSizer

    risk_mgr = create_risk_manager(
        enterprise=(risk_mode == "enterprise"),
        smart_money=(risk_mode == "smart_money"),
    )
    portfolio = Portfolio(initial_cash=cash)
    sizer = PositionSizer(method="fixed", fixed_lot=settings.default_lot_size)
    executor = SimulatedExecutor()

    feed = YahooLiveFeed(symbol=sym, timeframe=tf, poll_interval=10.0)

    click.echo(f"Yahoo Finance paper trading: {sym} {tf.value} for {duration}s")
    click.echo("Press Ctrl+C to stop early")

    strat.on_start()
    start_time = time_mod.time()
    signal_count = 0
    fill_count = 0

    try:
        while time_mod.time() - start_time < duration:
            bar = feed.get_latest_bar()
            if bar is None:
                time_mod.sleep(10)
                continue

            portfolio.update_market_price(bar.symbol, bar.close)
            executor.set_current_bar(bar)

            event = MarketEvent(symbol=bar.symbol, timestamp=bar.timestamp, data=bar)
            signals = strat.on_bar(event)

            for signal in signals:
                signal_count += 1
                quantity = sizer.calculate(equity=portfolio.equity, bar=bar)
                order = portfolio.generate_order(signal, quantity)
                if order is None:
                    continue
                snapshot = portfolio.take_snapshot(bar.timestamp)
                checked = risk_mgr.check_order(order, snapshot)
                if checked is None:
                    continue
                fill = executor.execute_order(checked)
                if fill is not None:
                    fill_count += 1
                    portfolio.on_fill(fill)
                    click.echo(
                        f"  [{fill.side.value}] {fill.symbol} @ {fill.price:.5f} "
                        f"qty={fill.quantity} | equity={portfolio.equity:.2f}"
                    )

            portfolio.take_snapshot(bar.timestamp)
            time_mod.sleep(10)

    except KeyboardInterrupt:
        click.echo("\nStopped by user")

    strat.on_stop()
    click.echo(f"\nResults: {signal_count} signals, {fill_count} fills")
    click.echo(f"Final equity: {portfolio.equity:.2f}")


@cli.command()
@click.option("--symbols", "-s", required=True, help="Comma-separated symbols (e.g. AAPL,EURUSD,BTCUSD)")
@click.option("--duration", default=0, help="Duration in seconds (0 = indefinite)")
def stream(symbols: str, duration: int) -> None:
    """Stream real-time ticks via Yahoo Finance WebSocket."""
    import time as time_mod

    from jamlechtrader.data.yahoo_provider import YahooWebSocketFeed

    symbol_list = [s.strip() for s in symbols.split(",")]
    tick_count = 0

    def on_tick(tick):
        nonlocal tick_count
        tick_count += 1
        click.echo(
            f"  {tick.symbol:>10} | bid={tick.bid:.5f}  ask={tick.ask:.5f}  "
            f"last={tick.last:.5f}  vol={tick.volume:.0f}"
        )

    feed = YahooWebSocketFeed(symbol_list, on_tick=on_tick)

    click.echo(f"Streaming real-time ticks for: {symbol_list}")
    click.echo("Press Ctrl+C to stop\n")

    feed.start_background()

    try:
        start_time = time_mod.time()
        while feed.is_running:
            if duration > 0 and (time_mod.time() - start_time) > duration:
                break
            time_mod.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nStopped by user")
    finally:
        feed.stop()
        click.echo(f"Total ticks received: {tick_count}")


@cli.command(name="snapshot")
@click.option("--symbol", "-s", default=None, help="Trading symbol")
def snapshot(symbol: str | None) -> None:
    """Get a quick price snapshot via Yahoo Finance fast_info."""
    settings = get_settings()
    sym = symbol or settings.default_symbol

    from jamlechtrader.data.yahoo_provider import YahooLiveFeed

    feed = YahooLiveFeed(sym)
    tick = feed.get_snapshot_tick()
    if tick is None:
        click.echo(f"Failed to get snapshot for {sym}")
        return

    click.echo(f"Symbol:    {tick.symbol}")
    click.echo(f"Bid:       {tick.bid:.6f}")
    click.echo(f"Ask:       {tick.ask:.6f}")
    click.echo(f"Last:      {tick.last:.6f}")
    click.echo(f"Volume:    {tick.volume:.0f}")
    click.echo(f"Timestamp: {tick.timestamp.isoformat()}")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Dashboard host")
@click.option("--port", default=8080, type=int, help="Dashboard port")
def dashboard(host: str, port: int) -> None:
    """Launch the monitoring dashboard."""
    import uvicorn

    from jamlechtrader.monitoring.dashboard import app

    click.echo(f"Starting dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    cli()
