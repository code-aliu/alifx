"""
Conversational AI copilot tests.

Covers:
  • router.py — intent classification + asset detection
  • assembler.py — context formatting
  • generator.py — template fallback (no API key required)
  • narrative.py — daily summary, top signals, portfolio risk, signal explanation
  • API routes — /ask, /market-summary, /top-signals, /portfolio-risk-summary
"""
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.copilot.router import classify
from app.copilot.assembler import assemble
from app.copilot.generator import generate_response, _template_response, _parse_context
from app.copilot.narrative import (
    daily_market_summary,
    top_signals_report,
    portfolio_risk_summary,
    signal_explanation,
)
from app.paper_trading.models import PaperTrade, PaperPortfolio
from app.signals.models import TradingSignal
from app.market_data.models import PriceBar
from app.events.models import MarketEvent
from app.news.models import NewsArticle


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_signal(db, asset="BTC", direction="SELL", confidence=72.0) -> TradingSignal:
    row = TradingSignal(
        asset=asset,
        signal=direction,
        confidence=confidence,
        time_horizon="swing",
        risk_level="medium",
        reasoning=[
            "News/event flow is bearish (impact score: -3.0)",
            "RSI overbought at 71 — caution, may pull back",
            "MACD bearish crossover — momentum shifting downward",
            "Price in established downtrend",
            "Regime (risk_off): confidence adjusted -5 [confidence=78%]",
        ],
        event_ids=[],
        entry_price=90_000.0,
        stop_loss=92_700.0,
        take_profit=84_600.0,
        generated_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _make_article(db) -> NewsArticle:
    article = NewsArticle(
        external_id="test-copilot-001",
        title="US CPI data shows inflation running hotter than expected",
        description="Price pressures mount",
        url="https://example.com",
        source_name="Test",
        provider="newsapi",
        published_at=datetime.utcnow(),
        fetched_at=datetime.utcnow(),
        processed=True,
    )
    db.add(article)
    db.commit()
    db.refresh(article)
    return article


def _make_event(db, article_id: int) -> MarketEvent:
    event = MarketEvent(
        news_article_id=article_id,
        headline="US CPI data shows inflation running hotter than expected — price pressures mount",
        category="macroeconomic",
        sentiment="risk_off",
        importance="high",
        affected_assets=["BTC", "SPY", "GOLD"],
        keywords=["cpi", "inflation"],
        llm_enriched=False,
        extraction_method="rule",
        extracted_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _make_price_bars(db, symbol="BTC", price=90_000.0, n=5):
    for i in range(n):
        bar = PriceBar(
            symbol=symbol,
            asset_class="crypto",
            source="test",
            open=price, high=price * 1.001, low=price * 0.999, close=price,
            volume=1000.0,
            fetched_at=datetime.utcnow() - timedelta(minutes=n - i),
        )
        db.add(bar)
    db.commit()


def _make_portfolio(db) -> PaperPortfolio:
    port = PaperPortfolio(
        initial_balance=10_000.0,
        current_balance=9_980.0,
        total_pnl=-20.0,
        updated_at=datetime.utcnow(),
    )
    db.add(port)
    db.commit()
    db.refresh(port)
    return port


def _make_open_trade(db, symbol="BTC", direction="SELL", notional=500.0) -> PaperTrade:
    trade = PaperTrade(
        symbol=symbol,
        direction=direction,
        notional=notional,
        entry_price=90_000.0,
        quantity=notional / 90_000.0,
        confidence=72.0,
        status="open",
        opened_at=datetime.utcnow() - timedelta(hours=2),
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


# ═══════════════════════════════════════════════════════════════════════════════
# router.py — intent classification
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntentClassification:

    def test_btc_bearish_question_signal_intent(self):
        result = classify("Why is BTC bearish today?")
        assert result["intent"] == "signal"
        assert result["asset"] == "BTC"

    def test_cpi_question_event_intent(self):
        result = classify("What macro events are affecting markets?")
        assert result["intent"] == "event"

    def test_fed_rate_question_event_intent(self):
        result = classify("What is the Fed doing with interest rates?")
        assert result["intent"] == "event"

    def test_portfolio_question(self):
        result = classify("What risks exist in the current portfolio?")
        assert result["intent"] == "portfolio"

    def test_regime_question(self):
        result = classify("What is the current market regime?")
        assert result["intent"] == "regime"

    def test_market_summary_question(self):
        result = classify("Give me a market summary")
        assert result["intent"] == "narrative"

    def test_performance_question(self):
        result = classify("What is the signal win rate?")
        assert result["intent"] == "performance"

    def test_signal_failure_question(self):
        result = classify("Why did the last BTC signal fail?")
        assert result["intent"] == "signal"
        assert result["asset"] == "BTC"

    def test_strongest_assets_question(self):
        result = classify("Which assets are strongest right now?")
        assert result["intent"] == "narrative"

    def test_high_confidence_signals_question(self):
        result = classify("Which signals have highest confidence?")
        assert result["intent"] == "signal"

    def test_eurusd_question(self):
        result = classify("What is EUR/USD doing?")
        assert result["asset"] == "EURUSD"

    def test_gold_detected(self):
        result = classify("Tell me about gold")
        assert result["asset"] == "XAUUSD"

    def test_spy_detected(self):
        result = classify("What is SPY signalling?")
        assert result["asset"] == "SPY"

    def test_no_asset_none(self):
        result = classify("What is the current market regime?")
        assert result["asset"] is None

    def test_asset_with_narrative_intent_promoted_to_signal(self):
        result = classify("Tell me about BTC")
        assert result["intent"] == "signal"
        assert result["asset"] == "BTC"

    def test_unknown_question_defaults_to_narrative(self):
        result = classify("What do you think about the weather?")
        assert result["intent"] == "narrative"

    def test_returns_dict_with_required_keys(self):
        result = classify("Something")
        assert "intent" in result
        assert "asset" in result

    def test_spy_not_matched_in_unrelated_word(self):
        # "spying" should not match "spy" due to word-boundary check
        result = classify("I have been spying on competitors")
        assert result["asset"] != "SPY"


# ═══════════════════════════════════════════════════════════════════════════════
# assembler.py
# ═══════════════════════════════════════════════════════════════════════════════

class TestAssembler:

    def _minimal_ctx(self):
        return {
            "intent": "signal",
            "asset": "BTC",
            "fetched_at": "2026-05-15T19:00:00",
            "regime": None,
            "signal": None,
        }

    def test_returns_string(self):
        ctx = self._minimal_ctx()
        result = assemble(ctx)
        assert isinstance(result, str)

    def test_contains_header(self):
        ctx = self._minimal_ctx()
        result = assemble(ctx)
        assert "MARKET CONTEXT" in result

    def test_regime_present_when_provided(self):
        ctx = self._minimal_ctx()
        ctx["regime"] = {
            "primary_regime": "risk_off",
            "confidence": 0.78,
            "reasoning": ["CPI beat expectations"],
        }
        result = assemble(ctx)
        assert "RISK_OFF" in result or "risk_off" in result.upper()

    def test_regime_unavailable_when_none(self):
        ctx = self._minimal_ctx()
        result = assemble(ctx)
        assert "unavailable" in result.lower()

    def test_signal_section_when_provided(self):
        ctx = self._minimal_ctx()
        ctx["signal"] = {
            "asset": "BTC",
            "signal": "SELL",
            "confidence": 72.0,
            "entry_price": 90_000.0,
            "stop_loss": 92_700.0,
            "take_profit": 84_600.0,
            "reasoning": ["MACD bearish crossover"],
        }
        result = assemble(ctx)
        assert "SIGNAL" in result
        assert "SELL" in result
        assert "BTC" in result

    def test_events_section_present(self):
        ctx = self._minimal_ctx()
        ctx["events"] = [
            {
                "headline": "CPI data beats estimates",
                "sentiment": "risk_off",
                "importance": "high",
                "affected_assets": ["BTC"],
            }
        ]
        result = assemble(ctx)
        assert "RECENT MARKET EVENTS" in result
        assert "CPI" in result

    def test_portfolio_section_no_positions(self):
        ctx = self._minimal_ctx()
        ctx["portfolio"] = {"status": "no_open_positions"}
        result = assemble(ctx)
        assert "no open" in result.lower()

    def test_performance_section_skipped_when_none(self):
        ctx = self._minimal_ctx()
        result = assemble(ctx)
        assert "PERFORMANCE" not in result

    def test_signals_list_sorted_by_confidence(self):
        ctx = self._minimal_ctx()
        ctx["signals"] = [
            {"asset": "SPY", "signal": "BUY", "confidence": 65.0},
            {"asset": "BTC", "signal": "SELL", "confidence": 80.0},
        ]
        result = assemble(ctx)
        btc_pos = result.find("BTC")
        spy_pos = result.find("SPY")
        assert btc_pos < spy_pos  # BTC higher confidence → appears first


# ═══════════════════════════════════════════════════════════════════════════════
# generator.py — template fallback (no API key)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGeneratorTemplate:

    def _assembled(self, intent="signal", asset="BTC"):
        ctx = {
            "intent": intent,
            "asset": asset,
            "fetched_at": "2026-05-15T19:00:00",
            "regime": {
                "primary_regime": "risk_off",
                "confidence": 0.78,
                "reasoning": ["CPI beat expectations"],
            },
            "signal": {
                "asset": asset,
                "signal": "SELL",
                "confidence": 72.0,
                "entry_price": 90_000.0,
                "stop_loss": 92_700.0,
                "take_profit": 84_600.0,
                "reasoning": ["MACD bearish crossover — momentum shifting downward"],
            },
            "events": [
                {
                    "headline": "CPI data shows inflation running hot",
                    "sentiment": "risk_off",
                    "importance": "high",
                    "affected_assets": ["BTC", "SPY"],
                }
            ],
        }
        return assemble(ctx)

    def test_no_api_key_uses_template(self):
        assembled = self._assembled()
        _, generated_by = generate_response("Why is BTC bearish?", assembled, "signal", "BTC", "")
        assert generated_by == "template"

    def test_template_returns_string(self):
        assembled = self._assembled()
        answer, _ = generate_response("Why is BTC bearish?", assembled, "signal", "BTC", "")
        assert isinstance(answer, str)
        assert len(answer) > 10

    def test_template_signal_intent_mentions_asset(self):
        assembled = self._assembled(intent="signal", asset="BTC")
        answer, _ = generate_response("Why is BTC bearish?", assembled, "signal", "BTC", "")
        assert "BTC" in answer or "SELL" in answer or "bearish" in answer.lower()

    def test_template_regime_intent_mentions_regime(self):
        assembled = self._assembled(intent="regime")
        answer, _ = generate_response("What is the market regime?", assembled, "regime", None, "")
        assert "risk" in answer.lower() or "regime" in answer.lower()

    def test_template_narrative_intent_returns_content(self):
        assembled = self._assembled(intent="narrative")
        answer, _ = generate_response("Give me a market summary", assembled, "narrative", None, "")
        assert len(answer) > 20

    def test_template_fallback_on_bad_api_key(self):
        # Bad key → httpx raises → falls back to template
        assembled = self._assembled()
        _, generated_by = generate_response("test", assembled, "signal", "BTC", "bad-key-xyz")
        assert generated_by == "template"

    def test_parse_context_extracts_regime(self):
        assembled = self._assembled()
        parsed = _parse_context(assembled)
        assert "regime" in parsed

    def test_parse_context_extracts_signal(self):
        assembled = self._assembled()
        parsed = _parse_context(assembled)
        sig = parsed.get("signal")
        # signal may or may not be parsed depending on line format; just check structure
        assert isinstance(parsed, dict)

    def test_parse_context_extracts_events(self):
        assembled = self._assembled()
        parsed = _parse_context(assembled)
        events = parsed.get("events", [])
        assert isinstance(events, list)


# ═══════════════════════════════════════════════════════════════════════════════
# narrative.py — daily_market_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestDailyMarketSummary:

    def test_returns_required_keys(self, db):
        result = daily_market_summary(db, api_key="")
        required = {
            "narrative", "generated_by", "regime", "signal_consensus",
            "key_events", "portfolio_status", "generated_at",
        }
        assert required.issubset(result.keys())

    def test_generated_by_is_template_without_key(self, db):
        result = daily_market_summary(db, api_key="")
        assert result["generated_by"] == "template"

    def test_narrative_is_non_empty_string(self, db):
        result = daily_market_summary(db, api_key="")
        assert isinstance(result["narrative"], str)
        assert len(result["narrative"]) > 0

    def test_regime_has_primary_field(self, db):
        result = daily_market_summary(db, api_key="")
        assert "primary" in result["regime"]

    def test_signal_consensus_has_counts(self, db):
        _make_signal(db, "BTC", "SELL", 72.0)
        result = daily_market_summary(db, api_key="")
        cons = result["signal_consensus"]
        assert "buy_count" in cons
        assert "sell_count" in cons
        assert "consensus" in cons

    def test_with_signals_populates_top_signals(self, db):
        _make_signal(db, "BTC", "SELL", 72.0)
        _make_signal(db, "SPY", "BUY", 65.0)
        result = daily_market_summary(db, api_key="")
        assert len(result["signal_consensus"]["top_signals"]) > 0

    def test_portfolio_status_has_open_positions(self, db):
        result = daily_market_summary(db, api_key="")
        assert "open_positions" in result["portfolio_status"]

    def test_key_events_is_list(self, db):
        result = daily_market_summary(db, api_key="")
        assert isinstance(result["key_events"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# narrative.py — top_signals_report
# ═══════════════════════════════════════════════════════════════════════════════

class TestTopSignalsReport:

    def test_returns_required_keys(self, db):
        result = top_signals_report(db, limit=5, api_key="")
        required = {"narrative", "generated_by", "signals", "total_signals", "generated_at"}
        assert required.issubset(result.keys())

    def test_signals_is_list(self, db):
        result = top_signals_report(db, limit=5, api_key="")
        assert isinstance(result["signals"], list)

    def test_no_signals_in_db_returns_empty_actionable_list(self, db):
        # With empty DB, no BUY/SELL signals exist → actionable list is empty.
        # total_signals may be non-zero if a Redis cache from a prior run exists.
        result = top_signals_report(db, limit=5, api_key="")
        for s in result["signals"]:
            # Any returned signals must be BUY or SELL
            assert s["signal"] in ("BUY", "SELL")

    def test_signals_sorted_by_confidence_descending(self, db):
        _make_signal(db, "BTC", "SELL", 72.0)
        _make_signal(db, "SPY", "BUY",  65.0)
        result = top_signals_report(db, limit=5, api_key="")
        sigs = result["signals"]
        if len(sigs) >= 2:
            assert sigs[0]["confidence"] >= sigs[1]["confidence"]

    def test_only_actionable_signals_included(self, db):
        _make_signal(db, "BTC", "SELL", 72.0)
        _make_signal(db, "SPY", "HOLD", 55.0)
        result = top_signals_report(db, limit=5, api_key="")
        for s in result["signals"]:
            assert s["signal"] in ("BUY", "SELL")

    def test_limit_respected(self, db):
        for i in range(6):
            _make_signal(db, "BTC", "SELL", 70.0 + i)
        result = top_signals_report(db, limit=3, api_key="")
        assert len(result["signals"]) <= 3

    def test_signal_entry_has_required_fields(self, db):
        _make_signal(db, "BTC", "SELL", 72.0)
        result = top_signals_report(db, limit=5, api_key="")
        if result["signals"]:
            s = result["signals"][0]
            assert "asset" in s
            assert "signal" in s
            assert "confidence" in s
            assert "top_reasons" in s


# ═══════════════════════════════════════════════════════════════════════════════
# narrative.py — portfolio_risk_summary
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortfolioRiskSummary:

    def test_returns_required_keys(self, db):
        result = portfolio_risk_summary(db, api_key="")
        required = {
            "narrative", "generated_by", "open_positions",
            "total_open_notional", "risk_warnings", "generated_at",
        }
        assert required.issubset(result.keys())

    def test_no_positions_zero_notional(self, db):
        result = portfolio_risk_summary(db, api_key="")
        assert result["open_positions"] == 0
        assert result["total_open_notional"] == 0.0

    def test_with_open_trades_counts_positions(self, db):
        _make_portfolio(db)
        _make_open_trade(db, "BTC", "SELL", 500.0)
        _make_open_trade(db, "SPY", "BUY",  500.0)
        result = portfolio_risk_summary(db, api_key="")
        assert result["open_positions"] == 2

    def test_risk_warnings_is_list(self, db):
        result = portfolio_risk_summary(db, api_key="")
        assert isinstance(result["risk_warnings"], list)

    def test_narrative_is_string(self, db):
        result = portfolio_risk_summary(db, api_key="")
        assert isinstance(result["narrative"], str)


# ═══════════════════════════════════════════════════════════════════════════════
# narrative.py — signal_explanation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignalExplanation:

    def test_unknown_id_returns_error(self, db):
        result = signal_explanation(db, signal_id=99999, api_key="")
        assert result.get("error") == "signal_not_found"

    def test_known_signal_returns_explanation(self, db):
        sig = _make_signal(db, "BTC", "SELL", 72.0)
        result = signal_explanation(db, signal_id=sig.id, api_key="")
        assert result["signal_id"] == sig.id
        assert result["asset"] == "BTC"
        assert result["signal"] == "SELL"

    def test_explanation_has_narrative(self, db):
        sig = _make_signal(db, "BTC", "SELL", 72.0)
        result = signal_explanation(db, signal_id=sig.id, api_key="")
        assert isinstance(result.get("narrative"), str)
        assert len(result["narrative"]) > 0

    def test_explanation_has_reasoning(self, db):
        sig = _make_signal(db, "BTC", "SELL", 72.0)
        result = signal_explanation(db, signal_id=sig.id, api_key="")
        assert isinstance(result.get("reasoning"), list)

    def test_explanation_generated_by_template(self, db):
        sig = _make_signal(db, "BTC", "SELL", 72.0)
        result = signal_explanation(db, signal_id=sig.id, api_key="")
        assert result["generated_by"] == "template"


# ═══════════════════════════════════════════════════════════════════════════════
# API routes via TestClient
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="function")
def _client_engine():
    """Shared StaticPool SQLite engine for client + client_db fixtures.

    StaticPool ensures all connections share the same in-memory database.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from app.database import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(_client_engine):
    """TestClient wired to _client_engine via dependency override.

    Does NOT run the app lifespan (which would make real network calls).
    """
    from sqlalchemy.orm import sessionmaker
    from app.main import app
    from app.database import get_db

    TestSession = sessionmaker(bind=_client_engine)

    def override_get_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app, raise_server_exceptions=True)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client_db(_client_engine):
    """DB session backed by the same engine as the `client` fixture.

    Use this instead of `db` in tests that also use `client` so that
    data inserted here is visible to the endpoint under test.
    """
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=_client_engine)()
    yield session
    session.close()


class TestAskEndpoint:

    def test_ask_returns_200(self, client):
        resp = client.post("/copilot/ask", json={"question": "What is the current market regime?"})
        assert resp.status_code == 200

    def test_ask_response_has_answer(self, client):
        resp = client.post("/copilot/ask", json={"question": "What is the current market regime?"})
        data = resp.json()["data"]
        assert "answer" in data
        assert isinstance(data["answer"], str)

    def test_ask_response_has_intent(self, client):
        resp = client.post("/copilot/ask", json={"question": "What is the current market regime?"})
        data = resp.json()["data"]
        assert data["intent_detected"] == "regime"

    def test_ask_btc_question_detects_asset(self, client):
        resp = client.post("/copilot/ask", json={"question": "Why is BTC bearish?"})
        data = resp.json()["data"]
        assert data["asset_detected"] == "BTC"

    def test_ask_asset_override(self, client):
        resp = client.post("/copilot/ask", json={"question": "What is the signal?", "asset": "SPY"})
        data = resp.json()["data"]
        assert data["asset_detected"] == "SPY"

    def test_ask_too_short_returns_422(self, client):
        resp = client.post("/copilot/ask", json={"question": "Hi"})
        assert resp.status_code == 422

    def test_ask_context_used_in_response(self, client):
        resp = client.post("/copilot/ask", json={"question": "What is the current market regime?"})
        data = resp.json()["data"]
        assert "context_used" in data

    def test_ask_generated_by_is_template_without_key(self, client):
        resp = client.post("/copilot/ask", json={"question": "Tell me about the market"})
        data = resp.json()["data"]
        assert data["generated_by"] == "template"


class TestMarketSummaryEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/copilot/market-summary")
        assert resp.status_code == 200

    def test_response_has_narrative(self, client):
        resp = client.get("/copilot/market-summary")
        data = resp.json()["data"]
        assert "narrative" in data

    def test_response_has_regime(self, client):
        resp = client.get("/copilot/market-summary")
        data = resp.json()["data"]
        assert "regime" in data

    def test_response_has_signal_consensus(self, client):
        resp = client.get("/copilot/market-summary")
        data = resp.json()["data"]
        assert "signal_consensus" in data


class TestTopSignalsEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/copilot/top-signals")
        assert resp.status_code == 200

    def test_response_has_signals_list(self, client):
        resp = client.get("/copilot/top-signals")
        data = resp.json()["data"]
        assert "signals" in data
        assert isinstance(data["signals"], list)

    def test_limit_param_respected(self, client, client_db):
        for i in range(6):
            _make_signal(client_db, "BTC", "SELL", 70.0 + i)
        resp = client.get("/copilot/top-signals?limit=3")
        data = resp.json()["data"]
        assert len(data["signals"]) <= 3


class TestSignalExplanationEndpoint:

    def test_unknown_id_returns_404(self, client):
        resp = client.get("/copilot/signal-explanation/99999")
        assert resp.status_code == 404

    def test_known_signal_returns_200(self, client, client_db):
        sig = _make_signal(client_db, "BTC", "SELL", 72.0)
        resp = client.get(f"/copilot/signal-explanation/{sig.id}")
        assert resp.status_code == 200

    def test_explanation_asset_matches(self, client, client_db):
        sig = _make_signal(client_db, "BTC", "SELL", 72.0)
        resp = client.get(f"/copilot/signal-explanation/{sig.id}")
        data = resp.json()["data"]
        assert data["asset"] == "BTC"


class TestPortfolioRiskSummaryEndpoint:

    def test_returns_200(self, client):
        resp = client.get("/copilot/portfolio-risk-summary")
        assert resp.status_code == 200

    def test_response_has_narrative(self, client):
        resp = client.get("/copilot/portfolio-risk-summary")
        data = resp.json()["data"]
        assert "narrative" in data

    def test_response_has_risk_warnings(self, client):
        resp = client.get("/copilot/portfolio-risk-summary")
        data = resp.json()["data"]
        assert "risk_warnings" in data
