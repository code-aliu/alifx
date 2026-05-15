from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.logging import setup_logging, get_logger
from app.database import engine, Base
from app.scheduler.jobs import create_scheduler
from app.api.routes import (
    health, market_data, events, signals, analysis,
    paper_trading, technical_analysis, paper_trading_aliases, regime,
    market_intel, explainability,
)

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("AliFx starting up...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started — market data, news, and event pipeline are running")

    # Run an initial fetch immediately on startup so the DB isn't empty
    from app.database import SessionLocal
    from app.market_data.service import fetch_and_store_all as fetch_prices
    from app.news.service import fetch_and_store_all as fetch_news
    from app.events.service import process_unprocessed_articles
    from app.signals.service import run_signal_pipeline

    db = SessionLocal()
    try:
        logger.info("Running initial market data fetch...")
        fetch_prices(db)
        logger.info("Running initial news fetch...")
        fetch_news(db)
        logger.info("Running initial event extraction...")
        process_unprocessed_articles(db)
        logger.info("Running initial signal generation...")
        run_signal_pipeline(db)
    except Exception as e:
        logger.error(f"Initial startup pipeline failed: {e}")
    finally:
        db.close()

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("AliFx shut down")


app = FastAPI(
    title="AliFx — AI Market Intelligence Platform",
    description="Real-time market intelligence, event extraction, and trading signal generation.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(market_data.router)
app.include_router(events.router)
app.include_router(signals.router)
app.include_router(analysis.router)
app.include_router(paper_trading.router)
app.include_router(technical_analysis.router)
app.include_router(paper_trading_aliases.router)
app.include_router(regime.router)
app.include_router(market_intel.router)
app.include_router(explainability.router)


@app.get("/", tags=["System"])
def root():
    return {
        "service": "AliFx Market Intelligence Platform",
        "version": "0.1.0",
        "phase": "1 — Foundation + Ingestion",
        "docs": "/docs",
    }
