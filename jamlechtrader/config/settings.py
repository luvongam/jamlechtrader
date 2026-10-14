"""Application settings loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Trading defaults
    default_symbol: str = "EURUSD"
    default_timeframe: str = "H1"
    default_lot_size: float = 0.01
    default_data_source: str = "yahoo"  # "yahoo" or "csv"

    # Data storage
    data_dir: Path = Path("./data_cache")

    # Risk management
    max_daily_drawdown_pct: float = 5.0
    max_position_size: float = 1.0
    max_open_positions: int = 5

    # Database
    database_url: str = "postgresql+asyncpg://jamlechtrader:jamlechtrader@localhost:5432/jamlechtrader"

    # Security
    use_secure_credentials: bool = False

    # Enterprise risk
    enterprise_risk: bool = False
    per_symbol_max_position: dict[str, float] | None = None
    per_symbol_max_notional: dict[str, float] | None = None
    max_total_notional: float = 1_000_000.0
    max_leverage_ratio: float = 10.0
    max_margin_utilization_pct: float = 80.0
    var_confidence_level: float = 0.95
    max_var_pct: float = 5.0
    kill_switch_drawdown_pct: float = 10.0
    kill_switch_max_loss: float = 50_000.0
    kill_switch_consecutive_losses: int = 10

    # Monitoring
    prometheus_port: int = 9090
    dashboard_port: int = 8080


def get_settings() -> Settings:
    return Settings()
