"""complete schema — all tables in final state

Revision ID: 0001_complete_schema
Revises:
Create Date: 2026-05-17

Single authoritative migration covering the full production schema.
Replaces the two partial migrations that were generated against a local
database with manual table creation mixed in.
"""
from alembic import op
import sqlalchemy as sa

revision = '0001_complete_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── news_articles ─────────────────────────────────────────────────────────
    op.create_table(
        'news_articles',
        sa.Column('id',          sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('external_id', sa.String(255), nullable=True),
        sa.Column('title',       sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('content',     sa.Text(), nullable=True),
        sa.Column('url',         sa.String(1000), nullable=True),
        sa.Column('source_name', sa.String(100), nullable=True),
        sa.Column('provider',    sa.String(30), nullable=False),
        sa.Column('published_at',sa.DateTime(), nullable=True),
        sa.Column('fetched_at',  sa.DateTime(), nullable=False),
        sa.Column('processed',   sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id'),
    )
    op.create_index('ix_news_articles_processed',  'news_articles', ['processed'])
    op.create_index('ix_news_articles_published',  'news_articles', ['published_at'])

    # ── price_bars ────────────────────────────────────────────────────────────
    op.create_table(
        'price_bars',
        sa.Column('id',          sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol',      sa.String(20), nullable=False),
        sa.Column('asset_class', sa.String(10), nullable=False),
        sa.Column('open',        sa.Float(), nullable=False),
        sa.Column('high',        sa.Float(), nullable=False),
        sa.Column('low',         sa.Float(), nullable=False),
        sa.Column('close',       sa.Float(), nullable=False),
        sa.Column('volume',      sa.Float(), nullable=True),
        sa.Column('source',      sa.String(30), nullable=False),
        sa.Column('fetched_at',  sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_price_bars_symbol_fetched', 'price_bars', ['symbol', 'fetched_at'])

    # ── trading_signals ───────────────────────────────────────────────────────
    op.create_table(
        'trading_signals',
        sa.Column('id',           sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('asset',        sa.String(20), nullable=False),
        sa.Column('signal',       sa.String(10), nullable=False),
        sa.Column('confidence',   sa.Float(), nullable=False),
        sa.Column('time_horizon', sa.String(20), nullable=False),
        sa.Column('risk_level',   sa.String(10), nullable=False),
        sa.Column('reasoning',    sa.JSON(), nullable=False),
        sa.Column('event_ids',    sa.JSON(), nullable=True),
        sa.Column('entry_price',  sa.Float(), nullable=True),
        sa.Column('stop_loss',    sa.Float(), nullable=True),
        sa.Column('take_profit',  sa.Float(), nullable=True),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at',   sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_trading_signals_asset',        'trading_signals', ['asset'])
    op.create_index('ix_trading_signals_generated_at', 'trading_signals', ['generated_at'])

    # ── market_events ─────────────────────────────────────────────────────────
    op.create_table(
        'market_events',
        sa.Column('id',                sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('news_article_id',   sa.Integer(), nullable=True),
        sa.Column('headline',          sa.String(500), nullable=False),
        sa.Column('category',          sa.String(50), nullable=False),
        sa.Column('sentiment',         sa.String(20), nullable=False),
        sa.Column('importance',        sa.String(10), nullable=False),
        sa.Column('affected_assets',   sa.JSON(), nullable=False),
        sa.Column('keywords',          sa.JSON(), nullable=True),
        sa.Column('llm_enriched',      sa.String(5), nullable=False),
        sa.Column('extraction_method', sa.String(10), nullable=False),
        sa.Column('extracted_at',      sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['news_article_id'], ['news_articles.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_market_events_category',     'market_events', ['category'])
    op.create_index('ix_market_events_extracted_at', 'market_events', ['extracted_at'])

    # ── paper_portfolio ───────────────────────────────────────────────────────
    op.create_table(
        'paper_portfolio',
        sa.Column('id',              sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('initial_balance', sa.Float(), nullable=False),
        sa.Column('current_balance', sa.Float(), nullable=False),
        sa.Column('total_pnl',       sa.Float(), nullable=False),
        sa.Column('total_pnl_pct',   sa.Float(), nullable=False),
        sa.Column('win_count',       sa.Integer(), nullable=False),
        sa.Column('loss_count',      sa.Integer(), nullable=False),
        sa.Column('trade_count',     sa.Integer(), nullable=False),
        sa.Column('updated_at',      sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── paper_trades ──────────────────────────────────────────────────────────
    op.create_table(
        'paper_trades',
        sa.Column('id',             sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('symbol',         sa.String(20), nullable=False),
        sa.Column('direction',      sa.String(5), nullable=False),
        sa.Column('notional',       sa.Float(), nullable=False),
        sa.Column('entry_price',    sa.Float(), nullable=False),
        sa.Column('quantity',       sa.Float(), nullable=False),
        sa.Column('stop_loss',      sa.Float(), nullable=True),
        sa.Column('take_profit',    sa.Float(), nullable=True),
        sa.Column('signal_id',      sa.Integer(), nullable=True),
        sa.Column('confidence',     sa.Float(), nullable=True),
        sa.Column('status',         sa.String(10), nullable=False),
        sa.Column('exit_price',     sa.Float(), nullable=True),
        sa.Column('exit_reason',    sa.String(20), nullable=True),
        sa.Column('pnl',            sa.Float(), nullable=True),
        sa.Column('pnl_pct',        sa.Float(), nullable=True),
        sa.Column('opened_at',      sa.DateTime(), nullable=False),
        sa.Column('closed_at',      sa.DateTime(), nullable=True),
        sa.Column('regime_at_open', sa.String(50), nullable=True),
        sa.Column('regime_at_close',sa.String(50), nullable=True),
        sa.Column('audit_entry',    sa.JSON(), nullable=True),
        sa.Column('audit_exit',     sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_paper_trades_symbol_status', 'paper_trades', ['symbol', 'status'])
    op.create_index('ix_paper_trades_opened_at',     'paper_trades', ['opened_at'])

    # ── signal_outcomes ───────────────────────────────────────────────────────
    op.create_table(
        'signal_outcomes',
        sa.Column('id',               sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('signal_id',        sa.Integer(), nullable=False),
        sa.Column('asset',            sa.String(20), nullable=False),
        sa.Column('direction',        sa.String(10), nullable=False),
        sa.Column('confidence',       sa.Float(), nullable=False),
        sa.Column('time_horizon',     sa.String(20), nullable=False),
        sa.Column('status',           sa.String(20), nullable=False),
        sa.Column('price_at_signal',  sa.Float(), nullable=True),
        sa.Column('stop_loss',        sa.Float(), nullable=True),
        sa.Column('take_profit',      sa.Float(), nullable=True),
        sa.Column('price_at_close',   sa.Float(), nullable=True),
        sa.Column('price_change_pct', sa.Float(), nullable=True),
        sa.Column('outcome',          sa.String(20), nullable=True),
        sa.Column('market_regime',    sa.String(50), nullable=True),
        sa.Column('event_ids',        sa.JSON(), nullable=True),
        sa.Column('trade_id',         sa.Integer(), nullable=True),
        sa.Column('performance_score',sa.Float(), nullable=True),
        sa.Column('created_at',       sa.DateTime(), nullable=False),
        sa.Column('resolved_at',      sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('signal_id', name='uq_signal_outcomes_signal_id'),
    )
    op.create_index('ix_signal_outcomes_asset',  'signal_outcomes', ['asset'])
    op.create_index('ix_signal_outcomes_status', 'signal_outcomes', ['status'])

    # ── user_profiles ─────────────────────────────────────────────────────────
    op.create_table(
        'user_profiles',
        sa.Column('id',          sa.Integer(), primary_key=True),
        sa.Column('mode',        sa.String(20), nullable=False),
        sa.Column('preferences', sa.JSON(), nullable=False),
        sa.Column('updated_at',  sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('user_profiles')
    op.drop_index('ix_signal_outcomes_status', table_name='signal_outcomes')
    op.drop_index('ix_signal_outcomes_asset',  table_name='signal_outcomes')
    op.drop_table('signal_outcomes')
    op.drop_index('ix_paper_trades_opened_at',      table_name='paper_trades')
    op.drop_index('ix_paper_trades_symbol_status',  table_name='paper_trades')
    op.drop_table('paper_trades')
    op.drop_table('paper_portfolio')
    op.drop_index('ix_market_events_extracted_at', table_name='market_events')
    op.drop_index('ix_market_events_category',     table_name='market_events')
    op.drop_table('market_events')
    op.drop_index('ix_trading_signals_generated_at', table_name='trading_signals')
    op.drop_index('ix_trading_signals_asset',        table_name='trading_signals')
    op.drop_table('trading_signals')
    op.drop_index('ix_price_bars_symbol_fetched', table_name='price_bars')
    op.drop_table('price_bars')
    op.drop_index('ix_news_articles_published', table_name='news_articles')
    op.drop_index('ix_news_articles_processed', table_name='news_articles')
    op.drop_table('news_articles')
