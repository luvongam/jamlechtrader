# JamlechTrader

Production-grade quantitative trading platform powered by MetaTrader 5.

## Features

- **8 built-in strategies** — SMA crossover, mean reversion, momentum, trend following, scalping, breakout, Smart Money Concepts, and advanced SMC
- **Multiple trading modes** — backtesting, paper trading, live trading, multi-symbol trading
- **Enterprise risk management** — Value-at-Risk, kill switch, per-symbol limits, margin monitoring
- **Order Management System** — state machine, bracket orders, partial fills
- **Database persistence** — PostgreSQL with crash recovery and audit logging
- **Monitoring dashboard** — REST API, WebSocket live feed, Prometheus metrics
- **Resilience** — circuit breaker, auto-reconnect, graceful shutdown
- **Credential encryption** — secure storage via OS keyring

## Installation

### Prerequisites

- Python >= 3.10
- MetaTrader 5 terminal (Windows only for live/paper trading)
- PostgreSQL (for database persistence features)

### Install from source

Using [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv sync
```

Or with pip:

```bash
pip install -e .
```

### Optional extras

```bash
# MetaTrader 5 connector (Windows only)
uv sync --extra mt5

# HTML tearsheet reports (quantstats)
uv sync --extra reports

# Both
uv sync --extra mt5 --extra reports
```

### Database setup

JamlechTrader uses PostgreSQL for trade persistence, audit logging, and crash recovery.

1. Create the database:

```bash
createdb jamlechtrader
```

2. Set the connection string in `.env`:

```
DATABASE_URL=postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5436/jamlechtrader
```

3. Run migrations:

```bash
uv run alembic upgrade head
```

## Configuration

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

### Environment variables

#### MT5 Connection

| Variable | Description | Default |
|---|---|---|
| `MT5_PATH` | Path to MetaTrader 5 terminal executable | `""` |
| `MT5_LOGIN` | MT5 account login number | `0` |
| `MT5_PASSWORD` | MT5 account password | `""` |
| `MT5_SERVER` | MT5 broker server name | `""` |

#### Trading Defaults

| Variable | Description | Default |
|---|---|---|
| `DEFAULT_SYMBOL` | Default trading symbol | `EURUSD` |
| `DEFAULT_TIMEFRAME` | Default timeframe (`M1`, `M5`, `M15`, `H1`, `H4`, `D1`, etc.) | `H1` |
| `DEFAULT_LOT_SIZE` | Default position lot size | `0.01` |

#### Data Storage

| Variable | Description | Default |
|---|---|---|
| `DATA_DIR` | Directory for cached market data (Parquet files) | `./data_cache` |

#### Risk Management

| Variable | Description | Default |
|---|---|---|
| `MAX_DAILY_DRAWDOWN_PCT` | Maximum daily drawdown percentage before halting | `5.0` |
| `MAX_POSITION_SIZE` | Maximum lot size for a single position | `1.0` |
| `MAX_OPEN_POSITIONS` | Maximum number of concurrent open positions | `5` |

#### Notifications

| Variable | Description | Default |
|---|---|---|
| `ENABLE_EMAIL_NOTIFICATIONS` | Enable email trade alerts | `false` |
| `SMTP_HOST` | SMTP server host | `smtp.gmail.com` |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USERNAME` | SMTP username | |
| `SMTP_PASSWORD` | SMTP app password | |
| `EMAIL_FROM` | Sender email address | |
| `EMAIL_TO` | Recipient email address | |
| `ENABLE_WEBHOOK_NOTIFICATIONS` | Enable webhook notifications (Slack, Discord) | `false` |
| `WEBHOOK_URL` | Webhook endpoint URL | |

#### Enterprise Risk

| Variable | Description | Default |
|---|---|---|
| `ENTERPRISE_RISK` | Enable enterprise risk management | `false` |
| `MAX_TOTAL_NOTIONAL` | Maximum total notional exposure | `1000000.0` |
| `MAX_LEVERAGE_RATIO` | Maximum leverage ratio | `10.0` |
| `MAX_MARGIN_UTILIZATION_PCT` | Maximum margin utilization percentage | `80.0` |
| `VAR_CONFIDENCE_LEVEL` | Value-at-Risk confidence level | `0.95` |
| `MAX_VAR_PCT` | Maximum VaR as percentage of portfolio | `5.0` |
| `KILL_SWITCH_DRAWDOWN_PCT` | Kill switch drawdown trigger | `10.0` |
| `KILL_SWITCH_MAX_LOSS` | Kill switch absolute loss trigger | `50000.0` |
| `KILL_SWITCH_CONSECUTIVE_LOSSES` | Kill switch consecutive losses trigger | `10` |
| `PER_SYMBOL_MAX_POSITION` | Per-symbol position limits (JSON) | `null` |
| `PER_SYMBOL_MAX_NOTIONAL` | Per-symbol notional limits (JSON) | `null` |

#### Database

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5432/jamlechtrader` |

#### Security

| Variable | Description | Default |
|---|---|---|
| `USE_SECURE_CREDENTIALS` | Use OS keyring for credential storage | `false` |

#### Monitoring

| Variable | Description | Default |
|---|---|---|
| `PROMETHEUS_PORT` | Prometheus metrics exporter port | `9090` |
| `DASHBOARD_PORT` | Monitoring dashboard port | `8080` |

## CLI Reference

All commands are accessed through the `jamlechtrader` entry point. Use `--verbose` / `-v` on any command for debug logging.

```bash
jamlechtrader --help
```

### `backtest` — Run historical backtests

```bash
jamlechtrader backtest \
  --strategy sma_crossover \
  --symbol EURUSD \
  --timeframe H1 \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --cash 10000 \
  --tearsheet
```

| Option | Required | Description |
|---|---|---|
| `--strategy`, `-s` | Yes | Strategy name or `module.path:ClassName` |
| `--symbol` | No | Trading symbol (default from settings) |
| `--timeframe`, `-tf` | No | Timeframe (default from settings) |
| `--start` | Yes | Start date `YYYY-MM-DD` |
| `--end` | Yes | End date `YYYY-MM-DD` |
| `--cash` | No | Initial cash (default `10000`) |
| `--lot-size` | No | Fixed lot size (default from settings) |
| `--tearsheet` | No | Generate HTML tearsheet report |

### `paper` — Paper trading with live data

```bash
jamlechtrader paper \
  --strategy mean_reversion \
  --symbol GBPUSD \
  --timeframe M5 \
  --duration 3600
```

| Option | Required | Description |
|---|---|---|
| `--strategy`, `-s` | Yes | Strategy name |
| `--symbol` | No | Trading symbol |
| `--timeframe`, `-tf` | No | Timeframe |
| `--duration` | No | Duration in seconds (default `600`) |

### `live` — Live trading

**Warning: This uses real money on live accounts. Use a demo account for testing.**

```bash
jamlechtrader live \
  --strategy sma_crossover \
  --symbol EURUSD \
  --timeframe H1
```

| Option | Required | Description |
|---|---|---|
| `--strategy`, `-s` | Yes | Strategy name |
| `--symbol` | No | Trading symbol |
| `--timeframe`, `-tf` | No | Timeframe |

### `async-live` — Async live trading engine

The async engine provides non-blocking execution with improved throughput for high-frequency strategies.

```bash
jamlechtrader async-live \
  --strategy scalping \
  --symbol EURUSD \
  --timeframe M1
```

| Option | Required | Description |
|---|---|---|
| `--strategy`, `-s` | Yes | Strategy name |
| `--symbol` | No | Trading symbol |
| `--timeframe`, `-tf` | No | Timeframe |

### `account` — Show MT5 account info

```bash
jamlechtrader account
```

Displays login, server, name, company, balance, equity, margin, free margin, and leverage.

### `download` — Download historical data

Downloads OHLCV data from MT5 and caches it as Parquet files for fast backtest loading.

```bash
jamlechtrader download \
  --symbol EURUSD \
  --timeframe H1 \
  --start 2023-01-01 \
  --end 2024-12-31
```

| Option | Required | Description |
|---|---|---|
| `--symbol` | Yes | Symbol to download |
| `--timeframe`, `-tf` | No | Timeframe (default `H1`) |
| `--start` | Yes | Start date `YYYY-MM-DD` |
| `--end` | No | End date `YYYY-MM-DD` (default: today) |

### `multi` — Multi-symbol trading

Trade multiple symbols simultaneously with a single strategy.

```bash
jamlechtrader multi \
  --symbols EURUSD,GBPUSD,USDJPY \
  --strategy momentum \
  --timeframe M5 \
  --duration 3600
```

| Option | Required | Description |
|---|---|---|
| `--symbols`, `-s` | Yes | Comma-separated symbols |
| `--strategy` | Yes | Strategy name |
| `--timeframe`, `-tf` | No | Timeframe (default `M5`) |
| `--duration` | No | Duration in seconds (default `3600`) |

### `schedule` — Scheduled trading sessions

Runs paper trading sessions on a daily schedule. Currently hard-coded to run the `sma_crossover` strategy on the default symbol and timeframe at 09:00 and 14:00 daily (1-hour sessions each).

```bash
jamlechtrader schedule
```

### `dashboard` — Monitoring dashboard

Launches a web-based monitoring dashboard.

```bash
jamlechtrader dashboard --host 0.0.0.0 --port 8080
```

| Option | Required | Description |
|---|---|---|
| `--host` | No | Bind address (default `0.0.0.0`) |
| `--port` | No | Port number (default `8080`) |

## Strategies

All built-in strategies can be referenced by name with the `--strategy` flag.

| Name | Description | Key Parameters |
|---|---|---|
| `sma_crossover` | SMA crossover — buy when fast SMA crosses above slow SMA | `fast_period=10`, `slow_period=30` |
| `mean_reversion` | Bollinger Band mean reversion — buy at lower band, sell at upper band | `period=20`, `std_dev=2.0` |
| `momentum` | RSI + ADX momentum — trade oversold/overbought in strong trends | `rsi_period=14`, `adx_period=14`, `rsi_oversold=30`, `rsi_overbought=70`, `adx_threshold=25` |
| `trend_following` | EMA trend with momentum confirmation | `ema_period=50`, `momentum_period=10` |
| `scalping` | Fast EMA crossover with RSI filter for quick trades | `fast=5`, `slow=13`, `rsi_period=14` |
| `breakout` | Trade breakouts above/below recent highs and lows | `lookback=20`, `threshold=0.001` |
| `smart_money` | Institutional Smart Money Concepts (order blocks, bias detection) | `lookback=50`, `risk_threshold=60` |
| `advanced_smc` | Professional SMC with BOS, CHoCH, order blocks, and fair value gaps | `swing_length=10`, `risk_threshold=60`, `min_risk_reward=2.0` |

### Custom strategies

You can load any custom strategy using the `module.path:ClassName` syntax:

```bash
jamlechtrader backtest \
  --strategy my_package.strategies.custom:MyStrategy \
  --start 2024-01-01 --end 2024-12-31
```

Your strategy must extend `jamlechtrader.strategy.base.AbstractStrategy` and implement the `on_bar` method.

## Trading Modes

### Backtesting

The recommended workflow for backtesting:

1. **Download data** — cache historical data locally for fast iteration:

```bash
jamlechtrader download --symbol EURUSD --timeframe H1 --start 2023-01-01
```

2. **Run backtest** — test your strategy on historical data:

```bash
jamlechtrader backtest -s sma_crossover --start 2023-01-01 --end 2024-12-31 --cash 10000
```

3. **Generate tearsheet** — add `--tearsheet` for an HTML performance report (requires the `reports` extra):

```bash
jamlechtrader backtest -s sma_crossover --start 2023-01-01 --end 2024-12-31 --tearsheet
```

The backtest engine will use cached Parquet data if available, otherwise it connects to MT5 directly.

### Paper trading

Paper trading uses live MT5 market data but simulates order execution. No real orders are placed.

```bash
jamlechtrader paper -s mean_reversion --symbol EURUSD --duration 3600
```

### Live trading

Live trading places real orders through MT5. Always test your strategy thoroughly with backtesting and paper trading first.

**Prerequisites:**
- MetaTrader 5 terminal running and logged in
- MT5 credentials configured in `.env`
- Strategy validated via backtest and paper trading

```bash
jamlechtrader live -s sma_crossover --symbol EURUSD --timeframe H1
```

The command prompts for confirmation before starting. Press `Ctrl+C` to stop.

### Multi-symbol trading

Trade multiple symbols with a single strategy instance:

```bash
jamlechtrader multi --symbols EURUSD,GBPUSD,USDJPY --strategy momentum --duration 7200
```

## Enterprise Features

### Database persistence and crash recovery

All trades, orders, and portfolio state are persisted to PostgreSQL. If the bot crashes or restarts, it recovers its state from the database automatically.

### Order Management System

The OMS provides a full order lifecycle with a state machine (pending, submitted, partially filled, filled, cancelled, rejected), bracket orders (entry + stop loss + take profit), and partial fill handling.

### Enterprise risk management

When `ENTERPRISE_RISK=true`, the following checks are enforced before every order:

- **Value-at-Risk (VaR)** — portfolio VaR calculated at the configured confidence level
- **Kill switch** — automatically halts trading when drawdown, absolute loss, or consecutive loss thresholds are breached
- **Per-symbol limits** — configurable maximum position size and notional per symbol
- **Margin monitoring** — rejects orders that would exceed margin utilization limits
- **Leverage limits** — enforces maximum leverage ratio

### Resilience

- **Circuit breaker** — automatically backs off after repeated failures
- **Auto-reconnect** — reconnects to MT5 after connection drops
- **Graceful shutdown** — cleanly closes positions and persists state on `SIGINT`/`SIGTERM`

### Audit logging

All order submissions, fills, cancellations, and risk rejections are logged to the database with timestamps and full context for compliance and debugging.

### Credential encryption

Set `USE_SECURE_CREDENTIALS=true` to store MT5 credentials in the OS keyring instead of plain text in `.env`.

## Monitoring Dashboard

Launch the dashboard:

```bash
jamlechtrader dashboard --port 8080
```

Then open `http://localhost:8080` in your browser.

### REST API endpoints

| Endpoint | Description |
|---|---|
| `GET /` | HTML dashboard page |
| `GET /health` | Health check (status, uptime) |
| `GET /metrics` | Prometheus metrics (text format) |
| `GET /api/portfolio` | Current portfolio state |
| `GET /api/orders` | Active orders |
| `GET /api/positions` | Open positions |

### WebSocket live feed

Connect to `ws://localhost:8080/ws/live` for real-time updates. The server sends JSON messages every 5 seconds containing portfolio state and health status.

### Prometheus integration

Scrape `http://localhost:9090/metrics` (or the configured `PROMETHEUS_PORT`) with your Prometheus instance to collect trading metrics.

## Development

A `Makefile` provides shortcuts for common tasks. Run `make help` to see all targets.

### First-time setup

```bash
make install      # Install all dependencies
make db-up        # Start PostgreSQL (Docker, port 5436)
make db-migrate   # Run Alembic migrations
```

### Running checks

```bash
make lint         # ruff check .
make typecheck    # mypy jamlechtrader/
make test         # pytest tests/ -v
make check        # All three at once
```

### Local Docker testing

Run the full CI pipeline in Docker (PostgreSQL + migrations + ruff + mypy + pytest):

```bash
make docker-test
```

Run only DB migration validation:

```bash
make docker-migration
```

### Monitoring stack

Start the dashboard, Prometheus, and Grafana locally:

```bash
make docker-monitoring
```

| Service | URL | Credentials |
|---|---|---|
| Dashboard | http://localhost:8050 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin / admin |

Stop everything:

```bash
make docker-down
```

## CI/CD Pipeline

GitHub Actions workflows handle automated quality checks, database migration validation, container publishing, and deployment.

| Workflow | Trigger | File |
|---|---|---|
| CI | Push to main, PRs | `.github/workflows/ci.yml` |
| CD | Push `v*` tag, manual dispatch | `.github/workflows/cd.yml` |
| Dependabot | Weekly (Mondays) | `.github/dependabot.yml` |

See the full pipeline runbook: [`devops/PIPELINE.md`](devops/PIPELINE.md)

## License

Proprietary. All rights reserved.
