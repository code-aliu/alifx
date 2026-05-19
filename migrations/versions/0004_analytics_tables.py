"""analytics tables — feedback_events, analytics_events

Revision ID: 0004_analytics_tables
Revises: 0003_prefs_v2
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_analytics_tables'
down_revision = '0003_prefs_v2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'feedback_events',
        sa.Column('id',          sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id',     sa.Integer(), nullable=True),
        sa.Column('feature',     sa.String(50), nullable=False),
        sa.Column('context_key', sa.String(100), nullable=True),
        sa.Column('intent',      sa.String(50), nullable=True),
        sa.Column('rating',      sa.SmallInteger(), nullable=False),
        sa.Column('clarity',     sa.SmallInteger(), nullable=True),
        sa.Column('notes',       sa.String(200), nullable=True),
        sa.Column('created_at',  sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_feedback_events_id',         'feedback_events', ['id'])
    op.create_index('ix_feedback_events_feature',    'feedback_events', ['feature'])
    op.create_index('ix_feedback_events_user_id',    'feedback_events', ['user_id'])
    op.create_index('ix_feedback_events_created_at', 'feedback_events', ['created_at'])

    op.create_table(
        'analytics_events',
        sa.Column('id',         sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('user_id',    sa.Integer(), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_analytics_events_id',         'analytics_events', ['id'])
    op.create_index('ix_analytics_events_event_type', 'analytics_events', ['event_type'])
    op.create_index('ix_analytics_events_user_id',    'analytics_events', ['user_id'])
    op.create_index('ix_analytics_events_created_at', 'analytics_events', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_analytics_events_created_at', table_name='analytics_events')
    op.drop_index('ix_analytics_events_user_id',    table_name='analytics_events')
    op.drop_index('ix_analytics_events_event_type', table_name='analytics_events')
    op.drop_index('ix_analytics_events_id',         table_name='analytics_events')
    op.drop_table('analytics_events')
    op.drop_index('ix_feedback_events_created_at', table_name='feedback_events')
    op.drop_index('ix_feedback_events_user_id',    table_name='feedback_events')
    op.drop_index('ix_feedback_events_feature',    table_name='feedback_events')
    op.drop_index('ix_feedback_events_id',         table_name='feedback_events')
    op.drop_table('feedback_events')
