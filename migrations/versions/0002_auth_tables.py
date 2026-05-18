"""auth tables — users, sessions, preferences, memory

Revision ID: 0002_auth_tables
Revises: 0001_complete_schema
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_auth_tables'
down_revision = '0001_complete_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        'users',
        sa.Column('id',            sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email',         sa.String(255), nullable=False),
        sa.Column('name',          sa.String(100), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role',          sa.String(20), nullable=False, server_default='user'),
        sa.Column('is_active',     sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at',    sa.DateTime(), nullable=True),
        sa.Column('updated_at',    sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_id',    'users', ['id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # ── user_sessions ─────────────────────────────────────────────────────────
    op.create_table(
        'user_sessions',
        sa.Column('id',                 sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id',            sa.Integer(), nullable=False),
        sa.Column('refresh_token_hash', sa.String(255), nullable=False),
        sa.Column('expires_at',         sa.DateTime(), nullable=False),
        sa.Column('created_at',         sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_sessions_id',      'user_sessions', ['id'])
    op.create_index('ix_user_sessions_user_id', 'user_sessions', ['user_id'])

    # ── user_preferences ──────────────────────────────────────────────────────
    op.create_table(
        'user_preferences',
        sa.Column('id',                sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id',           sa.Integer(), nullable=False),
        sa.Column('risk_profile',      sa.String(20), nullable=True, server_default='moderate'),
        sa.Column('explanation_depth', sa.String(20), nullable=True, server_default='intermediate'),
        sa.Column('preferred_assets',  sa.JSON(), nullable=True),
        sa.Column('market_interests',  sa.JSON(), nullable=True),
        sa.Column('updated_at',        sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id'),
    )
    op.create_index('ix_user_preferences_id',      'user_preferences', ['id'])
    op.create_index('ix_user_preferences_user_id', 'user_preferences', ['user_id'])

    # ── user_memory ───────────────────────────────────────────────────────────
    op.create_table(
        'user_memory',
        sa.Column('id',         sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id',    sa.Integer(), nullable=False),
        sa.Column('type',       sa.String(50), nullable=False),
        sa.Column('key',        sa.String(100), nullable=False),
        sa.Column('value',      sa.JSON(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_memory_id',      'user_memory', ['id'])
    op.create_index('ix_user_memory_user_id', 'user_memory', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_memory_user_id',      table_name='user_memory')
    op.drop_index('ix_user_memory_id',           table_name='user_memory')
    op.drop_table('user_memory')
    op.drop_index('ix_user_preferences_user_id', table_name='user_preferences')
    op.drop_index('ix_user_preferences_id',      table_name='user_preferences')
    op.drop_table('user_preferences')
    op.drop_index('ix_user_sessions_user_id',    table_name='user_sessions')
    op.drop_index('ix_user_sessions_id',         table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_index('ix_users_id',    table_name='users')
    op.drop_table('users')
