"""
Rule-based event classification.

Each rule is a dict with:
  keywords     : list[str]  — any match triggers this rule
  category     : str        — macroeconomic | geopolitical | earnings | crypto | sector
  sentiment    : str        — risk_on | risk_off | neutral
  importance   : str        — high | medium | low
  affected_assets: list[str] — asset codes this event typically moves
"""

RULES: list[dict] = [
    # ── Inflation / CPI ───────────────────────────────────────────────────────
    {
        "keywords": ["cpi", "consumer price index", "inflation rises", "inflation higher",
                     "inflation above", "price surge", "hotter than expected inflation"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["USD", "BTC", "NASDAQ", "SPY", "QQQ", "GOLD"],
    },
    {
        "keywords": ["inflation falls", "inflation cools", "deflation", "disinflation",
                     "lower cpi", "price decline", "inflation below expectations"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "high",
        "affected_assets": ["BTC", "NASDAQ", "SPY", "QQQ", "ETH"],
    },

    # ── Federal Reserve / Interest Rates ─────────────────────────────────────
    {
        "keywords": ["rate hike", "interest rate increase", "fed raises", "hawkish fed",
                     "tightening", "fed hikes", "50 basis points", "25 basis points hike"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["USD", "BTC", "ETH", "NASDAQ", "QQQ", "GOLD"],
    },
    {
        "keywords": ["rate cut", "interest rate cut", "fed cuts", "dovish fed", "rate reduction",
                     "easing", "pivot", "fed pivot", "lower rates", "cutting rates"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "high",
        "affected_assets": ["BTC", "ETH", "NASDAQ", "SPY", "QQQ", "GOLD"],
    },
    {
        "keywords": ["fed holds", "rates unchanged", "fed pause", "hold steady",
                     "no rate change", "pause rate"],
        "category": "macroeconomic",
        "sentiment": "neutral",
        "importance": "medium",
        "affected_assets": ["USD", "SPY", "QQQ"],
    },

    # ── GDP / Growth ──────────────────────────────────────────────────────────
    {
        "keywords": ["gdp growth", "economy grows", "strong gdp", "gdp beats",
                     "expansion", "economic growth"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["USD", "SPY", "QQQ", "NASDAQ"],
    },
    {
        "keywords": ["recession", "gdp contraction", "gdp shrinks", "economic slowdown",
                     "recessionary", "negative gdp", "stagflation"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["SPY", "QQQ", "BTC", "ETH", "NASDAQ"],
    },

    # ── Jobs / Employment ─────────────────────────────────────────────────────
    {
        "keywords": ["nonfarm payrolls", "jobs report", "unemployment falls", "strong jobs",
                     "payrolls beat", "low unemployment", "employment growth"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["USD", "SPY", "QQQ"],
    },
    {
        "keywords": ["jobless claims rise", "unemployment rises", "layoffs", "job cuts",
                     "mass layoffs", "hiring freeze", "unemployment surges"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "medium",
        "affected_assets": ["SPY", "QQQ", "USD"],
    },

    # ── Crypto-specific ───────────────────────────────────────────────────────
    {
        "keywords": ["bitcoin etf", "btc etf", "crypto etf approved", "spot etf",
                     "etf inflows", "institutional bitcoin", "blackrock bitcoin"],
        "category": "crypto",
        "sentiment": "risk_on",
        "importance": "high",
        "affected_assets": ["BTC", "ETH"],
    },
    {
        "keywords": ["crypto ban", "bitcoin ban", "crypto regulation crackdown",
                     "sec sues", "crypto lawsuit", "exchange hack", "crypto hack",
                     "exchange collapse", "ftx", "exchange insolvent"],
        "category": "crypto",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["BTC", "ETH"],
    },
    {
        "keywords": ["bitcoin halving", "btc halving", "block reward halving"],
        "category": "crypto",
        "sentiment": "risk_on",
        "importance": "high",
        "affected_assets": ["BTC", "ETH"],
    },
    {
        "keywords": ["crypto rally", "bitcoin surges", "btc breaks", "ath bitcoin",
                     "bitcoin all time high", "crypto bull"],
        "category": "crypto",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["BTC", "ETH"],
    },

    # ── Geopolitical ──────────────────────────────────────────────────────────
    {
        "keywords": ["war", "conflict", "sanctions", "military strike", "invasion",
                     "escalation", "geopolitical tension", "nuclear", "missile"],
        "category": "geopolitical",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["GOLD", "USD", "OIL", "BTC", "SPY"],
    },
    {
        "keywords": ["ceasefire", "peace deal", "de-escalation", "trade agreement",
                     "tariff removal", "trade deal signed"],
        "category": "geopolitical",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["SPY", "QQQ", "NASDAQ"],
    },

    # ── Tariffs / Trade ───────────────────────────────────────────────────────
    {
        "keywords": ["tariffs", "trade war", "import duties", "protectionism",
                     "trade barriers", "tariff increase", "new tariffs"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "high",
        "affected_assets": ["SPY", "QQQ", "NASDAQ", "AAPL", "NVDA"],
    },

    # ── Tech / Earnings ───────────────────────────────────────────────────────
    {
        "keywords": ["earnings beat", "profit beat", "revenue beat", "better than expected earnings",
                     "strong earnings", "record profit"],
        "category": "earnings",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["SPY", "QQQ", "NASDAQ", "NVDA", "AAPL"],
    },
    {
        "keywords": ["earnings miss", "profit miss", "revenue miss", "below expectations",
                     "earnings warning", "guidance cut", "profit warning"],
        "category": "earnings",
        "sentiment": "risk_off",
        "importance": "medium",
        "affected_assets": ["SPY", "QQQ", "NASDAQ", "NVDA", "AAPL"],
    },
    {
        "keywords": ["nvidia", "nvda", "ai chip", "gpu demand", "ai earnings"],
        "category": "sector",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["NVDA", "NASDAQ", "QQQ"],
    },
    {
        "keywords": ["apple", "aapl", "iphone sales", "apple revenue", "app store"],
        "category": "sector",
        "sentiment": "neutral",
        "importance": "low",
        "affected_assets": ["AAPL", "SPY", "QQQ"],
    },

    # ── Oil / Commodities ─────────────────────────────────────────────────────
    {
        "keywords": ["oil supply cut", "opec cuts", "oil production cut", "crude rally",
                     "oil prices rise", "energy crisis"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "medium",
        "affected_assets": ["OIL", "USD", "SPY"],
    },
    {
        "keywords": ["oil oversupply", "opec increases production", "oil prices fall",
                     "crude drops", "oil glut"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "low",
        "affected_assets": ["OIL", "SPY"],
    },

    # ── USD / Dollar ──────────────────────────────────────────────────────────
    {
        "keywords": ["dollar strengthens", "usd rallies", "strong dollar",
                     "dollar index rises", "dxy up"],
        "category": "macroeconomic",
        "sentiment": "risk_off",
        "importance": "medium",
        "affected_assets": ["BTC", "GOLD", "EURUSD", "GBPUSD"],
    },
    {
        "keywords": ["dollar weakens", "usd falls", "weak dollar",
                     "dollar index drops", "dxy down"],
        "category": "macroeconomic",
        "sentiment": "risk_on",
        "importance": "medium",
        "affected_assets": ["BTC", "ETH", "GOLD", "EURUSD", "GBPUSD"],
    },
]
