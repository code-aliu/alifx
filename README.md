# AliFx — AI Market Intelligence Platform

Real-time market intelligence, event extraction, and trading signal generation.

## Phase 1 — Foundation + Ingestion

### Prerequisites

- Python 3.11+
- PostgreSQL (local)
- Redis (local)

### Setup

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your API keys and database URL

# 4. Create the database
createdb alifx                  # or use pgAdmin

# 5. Run migrations
alembic upgrade head

# 6. Start the server
uvicorn app.main:app --reload --port 8000
```

### API Endpoints (Phase 1)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | System health check |
| GET | `/market-data` | Latest prices for all tracked assets |
| GET | `/market-data/history/{symbol}` | Historical price bars |
| POST | `/market-data/refresh` | Manually trigger price fetch |
| GET | `/events` | Recent market events extracted from news |
| GET | `/events/asset/{asset}` | Events affecting a specific asset |
| GET | `/events/news` | Raw news articles |
| POST | `/events/process` | Manually trigger event extraction |
| GET | `/signals` | Trading signals (Phase 2) |
| GET | `/analysis` | Technical analysis (Phase 2) |
| GET | `/docs` | Interactive API docs (Swagger) |

### Tracked Assets

| Class | Assets |
|-------|--------|
| Crypto | BTC, ETH |
| Stocks | SPY, QQQ, NVDA, AAPL |
| Forex | EUR/USD, USD/JPY, GBP/USD |

### Polling Schedule

| Job | Interval | Description |
|-----|----------|-------------|
| Market Data | 2 min | Fetch prices from Binance, Yahoo, FxApi |
| News | 5 min | Fetch from NewsAPI + RSS feeds |
| Event Pipeline | 5 min | Extract events from unprocessed articles |

### Environment Variables

See `.env.example` for all configuration options.

Required:
- `DATABASE_URL` — PostgreSQL connection string
- `NEWSAPI_KEY` — from newsapi.org

Optional (enrichment):
- `OPENAI_API_KEY` — enables LLM event enrichment (non-blocking)
- `ALPHA_VANTAGE_KEY` — fallback stock data source

### Architecture

```
External APIs → Providers → Normalizer → PostgreSQL
                                       → Redis (hot cache)
                                       ↓
                             Event Extraction (rules)
                                       ↓ (optional)
                             LLM Enrichment (OpenAI)
                                       ↓
                              FastAPI Endpoints
```
