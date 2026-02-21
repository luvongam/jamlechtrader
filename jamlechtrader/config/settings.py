"""Application settings loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # MT5 connection
    mt5_path: str = ""
    mt5_login: int = 0
    mt5_password: str = ""
    mt5_server: str = ""

    # Trading defaults
    default_symbol: str = "EURUSD"
    default_timeframe: str = "H1"
    default_lot_size: float = 0.01

    # Data storage
    data_dir: Path = Path("./data_cache")

    # Risk management
    max_daily_drawdown_pct: float = 5.0
    max_position_size: float = 1.0
    max_open_positions: int = 5


def get_settings() -> Settings:
    return Settings()
