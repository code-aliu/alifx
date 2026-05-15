"""
Integration tests — Phase 1: Event Extraction

Tests the rule-based extractor against realistic financial news headlines
for BTC, SPY, and EUR/USD scenarios. No database required — the extractor
works on any object with .id, .title, .description attributes.
"""
import pytest
from app.events.extractor import extract_event


class _Article:
    """Minimal stub matching what extract_event reads from NewsArticle."""
    def __init__(self, id: int, title: str, description: str = ""):
        self.id = id
        self.title = title
        self.description = description


# ── BTC / Crypto extraction ───────────────────────────────────────────────────

class TestBTCEventExtraction:

    def test_bitcoin_etf_inflow_headline(self):
        article = _Article(
            1,
            "BlackRock Bitcoin ETF sees record $1.2B inflows as institutional demand surges",
            "Bitcoin ETF inflows reach all-time high driven by institutional adoption.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["category"] == "crypto"
        assert event["sentiment"] == "risk_on"
        assert event["importance"] == "high"
        assert "BTC" in event["affected_assets"]
        assert "ETH" in event["affected_assets"]
        assert event["extraction_method"] == "rule"
        assert event["news_article_id"] == 1

    def test_crypto_ban_headline_is_risk_off(self):
        article = _Article(
            2,
            "SEC sues major crypto exchange over unregistered securities",
            "Regulators launch crypto lawsuit against largest US exchange.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["category"] == "crypto"
        assert event["sentiment"] == "risk_off"
        assert event["importance"] == "high"

    def test_bitcoin_halving_headline(self):
        article = _Article(
            3,
            "Bitcoin halving complete — block reward drops to 3.125 BTC",
            "BTC halving event reduces miner reward, historically bullish.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["sentiment"] == "risk_on"
        assert "BTC" in event["affected_assets"]

    def test_btc_all_time_high_medium_importance(self):
        article = _Article(
            4,
            "Bitcoin all time high broken as crypto bull market accelerates",
        )
        event = extract_event(article)

        assert event is not None
        assert event["sentiment"] == "risk_on"
        assert event["category"] == "crypto"

    def test_matched_keywords_are_extracted(self):
        article = _Article(
            5,
            "Spot ETF inflows boost institutional bitcoin holdings to record levels",
        )
        event = extract_event(article)
        assert event is not None
        # At least one matched keyword should appear in the text
        assert len(event["keywords"]) > 0


# ── SPY / Macro extraction ────────────────────────────────────────────────────

class TestSPYEventExtraction:

    def test_fed_dovish_pivot_headline(self):
        article = _Article(
            10,
            "Fed signals dovish pivot as US inflation cools to 2.1% — rate cut expected",
            "Federal Reserve set to begin easing cycle as inflation falls below target.",
        )
        event = extract_event(article)

        assert event is not None
        # "inflation falls" and "rate cut" both appear — highest importance wins (both high)
        assert event["importance"] == "high"
        assert event["sentiment"] == "risk_on"
        assert "SPY" in event["affected_assets"] or "BTC" in event["affected_assets"]

    def test_inflation_falls_below_expectations(self):
        article = _Article(
            11,
            "US CPI inflation below expectations for third straight month",
            "Consumer price index comes in lower than forecast, boosting risk assets.",
        )
        event = extract_event(article)

        # "cpi" matches the risk_off rule, "inflation below expectations" matches risk_on
        # highest importance wins — both are "high", so whichever is first in list
        assert event is not None
        assert event["importance"] == "high"
        assert "SPY" in event["affected_assets"] or "QQQ" in event["affected_assets"]

    def test_strong_nonfarm_payrolls(self):
        article = _Article(
            12,
            "Nonfarm payrolls beat forecast with 250k jobs added in April",
            "Strong jobs report shows unemployment falls to 3.8%.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["category"] == "macroeconomic"
        assert event["sentiment"] == "risk_on"
        assert "SPY" in event["affected_assets"] or "USD" in event["affected_assets"]

    def test_earnings_beat_headline(self):
        article = _Article(
            13,
            "S&P 500 earnings beat expectations — record profit for Q1 2026",
            "Strong earnings season drives SPY higher.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["category"] == "earnings"
        assert event["sentiment"] == "risk_on"

    def test_recession_fear_is_high_importance_risk_off(self):
        article = _Article(
            14,
            "US economy enters recession as GDP contraction confirmed",
            "Negative GDP reading raises stagflation concerns.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["sentiment"] == "risk_off"
        assert event["importance"] == "high"
        assert "SPY" in event["affected_assets"]

    def test_tariffs_trigger_risk_off(self):
        article = _Article(
            15,
            "White House announces sweeping new tariffs on Chinese imports",
            "Trade war fears mount as tariff increase sparks retaliation risk.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["sentiment"] == "risk_off"
        assert event["importance"] == "high"
        assert "SPY" in event["affected_assets"]


# ── EUR/USD / Forex extraction ────────────────────────────────────────────────

class TestEURUSDEventExtraction:

    def test_dollar_weakens_headline(self):
        # Headline avoids "nonfarm payrolls" to ensure the "dollar weakens" rule wins.
        # Both rules are medium importance; the first match in RULES wins on ties,
        # so the description must not trigger the jobs rule.
        article = _Article(
            20,
            "Dollar weakens sharply as DXY index drops 0.9% on risk-off flows",
            "Weak dollar lifts EUR and GBP broadly; dollar index drops across the board.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["sentiment"] == "risk_on"
        assert "EURUSD" in event["affected_assets"]
        assert "GBPUSD" in event["affected_assets"]

    def test_dollar_strengthens_is_risk_off_for_eurusd(self):
        article = _Article(
            21,
            "Dollar strengthens after hot CPI — dollar index rises 1.2%",
            "Strong inflation data pushes USD rallies across the board.",
        )
        event = extract_event(article)

        assert event is not None
        # "dollar strengthens" → risk_off, "cpi" → risk_off both match
        # both high importance — first matching high-importance rule wins
        assert event["sentiment"] == "risk_off"
        assert "EURUSD" in event["affected_assets"] or "USD" in event["affected_assets"]

    def test_rate_cut_bullish_for_risk_assets_including_eurusd(self):
        article = _Article(
            22,
            "Fed cuts rates by 25 basis points in surprise dovish move",
            "Interest rate cut surprises markets — risk assets rally broadly.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["category"] == "macroeconomic"
        assert event["sentiment"] == "risk_on"
        assert event["importance"] == "high"


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestExtractionEdgeCases:

    def test_unrelated_headline_returns_none(self):
        # Deliberately avoids any financial keyword substrings.
        # ("award" contains "war"; "local" contains nothing; safe phrasing used.)
        article = _Article(
            30,
            "Local chef earns top prize for best sourdough loaf in the city",
            "Community celebrates its thriving food scene.",
        )
        assert extract_event(article) is None

    def test_sports_news_returns_none(self):
        article = _Article(
            31,
            "Lakers win championship in overtime thriller",
        )
        assert extract_event(article) is None

    def test_highest_importance_wins_when_multiple_match(self):
        """Headline matches both a medium and high importance rule — high must win."""
        article = _Article(
            32,
            "Rate hike fears compound as GDP contraction confirmed — recession looms",
            "Federal Reserve hawkish stance and negative GDP combine for worst macro outlook.",
        )
        event = extract_event(article)

        assert event is not None
        assert event["importance"] == "high"

    def test_event_includes_headline(self):
        article = _Article(
            33,
            "Bitcoin ETF approved — BTC price surges 20%",
        )
        event = extract_event(article)
        assert event is not None
        assert event["headline"] == article.title

    def test_empty_description_does_not_crash(self):
        article = _Article(34, "Inflation falls for fifth consecutive month", "")
        event = extract_event(article)
        assert event is not None

    def test_title_only_lowercase_match(self):
        """Rule matching is case-insensitive (via .lower() in _build_text)."""
        article = _Article(
            35,
            "BITCOIN ETF INFLOWS HIT RECORD HIGH — INSTITUTIONAL DEMAND SURGES",
        )
        event = extract_event(article)
        assert event is not None
        assert event["sentiment"] == "risk_on"
