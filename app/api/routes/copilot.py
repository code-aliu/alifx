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
from app.explanation.engine import enrich_context
from app.profiles.service import get_active_profile

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])

_VALID_LEVELS = {"beginner", "intermediate", "advanced"}


class AskRequest(BaseModel):
    question:   str      = Field(..., min_length=3, max_length=500)
    asset:      str | None = Field(default=None)
    user_level: str | None = Field(default=None, description="beginner | intermediate | advanced")


# ── /ask ─────────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=ApiResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    """Free-form natural language question about market conditions.

    Adapts language complexity and depth based on user_level
    (beginner / intermediate / advanced). Defaults to stored profile level.
    """
    # Resolve user level: request override → stored profile → default
    if body.user_level and body.user_level in _VALID_LEVELS:
        user_level = body.user_level
    else:
        profile    = get_active_profile(db)
        user_level = profile.get("mode", "intermediate")

    routing   = classify(body.question)
    intent    = routing["intent"]
    asset     = body.asset or routing["asset"]

    ctx       = retrieve_context(db, intent=intent, asset=asset)
    assembled = assemble(ctx)

    # Inject educational context for relevant intents/levels
    enriched, injected_concepts = enrich_context(
        assembled, body.question, user_level, intent
    )

    answer, by = generate_response(
        body.question, enriched, intent, asset,
        anthropic_key=settings.anthropic_api_key,
        openai_key=settings.openai_api_key,
        provider=settings.llm_provider,
        user_level=user_level,
    )

    return ApiResponse(
        success=True,
        data={
            "answer":              answer,
            "intent_detected":     intent,
            "asset_detected":      asset,
            "generated_by":        by,
            "explanation_level":   user_level,
            "education_injected":  injected_concepts,
            "context_used":        ctx,
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
    """Deep explanation for a specific signal: why it was generated, regime context."""
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
