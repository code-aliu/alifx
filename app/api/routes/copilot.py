from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.config import settings
from app.copilot.router import classify
from app.copilot.retriever import retrieve_context
from app.copilot.assembler import assemble
from app.copilot.generator import generate_response
from app.copilot import narrative as narr

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    asset: str | None = Field(default=None, description="Optional asset hint (BTC, SPY, EURUSD…)")


# ── /ask ─────────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=ApiResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    """Free-form natural language question about market conditions.

    Examples:
    - Why is BTC bearish today?
    - What macro events are affecting markets?
    - What risks exist in the current portfolio?
    - Which signals have highest confidence?
    """
    routing    = classify(body.question)
    intent     = routing["intent"]
    asset      = body.asset or routing["asset"]

    ctx        = retrieve_context(db, intent=intent, asset=asset)
    assembled  = assemble(ctx)
    answer, by = generate_response(
        body.question, assembled, intent, asset,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
    )

    return ApiResponse(
        success=True,
        data={
            "answer":         answer,
            "intent_detected":intent,
            "asset_detected": asset,
            "generated_by":   by,
            "context_used":   ctx,
        },
    )


# ── /market-summary ───────────────────────────────────────────────────────────

@router.get("/market-summary", response_model=ApiResponse)
def market_summary(db: Session = Depends(get_db)):
    """Full daily market narrative: regime, signals, macro events, portfolio, performance."""
    result = narr.daily_market_summary(
        db,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
    )
    return ApiResponse(success=True, data=result)


# ── /top-signals ──────────────────────────────────────────────────────────────

@router.get("/top-signals", response_model=ApiResponse)
def top_signals(limit: int = 5, db: Session = Depends(get_db)):
    """Highest-confidence BUY/SELL signals with brief AI explanation of each."""
    result = narr.top_signals_report(
        db, limit=limit,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
    )
    return ApiResponse(success=True, data=result)


# ── /signal-explanation/{signal_id} ──────────────────────────────────────────

@router.get("/signal-explanation/{signal_id}", response_model=ApiResponse)
def signal_explanation(signal_id: int, db: Session = Depends(get_db)):
    """Deep explanation for a specific signal: why it was generated, what confirmed it, regime context."""
    result = narr.signal_explanation(
        db, signal_id,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
    )
    if result.get("error") == "signal_not_found":
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return ApiResponse(success=True, data=result)


# ── /portfolio-risk-summary ───────────────────────────────────────────────────

@router.get("/portfolio-risk-summary", response_model=ApiResponse)
def portfolio_risk_summary(db: Session = Depends(get_db)):
    """Narrative risk report: exposure, concentration, correlated pairs, warnings."""
    result = narr.portfolio_risk_summary(
        db,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
    )
    return ApiResponse(success=True, data=result)
