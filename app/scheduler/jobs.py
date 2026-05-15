from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.database import SessionLocal
from app.core.logging import get_logger

logger = get_logger(__name__)


def _run_market_data_poll() -> None:
    from app.market_data.service import fetch_and_store_all
    db = SessionLocal()
    try:
        count = fetch_and_store_all(db)
        logger.info(f"Scheduler: market data poll complete — {count} bars stored")
    except Exception as e:
        logger.error(f"Scheduler: market data poll failed: {e}")
    finally:
        db.close()


def _run_news_poll() -> None:
    from app.news.service import fetch_and_store_all
    db = SessionLocal()
    try:
        count = fetch_and_store_all(db)
        logger.info(f"Scheduler: news poll complete — {count} new articles")
    except Exception as e:
        logger.error(f"Scheduler: news poll failed: {e}")
    finally:
        db.close()


def _run_event_pipeline() -> None:
    from app.events.service import process_unprocessed_articles
    db = SessionLocal()
    try:
        count = process_unprocessed_articles(db)
        logger.info(f"Scheduler: event pipeline complete — {count} events extracted")
    except Exception as e:
        logger.error(f"Scheduler: event pipeline failed: {e}")
    finally:
        db.close()


def _run_signal_pipeline() -> None:
    from app.signals.service import run_signal_pipeline
    db = SessionLocal()
    try:
        count = run_signal_pipeline(db)
        logger.info(f"Scheduler: signal pipeline complete — {count} signals generated")
    except Exception as e:
        logger.error(f"Scheduler: signal pipeline failed: {e}")
    finally:
        db.close()


def _run_paper_trading_cycle() -> None:
    from app.paper_trading.service import run_paper_trading_cycle
    db = SessionLocal()
    try:
        result = run_paper_trading_cycle(db)
        logger.info(f"Scheduler: paper trading cycle — {result}")
    except Exception as e:
        logger.error(f"Scheduler: paper trading cycle failed: {e}")
    finally:
        db.close()


def _run_outcome_resolution() -> None:
    from app.signal_tracking.service import resolve_active_outcomes
    db = SessionLocal()
    try:
        resolved = resolve_active_outcomes(db)
        if resolved:
            logger.info(f"Scheduler: resolved {resolved} signal outcomes")
    except Exception as e:
        logger.error(f"Scheduler: outcome resolution failed: {e}")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")

    scheduler.add_job(
        _run_market_data_poll,
        trigger=IntervalTrigger(seconds=settings.market_data_poll_interval),
        id="market_data_poll",
        name="Market Data Poll",
        replace_existing=True,
        max_instances=1,       # never run two at once
        misfire_grace_time=30,
    )

    scheduler.add_job(
        _run_news_poll,
        trigger=IntervalTrigger(seconds=settings.news_poll_interval),
        id="news_poll",
        name="News Poll",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _run_event_pipeline,
        trigger=IntervalTrigger(seconds=settings.pipeline_run_interval),
        id="event_pipeline",
        name="Event Extraction Pipeline",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _run_signal_pipeline,
        trigger=IntervalTrigger(seconds=settings.pipeline_run_interval),
        id="signal_pipeline",
        name="Signal Generation Pipeline",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _run_paper_trading_cycle,
        trigger=IntervalTrigger(seconds=settings.pipeline_run_interval),
        id="paper_trading",
        name="Paper Trading Cycle",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    scheduler.add_job(
        _run_outcome_resolution,
        trigger=IntervalTrigger(seconds=settings.pipeline_run_interval),
        id="outcome_resolution",
        name="Signal Outcome Resolution",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    return scheduler
