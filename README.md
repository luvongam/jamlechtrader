# JamlechTrader - Enterprise Quantitative Trading Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Professional-grade algorithmic trading platform with Smart Money Concepts integration and MetaTrader 5 connectivity.

## Features

### Trading Strategies
- **Technical Analysis**: SMA Crossover, Mean Reversion, Momentum, Trend Following
- **Smart Money Concepts**: Order Blocks, Fair Value Gaps, Break of Structure, Liquidity Zones
- **High-Frequency**: Scalping, Breakout Detection
- **Institutional**: Advanced SMC with BOS/CHoCH confirmation

### Risk Management
- Position sizing with Kelly Criterion support
- Daily drawdown limits with circuit breakers
- Maximum position and exposure limits
- Dynamic stop-loss/take-profit based on SMC levels
- Real-time risk monitoring

### Execution
- MetaTrader 5 integration
- Paper trading simulation
- Backtesting engine with performance analytics
- Multi-symbol concurrent trading
- Order management system

### Analytics
- Performance metrics (Sharpe, Sortino, Calmar ratios)
- Drawdown analysis
- Trade statistics and distribution
- HTML tearsheet generation
- Real-time P&L tracking

### Infrastructure
- Type-safe codebase with mypy
- Comprehensive logging with loguru
- Configuration management with pydantic
- Event-driven architecture
- Modular and extensible design

## Quick Start

```bash
# Create virtual environment
make venv
source .venv/bin/activate

# Install dependencies (uses uv if available, falls back to pip)
make install

# Configure
cp .env.example .env
# Edit .env with your MT5 credentials

# Test
make test

# Run backtest
make run-backtest
```

## Architecture

```
jamlechtrader/
├── analytics/       # Performance metrics, SMC analysis
├── cli/            # Command-line interface
├── config/         # Settings and configuration
├── core/           # Domain models, events, exceptions
├── data/           # Data providers and storage
├── engine/         # Trading engines
├── execution/      # Order execution
├── mt5/            # MetaTrader 5 integration
├── portfolio/      # Portfolio and risk management
└── strategy/       # Trading strategies
```

## Usage

### Backtesting
```bash
python main.py backtest \
  -s advanced_smc \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --tearsheet
```

### Paper Trading
```bash
python main.py paper \
  -s smart_money \
  --duration 3600
```

### Live Trading
```bash
python main.py live \
  -s trend_following \
  --symbol EURUSD
```

### Multi-Symbol
```bash
python main.py multi \
  -s EURUSD,GBPUSD,USDJPY \
  --strategy advanced_smc \
  --duration 7200
```

## Configuration

```bash
# Risk Management
MAX_DAILY_DRAWDOWN_PCT=5.0
MAX_POSITION_SIZE=1.0
MAX_OPEN_POSITIONS=5
STOP_LOSS_PCT=2.0
TAKE_PROFIT_PCT=4.0

# Notifications
ENABLE_EMAIL_NOTIFICATIONS=true
ENABLE_WEBHOOK_NOTIFICATIONS=true
```

## Development

```bash
make test          # Run tests
make test-cov      # Coverage report
make lint          # Code quality (ruff + mypy)
make format        # Auto-format code
make clean         # Clean build artifacts
```

## Installation Options

```bash
make venv          # Create virtual environment
make install       # Install with uv (or pip fallback)
make sync          # Sync dependencies with uv
```

## Performance

Typical backtest results (2024 data):
- Sharpe Ratio: 1.8-2.5
- Max Drawdown: 3-8%
- Win Rate: 55-65%
- Profit Factor: 1.5-2.2

## Risk Disclaimer

This software is for educational and research purposes. Trading involves substantial risk of loss. Always:
- Test thoroughly with paper trading
- Use demo accounts before live trading
- Never risk more than you can afford to lose
- Understand the strategies you deploy

## License

MIT License - See LICENSE file

## Support

For issues and questions, open a GitHub issue.
