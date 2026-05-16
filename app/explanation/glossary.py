"""
Financial concept glossary — two-level (beginner / advanced).

Beginner entries use plain English and real-world analogies.
Advanced entries use standard financial terminology without apology.
Intermediate gets the same as advanced but the system prompt softens delivery.
"""
from __future__ import annotations

# Each entry: {"beginner": str, "advanced": str}
GLOSSARY: dict[str, dict[str, str]] = {
    "inflation": {
        "beginner": (
            "Inflation means prices are rising across the economy — groceries, rent, fuel. "
            "When inflation is high, central banks raise interest rates to slow spending, "
            "which tends to lower stock prices because borrowing becomes more expensive."
        ),
        "advanced": (
            "Elevated CPI/PCE triggers hawkish monetary policy. Rate hikes compress equity "
            "multiples, strengthen USD, pressure duration-sensitive assets (tech, bonds), "
            "and typically reduce risk appetite for speculative assets like crypto."
        ),
    },
    "interest_rate": {
        "beginner": (
            "Interest rates are what banks charge to lend money. When the central bank raises "
            "rates, borrowing costs go up for companies and consumers, which usually slows "
            "economic growth and can push stock prices down."
        ),
        "advanced": (
            "Rate hike cycles increase the risk-free rate, raising the discount rate applied "
            "to future cash flows. This compresses P/E multiples, inverts the yield curve, "
            "and shifts capital from equities to fixed income."
        ),
    },
    "fed": {
        "beginner": (
            "The Federal Reserve (Fed) is the US central bank. It controls interest rates "
            "to keep inflation in check and employment healthy. When it raises rates, "
            "borrowing becomes pricier; when it cuts, borrowing gets cheaper."
        ),
        "advanced": (
            "The FOMC sets the federal funds rate target. Hawkish surprises strengthen USD, "
            "invert the curve, and reduce risk-asset valuations. Dovish pivots trigger "
            "risk-on rallies across equities, commodities, and crypto."
        ),
    },
    "fomc": {
        "beginner": (
            "FOMC stands for Federal Open Market Committee — the group within the US Federal "
            "Reserve that decides interest rates. Their meetings often move markets significantly "
            "because investors adjust expectations when rate decisions are announced."
        ),
        "advanced": (
            "FOMC meetings are binary risk events. Dot-plot projections, statement language, "
            "and Chair press conference tone drive rate expectations and repricing across "
            "rate-sensitive assets. Watch for hawkish/dovish pivots in guidance."
        ),
    },
    "yield_curve": {
        "beginner": (
            "The yield curve shows interest rates on government bonds of different lengths. "
            "Normally, longer bonds pay more. When short-term bonds pay more than long-term "
            "ones (inverted), it often signals the economy may slow down."
        ),
        "advanced": (
            "Yield curve inversion (2s10s or 3m10y spread negative) is a leading recession "
            "indicator. It signals market expectations of future rate cuts, compresses bank "
            "net interest margins, and favours defensive sectors and gold."
        ),
    },
    "risk_on": {
        "beginner": (
            "Risk-on means investors feel confident and are buying higher-risk assets — stocks, "
            "crypto, emerging markets. Think of it like people being optimistic about the "
            "economy and willing to take chances for bigger returns."
        ),
        "advanced": (
            "Risk-on environments are characterised by equity outperformance, spread "
            "compression, USD weakness, and capital flows into high-beta assets. "
            "Triggered by easing financial conditions or improving macro data."
        ),
    },
    "risk_off": {
        "beginner": (
            "Risk-off means investors are nervous and moving money from risky assets like "
            "stocks and crypto into safer ones like gold and government bonds. "
            "It happens when there is fear, uncertainty, or bad economic news."
        ),
        "advanced": (
            "Risk-off regimes see capital flight to safe havens (Treasuries, JPY, CHF, gold). "
            "Equities and crypto sell off, credit spreads widen, and USD typically strengthens. "
            "Triggered by geopolitical shocks, recession fears, or liquidity crises."
        ),
    },
    "volatility": {
        "beginner": (
            "Volatility means how much prices swing up and down. High volatility means big, "
            "unpredictable moves — more risk, but also more opportunity. Low volatility "
            "means steadier, calmer markets."
        ),
        "advanced": (
            "Implied volatility (VIX) reflects options market expectations. Rising vol "
            "compresses risk appetite, widens bid-ask spreads, and increases margin "
            "requirements. ATR measures realised volatility on individual assets."
        ),
    },
    "hawkish": {
        "beginner": (
            "Hawkish means the central bank is focused on fighting inflation — likely raising "
            "interest rates. This is usually bad for stocks and crypto in the short term "
            "because borrowing costs rise."
        ),
        "advanced": (
            "Hawkish stance signals tighter monetary conditions — rate hikes or "
            "balance sheet reduction (QT). Strengthens currency, compresses equity multiples, "
            "and favours defensive sectors and short-duration fixed income."
        ),
    },
    "dovish": {
        "beginner": (
            "Dovish means the central bank is focused on supporting growth — likely cutting "
            "rates or keeping them low. This is generally positive for stocks and crypto "
            "because money becomes cheaper to borrow."
        ),
        "advanced": (
            "Dovish pivot signals looser monetary conditions — rate cuts or QE. Typically "
            "triggers risk-on rallies, USD weakness, yield curve steepening, and "
            "outperformance of growth equities and crypto."
        ),
    },
    "cpi": {
        "beginner": (
            "CPI (Consumer Price Index) measures how much everyday goods cost. "
            "A higher CPI means prices are rising faster — inflation. "
            "Markets react because high CPI often means the Fed will raise rates."
        ),
        "advanced": (
            "CPI is the primary inflation benchmark. A hot print above consensus "
            "reinforces hawkish Fed expectations — USD rallies, yields rise, equities "
            "sell off. Core CPI (ex-food/energy) is more closely watched for policy signals."
        ),
    },
    "correlation": {
        "beginner": (
            "Correlation means how similar two assets move. If BTC and tech stocks both "
            "go up and down together, they are highly correlated. When everything in your "
            "portfolio moves the same way, you are less protected from losses."
        ),
        "advanced": (
            "High inter-asset correlation reduces portfolio diversification benefit. "
            "BTC/equities correlation has risen in high-rate environments. "
            "Monitor rolling 30-day correlation to identify diversification breakdown."
        ),
    },
    "drawdown": {
        "beginner": (
            "Drawdown is how much a portfolio has fallen from its highest value. "
            "A 20% drawdown means your portfolio dropped 20% from its peak. "
            "Smaller drawdowns mean the strategy protects capital better."
        ),
        "advanced": (
            "Max drawdown quantifies the worst peak-to-trough decline. Paired with "
            "Sharpe ratio, it measures risk-adjusted return quality. "
            "Higher drawdown with similar returns indicates inefficient risk-taking."
        ),
    },
    "rsi": {
        "beginner": (
            "RSI (Relative Strength Index) measures if an asset is being bought or sold "
            "too aggressively. Above 70 may mean it is overbought (due for a pullback); "
            "below 30 may mean it is oversold (potentially due for a bounce)."
        ),
        "advanced": (
            "RSI is a momentum oscillator (0–100). Readings above 70 signal overbought "
            "conditions; below 30 signal oversold. Divergences between RSI and price "
            "are stronger signals than absolute levels."
        ),
    },
    "macd": {
        "beginner": (
            "MACD is a technical indicator that shows whether buying or selling momentum "
            "is building. When the MACD line crosses above its signal line, it is often "
            "seen as a buy signal; crossing below can be a sell signal."
        ),
        "advanced": (
            "MACD (12/26/9) measures momentum via EMA differentials. Bullish crossovers "
            "above zero confirm uptrend continuation; bearish crossovers in negative "
            "territory confirm downtrend. Histogram divergence precedes crossovers."
        ),
    },
    "regime": {
        "beginner": (
            "Market regime describes the overall mood of the market — are investors "
            "feeling confident (risk-on) or cautious (risk-off)? Knowing the regime "
            "helps set expectations for how different assets might perform."
        ),
        "advanced": (
            "Regime classification (trend, volatility, event-flow components) sets the "
            "macro backdrop for signal generation. Risk-on regimes favour momentum; "
            "risk-off regimes favour defensive assets and cash preservation."
        ),
    },
    "liquidity": {
        "beginner": (
            "Liquidity means how easy it is to buy or sell an asset quickly without "
            "affecting its price. High liquidity = easy to trade. Low liquidity = "
            "big price swings even on small trades."
        ),
        "advanced": (
            "Market liquidity affects bid-ask spreads, slippage, and volatility. "
            "Illiquid markets amplify price moves in both directions. "
            "Central bank QE/QT cycles directly impact global liquidity conditions."
        ),
    },
}

# Concept triggers — keywords in the question that map to glossary keys
CONCEPT_TRIGGERS: dict[str, list[str]] = {
    "inflation":      ["inflation", "inflationary", "price rise", "price increase"],
    "interest_rate":  ["interest rate", "rate hike", "rate cut", "rate rise", "borrowing cost"],
    "fed":            ["fed", "federal reserve", "central bank"],
    "fomc":           ["fomc", "fed meeting", "rate decision", "dot plot"],
    "yield_curve":    ["yield curve", "2s10s", "inverted", "bond yield"],
    "risk_on":        ["risk-on", "risk on", "risk appetite", "bullish sentiment"],
    "risk_off":       ["risk-off", "risk off", "safe haven", "flight to safety"],
    "volatility":     ["volatility", "vix", "volatile", "vol spike"],
    "hawkish":        ["hawkish", "tightening", "quantitative tightening", "qt"],
    "dovish":         ["dovish", "easing", "quantitative easing", "qe", "rate cut"],
    "cpi":            ["cpi", "consumer price", "inflation data", "pce"],
    "correlation":    ["correlation", "correlated", "move together", "diversification"],
    "drawdown":       ["drawdown", "peak to trough", "capital loss", "max drawdown"],
    "rsi":            ["rsi", "relative strength", "overbought", "oversold"],
    "macd":           ["macd", "moving average convergence", "momentum indicator"],
    "regime":         ["regime", "market condition", "risk-on", "risk-off", "market environment"],
    "liquidity":      ["liquidity", "bid-ask", "illiquid", "market depth"],
}


def detect_concepts(question: str) -> list[str]:
    """Return glossary keys for concepts mentioned in the question."""
    lower = question.lower()
    found = []
    for concept, triggers in CONCEPT_TRIGGERS.items():
        if any(t in lower for t in triggers):
            found.append(concept)
    return found


def lookup(concept: str, user_level: str) -> str | None:
    """Return the appropriate explanation for a concept at the given user level."""
    entry = GLOSSARY.get(concept)
    if not entry:
        return None
    if user_level == "beginner":
        return entry["beginner"]
    return entry["advanced"]
