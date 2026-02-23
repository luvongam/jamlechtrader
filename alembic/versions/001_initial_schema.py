"""Initial schema — orders, fills, positions, snapshots, audit_log, closed_trades.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Orders
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("client_order_id", sa.String(64), unique=True, nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("order_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=True),
        sa.Column("stop_loss", sa.Float, nullable=True),
        sa.Column("take_profit", sa.Float, nullable=True),
        sa.Column("time_in_force", sa.String(8), server_default="GTC"),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("broker_order_id", sa.String(64), nullable=True),
        sa.Column("strategy_name", sa.String(64), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_orders_client_order_id", "orders", ["client_order_id"])
    op.create_index("ix_orders_symbol", "orders", ["symbol"])
    op.create_index("ix_orders_status", "orders", ["status"])

    # Fills
    op.create_table(
        "fills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("commission", sa.Float, server_default="0"),
        sa.Column("slippage", sa.Float, server_default="0"),
        sa.Column("broker_fill_id", sa.String(64), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_fills_order_id", "fills", ["order_id"])

    # Positions
    op.create_table(
        "positions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False, unique=True),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("current_price", sa.Float, server_default="0"),
        sa.Column("stop_loss", sa.Float, nullable=True),
        sa.Column("take_profit", sa.Float, nullable=True),
        sa.Column("unrealized_pnl", sa.Float, server_default="0"),
        sa.Column("ticket", sa.Integer, server_default="0"),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Portfolio snapshots
    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("cash", sa.Float, nullable=False),
        sa.Column("equity", sa.Float, nullable=False),
        sa.Column("margin_used", sa.Float, server_default="0"),
        sa.Column("unrealized_pnl", sa.Float, server_default="0"),
        sa.Column("realized_pnl", sa.Float, server_default="0"),
        sa.Column("drawdown", sa.Float, server_default="0"),
        sa.Column("positions", JSONB, nullable=True),
    )
    op.create_index("ix_portfolio_snapshots_timestamp", "portfolio_snapshots", ["timestamp"])

    # Audit log — APPEND-ONLY
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", JSONB, nullable=True),
        sa.Column("correlation_id", sa.String(36), nullable=True),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_correlation_id", "audit_log", ["correlation_id"])
    op.create_index(
        "ix_audit_log_event_type_timestamp", "audit_log", ["event_type", "timestamp"]
    )

    # Closed trades
    op.create_table(
        "closed_trades",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("side", sa.String(4), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float, nullable=False),
        sa.Column("exit_price", sa.Float, nullable=False),
        sa.Column("pnl", sa.Float, nullable=False),
        sa.Column("commission", sa.Float, server_default="0"),
        sa.Column("strategy_name", sa.String(64), nullable=True),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=True),
        sa.Column("tags", JSONB, nullable=True),
    )
    op.create_index("ix_closed_trades_symbol", "closed_trades", ["symbol"])


def downgrade() -> None:
    op.drop_table("closed_trades")
    op.drop_table("audit_log")
    op.drop_table("portfolio_snapshots")
    op.drop_table("positions")
    op.drop_table("fills")
    op.drop_table("orders")
