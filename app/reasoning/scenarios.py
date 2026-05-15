"""
Historical reasoning test scenarios.

Each scenario pairs a realistic market headline with the expected extraction
and reasoning outcomes, allowing the validation framework to score how well
the pipeline handles each event type.

11 scenarios spanning: CPI, Fed decisions, BTC ETF, earnings, geopolitical,
and oil market events.
"""

SCENARIOS: list[dict] = [
    # ── Inflation / CPI ───────────────────────────────────────────────────────
    {
        "id": "cpi_hot",
        "name": "Hot CPI — Inflation Surprise",
        "event_type": "macroeconomic",
        "description": "CPI print comes in above expectations, signalling persistent inflation.",
        "headline": "US CPI report shows inflation running hotter than expected — price pressures mount",
        "expected": {
            "event_sentiment":  "risk_off",
            "event_importance": "high",
            "event_category":   "macroeconomic",
            "directional_bias": "bearish",
            "affected_assets":  ["USD", "BTC", "NASDAQ", "SPY", "QQQ", "GOLD"],
            "reasoning_keywords": ["bearish", "impact score"],
            "regime_signal":      "risk_off",
            "confidence_direction": "down",
        },
    },
    {
        "id": "cpi_cool",
        "name": "Cool CPI — Disinflation",
        "event_type": "macroeconomic",
        "description": "CPI print comes in below expectations, signalling cooling inflation.",
        "headline": "Inflation falls sharply below Fed's 2% target — disinflation trend accelerates",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "high",
            "event_category":   "macroeconomic",
            "directional_bias": "bullish",
            "affected_assets":  ["BTC", "NASDAQ", "SPY", "QQQ", "ETH"],
            "reasoning_keywords": ["bullish", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },

    # ── Federal Reserve ───────────────────────────────────────────────────────
    {
        "id": "fed_hike",
        "name": "Fed Rate Hike",
        "event_type": "macroeconomic",
        "description": "Federal Reserve raises interest rates, tightening monetary policy.",
        "headline": "Fed raises interest rates — hawkish Fed stance signals continued tightening",
        "expected": {
            "event_sentiment":  "risk_off",
            "event_importance": "high",
            "event_category":   "macroeconomic",
            "directional_bias": "bearish",
            "affected_assets":  ["USD", "BTC", "ETH", "NASDAQ", "QQQ", "GOLD"],
            "reasoning_keywords": ["bearish", "impact score"],
            "regime_signal":      "risk_off",
            "confidence_direction": "down",
        },
    },
    {
        "id": "fed_cut",
        "name": "Fed Rate Cut",
        "event_type": "macroeconomic",
        "description": "Federal Reserve cuts interest rates, easing monetary policy.",
        "headline": "Federal Reserve signals rate cut — dovish Fed pivot expected at next meeting",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "high",
            "event_category":   "macroeconomic",
            "directional_bias": "bullish",
            "affected_assets":  ["BTC", "ETH", "NASDAQ", "SPY", "QQQ", "GOLD"],
            "reasoning_keywords": ["bullish", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },

    # ── Crypto ────────────────────────────────────────────────────────────────
    {
        "id": "btc_etf",
        "name": "Bitcoin ETF Approval",
        "event_type": "crypto",
        "description": "Spot Bitcoin ETF approved by regulators, enabling institutional inflows.",
        "headline": "Bitcoin ETF approved by regulators — institutional bitcoin demand expected to surge",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "high",
            "event_category":   "crypto",
            "directional_bias": "bullish",
            "affected_assets":  ["BTC", "ETH"],
            "reasoning_keywords": ["bullish", "etf", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },

    # ── Earnings ──────────────────────────────────────────────────────────────
    {
        "id": "earnings_beat",
        "name": "Tech Earnings Beat",
        "event_type": "earnings",
        "description": "Technology sector reports strong earnings, beating consensus estimates.",
        "headline": "Tech giants deliver strong earnings — profit beat boosts market sentiment",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "medium",
            "event_category":   "earnings",
            "directional_bias": "bullish",
            "affected_assets":  ["SPY", "QQQ", "NASDAQ", "NVDA", "AAPL"],
            "reasoning_keywords": ["bullish", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },
    {
        "id": "earnings_miss",
        "name": "Tech Earnings Miss",
        "event_type": "earnings",
        "description": "Technology sector misses earnings estimates and cuts forward guidance.",
        "headline": "Tech sector misses earnings estimates — guidance cut raises investor alarm",
        "expected": {
            "event_sentiment":  "risk_off",
            "event_importance": "medium",
            "event_category":   "earnings",
            "directional_bias": "bearish",
            "affected_assets":  ["SPY", "QQQ", "NASDAQ", "NVDA", "AAPL"],
            "reasoning_keywords": ["bearish", "impact score"],
            "regime_signal":      "risk_off",
            "confidence_direction": "down",
        },
    },

    # ── Geopolitical ──────────────────────────────────────────────────────────
    {
        "id": "geo_escalation",
        "name": "Geopolitical Escalation",
        "event_type": "geopolitical",
        "description": "Military conflict escalates, driving risk-off flows into safe-haven assets.",
        "headline": "Geopolitical escalation intensifies — military conflict fears grip global markets",
        "expected": {
            "event_sentiment":  "risk_off",
            "event_importance": "high",
            "event_category":   "geopolitical",
            "directional_bias": "bearish",
            "affected_assets":  ["GOLD", "USD", "OIL", "BTC", "SPY"],
            "reasoning_keywords": ["bearish", "impact score"],
            "regime_signal":      "risk_off",
            "confidence_direction": "down",
        },
    },
    {
        "id": "geo_ceasefire",
        "name": "Geopolitical Ceasefire",
        "event_type": "geopolitical",
        "description": "Ceasefire agreement reduces geopolitical risk, boosting risk appetite.",
        "headline": "Historic ceasefire agreement signed — peace deal brings calm to global markets",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "medium",
            "event_category":   "geopolitical",
            "directional_bias": "bullish",
            "affected_assets":  ["SPY", "QQQ", "NASDAQ"],
            "reasoning_keywords": ["bullish", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },

    # ── Oil / Commodities ─────────────────────────────────────────────────────
    {
        "id": "oil_supply_cut",
        "name": "OPEC Oil Supply Cut",
        "event_type": "macroeconomic",
        "description": "OPEC announces production cuts, tightening oil supply and raising energy prices.",
        "headline": "OPEC cuts oil production by 1.5 million barrels — energy supply tightens",
        "expected": {
            "event_sentiment":  "risk_off",
            "event_importance": "medium",
            "event_category":   "macroeconomic",
            "directional_bias": "bearish",
            "affected_assets":  ["OIL", "USD", "SPY"],
            "reasoning_keywords": ["bearish", "impact score"],
            "regime_signal":      "risk_off",
            "confidence_direction": "down",
        },
    },
    {
        "id": "oil_oversupply",
        "name": "Oil Oversupply",
        "event_type": "macroeconomic",
        "description": "Oil glut persists as production outpaces demand, pushing prices lower.",
        "headline": "Global oil glut deepens — crude prices drop on rising production",
        "expected": {
            "event_sentiment":  "risk_on",
            "event_importance": "low",
            "event_category":   "macroeconomic",
            "directional_bias": "bullish",
            "affected_assets":  ["OIL", "SPY"],
            "reasoning_keywords": ["bullish", "impact score"],
            "regime_signal":      "risk_on",
            "confidence_direction": "up",
        },
    },
]

# O(1) lookup by id
SCENARIO_INDEX: dict[str, dict] = {s["id"]: s for s in SCENARIOS}


def get_scenario(scenario_id: str) -> dict | None:
    return SCENARIO_INDEX.get(scenario_id)


def list_scenarios() -> list[dict]:
    """Return scenario metadata only (no expected internals) for public listing."""
    return [
        {
            "id":          s["id"],
            "name":        s["name"],
            "event_type":  s["event_type"],
            "description": s["description"],
            "headline":    s["headline"],
        }
        for s in SCENARIOS
    ]
