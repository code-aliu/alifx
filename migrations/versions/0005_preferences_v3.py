"""user_preferences v3 — add time_horizon, macro_sensitivity, portfolio_style

Revision ID: 0005_preferences_v3
Revises: 0004_analytics_tables
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '0005_preferences_v3'
down_revision = '0004_analytics_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_preferences', sa.Column(
        'time_horizon', sa.String(20), nullable=True, server_default='medium_term',
    ))
    op.add_column('user_preferences', sa.Column(
        'macro_sensitivity', sa.String(20), nullable=True, server_default='medium',
    ))
    op.add_column('user_preferences', sa.Column(
        'portfolio_style', sa.String(20), nullable=True, server_default='balanced',
    ))


def downgrade() -> None:
    op.drop_column('user_preferences', 'portfolio_style')
    op.drop_column('user_preferences', 'macro_sensitivity')
    op.drop_column('user_preferences', 'time_horizon')
