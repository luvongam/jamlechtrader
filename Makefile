.PHONY: venv sync install test lint format clean run-backtest run-paper

venv:
	@command -v uv >/dev/null 2>&1 && uv venv || python -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

sync:
	@command -v uv >/dev/null 2>&1 && uv sync || (source .venv/bin/activate && pip install -e ".[reports,dev]")

install:
	@command -v uv >/dev/null 2>&1 && uv pip install -e ".[reports,dev]" || pip install -e ".[reports,dev]"
	@echo "✅ Installation complete for Python 3.14!"
	@echo "📊 Using custom SMC implementation (no external package needed)"
	@echo "ℹ️  MT5 is Windows-only, skipped on Linux"

install-minimal:
	@command -v uv >/dev/null 2>&1 && uv pip install -e ".[reports,dev]" || pip install -e ".[reports,dev]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=jamlechtrader --cov-report=html

lint:
	ruff check jamlechtrader/
	mypy jamlechtrader/

format:
	ruff format jamlechtrader/
	ruff check --fix jamlechtrader/

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf build/ dist/ *.egg-info
	rm -rf .pytest_cache .coverage htmlcov/

run-backtest:
	python main.py backtest -s advanced_smc --start 2024-01-01 --end 2024-12-31 --tearsheet

run-paper:
	python main.py paper -s smart_money --duration 600

account:
	python main.py account
