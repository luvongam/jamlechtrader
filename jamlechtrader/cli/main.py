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
}


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
@click.option("--symbol", default=None, help="Trading symbol (e.g. EURUSD)")
@click.option("--timeframe", "-tf", default=None, help="Timeframe (e.g. H1, M5)")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", required=True, help="End date YYYY-MM-DD")
@click.option("--cash", default=10000.0, help="Initial cash")
@click.option("--lot-size", default=None, type=float, help="Fixed lot size")
@click.option("--tearsheet", is_flag=True, help="Generate HTML tearsheet")
def backtest(
    strategy: str,
    symbol: str | None,
    timeframe: str | None,
    start: str,
    end: str,
    cash: float,
    lot_size: float | None,
    tearsheet: bool,
) -> None:
    """Run a backtest on historical MT5 data."""
    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)
    lot = lot_size or settings.default_lot_size

    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")

    strat = _load_strategy(strategy)

    from jamlechtrader.analytics.metrics import calculate_metrics, format_metrics
    from jamlechtrader.data.store import DataStore
    from jamlechtrader.engine.backtest import BacktestEngine
    from jamlechtrader.portfolio.portfolio import Portfolio
    from jamlechtrader.portfolio.sizing import PositionSizer

    # Try cached data first, otherwise use MT5 provider
    store = DataStore(settings.data_dir)
    if store.has_cache(sym, tf):
        from jamlechtrader.data.csv_provider import CSVDataProvider

        path = store._file_path(sym, tf)
        data_handler = CSVDataProvider(path, symbol=sym)
    else:
        from jamlechtrader.mt5.connection import MT5Connection
        from jamlechtrader.data.mt5_provider import MT5DataProvider

        conn = MT5Connection(settings)
        if not conn.connect():
            click.echo("Failed to connect to MT5. Run 'jamlechtrader download' first.")
            return
        data_handler = MT5DataProvider(sym, tf, start_dt, end_dt)

    portfolio = Portfolio(initial_cash=cash)
    sizer = PositionSizer(method="fixed", fixed_lot=lot)

    engine = BacktestEngine(
        data_handler=data_handler,
        strategy=strat,
        portfolio=portfolio,
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
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--symbol", default=None, help="Trading symbol")
@click.option("--timeframe", "-tf", default=None, help="Timeframe")
@click.option("--duration", default=600, help="Duration in seconds (default 10min)")
def paper(strategy: str, symbol: str | None, timeframe: str | None, duration: int) -> None:
    """Run paper trading with live MT5 data."""
    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)

    strat = _load_strategy(strategy)

    from jamlechtrader.engine.paper import PaperEngine
    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    engine = PaperEngine(
        connection=conn, strategy=strat, symbol=sym, timeframe=tf
    )

    click.echo(f"Paper trading {sym} {tf.value} for {duration}s ...")
    try:
        results = engine.run(duration_seconds=duration)
        click.echo(f"Trades: {results['trades']}, Final equity: {results['final_equity']:.2f}")
    finally:
        conn.disconnect()


@cli.command()
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--symbol", default=None, help="Trading symbol")
@click.option("--timeframe", "-tf", default=None, help="Timeframe")
def live(strategy: str, symbol: str | None, timeframe: str | None) -> None:
    """Run live trading (CAUTION: uses real money on live accounts)."""
    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)

    click.echo("WARNING: Live trading uses REAL orders. Use a demo account.")
    if not click.confirm("Continue?"):
        return

    strat = _load_strategy(strategy)

    from jamlechtrader.engine.live import LiveEngine
    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    engine = LiveEngine(
        connection=conn, strategy=strat, symbol=sym, timeframe=tf
    )

    try:
        engine.run()
    except KeyboardInterrupt:
        click.echo("Stopped by user")
    finally:
        conn.disconnect()


@cli.command()
def account() -> None:
    """Show MT5 account information."""
    settings = get_settings()

    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    info = conn.account_info()
    if info:
        click.echo(f"Login:       {info.login}")
        click.echo(f"Server:      {info.server}")
        click.echo(f"Name:        {info.name}")
        click.echo(f"Company:     {info.company}")
        click.echo(f"Balance:     {info.balance:.2f} {info.currency}")
        click.echo(f"Equity:      {info.equity:.2f} {info.currency}")
        click.echo(f"Margin:      {info.margin:.2f} {info.currency}")
        click.echo(f"Free margin: {info.free_margin:.2f} {info.currency}")
        click.echo(f"Leverage:    1:{info.leverage}")
    else:
        click.echo("Failed to retrieve account info")

    conn.disconnect()


@cli.command()
@click.option("--symbol", required=True, help="Symbol to download")
@click.option("--timeframe", "-tf", default="H1", help="Timeframe")
@click.option("--start", required=True, help="Start date YYYY-MM-DD")
@click.option("--end", default=None, help="End date YYYY-MM-DD (default: today)")
def download(symbol: str, timeframe: str, start: str, end: str | None) -> None:
    """Download historical data from MT5 and cache as Parquet."""
    settings = get_settings()
    tf = Timeframe(timeframe)
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d") if end else datetime.now(tz=UTC)

    from jamlechtrader.data.store import DataStore
    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    store = DataStore(settings.data_dir)
    df = store.download(symbol, tf, start_dt, end_dt)
    click.echo(f"Downloaded {len(df)} bars for {symbol} {tf.value}")

    conn.disconnect()


@cli.command()
@click.option("--symbols", "-s", required=True, help="Comma-separated symbols (e.g. EURUSD,GBPUSD)")
@click.option("--strategy", required=True, help="Strategy name")
@click.option("--timeframe", "-tf", default="M5", help="Timeframe")
@click.option("--duration", default=3600, help="Duration in seconds")
def multi(symbols: str, strategy: str, timeframe: str, duration: int) -> None:
    """Trade multiple symbols simultaneously."""
    settings = get_settings()
    symbol_list = [s.strip() for s in symbols.split(",")]
    tf = Timeframe(timeframe)
    strat = _load_strategy(strategy)

    from jamlechtrader.engine.multi_symbol import MultiSymbolEngine
    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    engine = MultiSymbolEngine(
        connection=conn,
        symbols=symbol_list,
        strategies={"main": strat},
        timeframe=tf,
    )

    click.echo(f"Multi-symbol trading: {symbol_list}")
    try:
        results = engine.run(duration_seconds=duration)
        click.echo(f"Completed: {results['trades']} trades, Final equity: {results['final_equity']:.2f}")
    finally:
        conn.disconnect()


@cli.command(name="async-live")
@click.option("--strategy", "-s", required=True, help="Strategy name")
@click.option("--symbol", default=None, help="Trading symbol")
@click.option("--timeframe", "-tf", default=None, help="Timeframe")
def async_live(strategy: str, symbol: str | None, timeframe: str | None) -> None:
    """Run async live trading engine (CAUTION: uses real money)."""
    import asyncio

    settings = get_settings()
    sym = symbol or settings.default_symbol
    tf = Timeframe(timeframe or settings.default_timeframe)

    click.echo("WARNING: Async live trading uses REAL orders. Use a demo account.")
    if not click.confirm("Continue?"):
        return

    strat = _load_strategy(strategy)

    from jamlechtrader.engine.async_live import AsyncLiveEngine
    from jamlechtrader.mt5.connection import MT5Connection

    conn = MT5Connection(settings)
    if not conn.connect():
        click.echo("Failed to connect to MT5")
        return

    engine = AsyncLiveEngine(
        connection=conn, strategy=strat, symbol=sym, timeframe=tf
    )

    try:
        asyncio.run(engine.run())
    except KeyboardInterrupt:
        click.echo("Stopped by user")
    finally:
        conn.disconnect()


@cli.command()
def schedule() -> None:
    """Run trading bot on a schedule."""
    from datetime import time as dt_time
    from jamlechtrader.scheduler import TradingScheduler
    from jamlechtrader.mt5.connection import MT5Connection
    from jamlechtrader.engine.paper import PaperEngine

    settings = get_settings()

    def run_trading_session():
        conn = MT5Connection(settings)
        if not conn.connect():
            logger.error("Failed to connect to MT5")
            return
        
        strat = _load_strategy("sma_crossover")
        engine = PaperEngine(
            connection=conn,
            strategy=strat,
            symbol=settings.default_symbol,
            timeframe=Timeframe(settings.default_timeframe),
        )
        
        try:
            results = engine.run(duration_seconds=3600)
            logger.info(f"Session complete: {results['trades']} trades")
        finally:
            conn.disconnect()

    scheduler = TradingScheduler()
    scheduler.add_daily_job(dt_time(9, 0), run_trading_session)
    scheduler.add_daily_job(dt_time(14, 0), run_trading_session)
    
    click.echo("Scheduler started. Trading at 09:00 and 14:00 daily.")
    scheduler.run()


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
