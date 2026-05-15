"""
Integration tests — Phase 1: News Ingestion

Tests article persistence, deduplication, and retrieval without hitting
real external APIs. Uses the real ORM models against SQLite in-memory.
"""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app.news.base import Article
from app.news.models import NewsArticle
from app.news.service import (
    fetch_and_store_all,
    get_unprocessed,
    get_recent,
    _is_new,
    _persist,
)
from tests.conftest import make_article


# ── Article persistence ───────────────────────────────────────────────────────

class TestArticlePersistence:

    def test_persist_new_article(self, db):
        article = make_article(
            db,
            title="Bitcoin ETF sees record $1.2B inflows as institutional demand surges",
            description="BlackRock's iShares Bitcoin Trust receives largest single-day inflow.",
            provider="newsapi",
            external_id="btc-etf-001",
        )

        assert article.id is not None
        assert article.processed is False
        assert article.external_id == "btc-etf-001"
        assert "Bitcoin ETF" in article.title

    def test_to_dict_contains_required_fields(self, db):
        article = make_article(
            db,
            title="Fed signals dovish pivot as inflation cools to 2.1%",
            provider="rss",
        )

        d = article.to_dict()
        assert set(d.keys()) >= {"id", "title", "description", "source_name",
                                  "provider", "published_at", "fetched_at"}

    def test_is_new_returns_true_for_unknown_id(self, db):
        assert _is_new(db, "never-seen-id-xyz") is True

    def test_is_new_returns_false_for_existing_id(self, db):
        make_article(db, title="Existing article", external_id="dup-001")
        assert _is_new(db, "dup-001") is False

    def test_is_new_allows_null_external_id(self, db):
        assert _is_new(db, None) is True


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:

    def test_duplicate_external_id_not_stored_twice(self, db):
        article_obj = Article(
            external_id="unique-btc-123",
            title="BTC breaks $100k milestone",
            description="Bitcoin reaches six figures for the first time.",
            content=None,
            url="https://coindesk.com/btc-100k",
            source_name="CoinDesk",
            provider="rss",
            published_at=datetime.utcnow(),
        )

        with patch("app.news.service._build_providers") as mock_providers:
            provider = MagicMock()
            provider.name = "mock_rss"
            provider.fetch_articles.return_value = [article_obj, article_obj]
            mock_providers.return_value = [provider]

            stored = fetch_and_store_all(db)

        assert stored == 1
        count = db.query(NewsArticle).filter(
            NewsArticle.external_id == "unique-btc-123"
        ).count()
        assert count == 1

    def test_two_different_articles_stored_independently(self, db):
        articles = [
            Article(
                external_id=f"article-{i}",
                title=f"Market update #{i}",
                description="",
                content=None,
                url=f"https://example.com/{i}",
                source_name="Reuters",
                provider="rss",
                published_at=datetime.utcnow(),
            )
            for i in range(3)
        ]

        with patch("app.news.service._build_providers") as mock_providers:
            provider = MagicMock()
            provider.name = "mock"
            provider.fetch_articles.return_value = articles
            mock_providers.return_value = [provider]

            stored = fetch_and_store_all(db)

        assert stored == 3

    def test_provider_failure_does_not_crash_pipeline(self, db):
        with patch("app.news.service._build_providers") as mock_providers:
            failing = MagicMock()
            failing.name = "broken_provider"
            failing.fetch_articles.side_effect = ConnectionError("API unreachable")
            mock_providers.return_value = [failing]

            stored = fetch_and_store_all(db)

        assert stored == 0


# ── Retrieval ─────────────────────────────────────────────────────────────────

class TestRetrieval:

    def test_get_unprocessed_returns_only_unprocessed(self, db):
        make_article(db, title="Unprocessed article A", processed=False)
        make_article(db, title="Unprocessed article B", processed=False)
        make_article(db, title="Already processed", processed=True,
                     external_id="proc-001")

        results = get_unprocessed(db)
        assert len(results) == 2
        assert all(not r.processed for r in results)

    def test_get_unprocessed_respects_limit(self, db):
        for i in range(10):
            make_article(db, title=f"Article {i}", external_id=f"art-{i}")

        results = get_unprocessed(db, limit=4)
        assert len(results) == 4

    def test_get_recent_returns_articles_within_window(self, db):
        now = datetime.utcnow()
        make_article(db, title="Fresh news",
                     published_at=now - timedelta(hours=1),
                     fetched_at=now - timedelta(hours=1))
        # fetched_at 30 hours ago — outside the 24-hour window
        make_article(db, title="Old news",
                     published_at=now - timedelta(hours=30),
                     fetched_at=now - timedelta(hours=30),
                     external_id="old-001")

        results = get_recent(db, hours=24)
        titles = [r["title"] for r in results]
        assert "Fresh news" in titles
        assert "Old news" not in titles

    def test_get_recent_returns_dict_list(self, db):
        make_article(db, title="Some news story")
        results = get_recent(db, hours=24)
        assert isinstance(results, list)
        assert isinstance(results[0], dict)
        assert "title" in results[0]
        assert "provider" in results[0]

    def test_get_recent_limit_respected(self, db):
        for i in range(20):
            make_article(db, title=f"Story {i}", external_id=f"s-{i}")

        results = get_recent(db, hours=24, limit=5)
        assert len(results) == 5
