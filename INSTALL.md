# Installation Guide

## Prerequisites

- Python 3.10+ (3.14 supported)
- MetaTrader 5 (for live/paper trading)
- Git

## Quick Install

```bash
# Clone repository
git clone <your-repo-url>
cd jamlechtrader

# Create virtual environment
make venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Install dependencies
make install
```

## Package Manager

The project uses **uv** (ultra-fast Python package manager) with automatic fallback to pip:

### Option 1: With uv (Recommended - 10-100x faster)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project
make install
```

### Option 2: Without uv (Standard pip)

```bash
# Works automatically if uv not installed
make install
```

The Makefile automatically detects and uses uv if available, otherwise falls back to pip.

## Verify Installation

```bash
# Check installation
python -c "import jamlechtrader; print('✅ Installation successful')"

# Run tests
make test

# Check MT5 connection
make account
```

## Configuration

```bash
# Copy example config
cp .env.example .env

# Edit with your credentials
nano .env  # or your preferred editor
```

Required settings:
```bash
MT5_LOGIN=your_account
MT5_PASSWORD=your_password
MT5_SERVER=your_broker
DEFAULT_SYMBOL=EURUSD
```

## First Run

```bash
# Download data
python main.py download --symbol EURUSD --timeframe H1 --start 2024-01-01

# Run backtest
make run-backtest

# Paper trade
make run-paper
```

## Troubleshooting

### uv not found
```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip fallback (automatic)
make install
```

### MT5 connection failed
- Ensure MT5 terminal is running
- Check credentials in .env
- Verify broker server name

### Import errors
```bash
# Reinstall dependencies
make clean
make install
```

## Development Setup

```bash
# Install with dev tools
make install

# Run linting
make lint

# Format code
make format

# Run tests with coverage
make test-cov
```

## Updating

```bash
# Pull latest changes
git pull

# Update dependencies
make install

# Or with uv sync
make sync
```

## Uninstall

```bash
# Remove virtual environment
rm -rf .venv

# Clean build artifacts
make clean
```

---

**Ready to trade!** 🚀
