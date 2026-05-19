"""user_preferences v2 — add user_type, onboarded; rename moderate→balanced default

Revision ID: 0003_prefs_v2
Revises: 0002_auth_tables
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_prefs_v2'
down_revision = '0002_auth_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('user_preferences', sa.Column('user_type',  sa.String(20), nullable=True, server_default='intermediate'))
    op.add_column('user_preferences', sa.Column('onboarded',  sa.Boolean(),  nullable=True, server_default='false'))
    # Rename existing 'moderate' risk_profile values to 'balanced'
    op.execute("UPDATE user_preferences SET risk_profile = 'balanced' WHERE risk_profile = 'moderate'")


def downgrade() -> None:
    op.execute("UPDATE user_preferences SET risk_profile = 'moderate' WHERE risk_profile = 'balanced'")
    op.drop_column('user_preferences', 'onboarded')
    op.drop_column('user_preferences', 'user_type')
