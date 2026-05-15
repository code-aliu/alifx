from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.reasoning.service import (
    run_test_scenario,
    get_reasoning_audit,
    validate_reasoning_from_headline,
)
from app.reasoning.scenarios import list_scenarios

router = APIRouter(prefix="/reasoning", tags=["Reasoning"])


@router.get("/test-scenarios", response_model=ApiResponse)
def get_all_scenarios():
    """List all available historical test scenarios."""
    scenarios = list_scenarios()
    return ApiResponse(success=True, data={"scenarios": scenarios, "total": len(scenarios)})


@router.get("/test-scenarios/{scenario_id}", response_model=ApiResponse)
def run_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """Run a specific scenario end-to-end and return extraction + validation scores."""
    result = run_test_scenario(scenario_id, db)
    if result.get("error") == "scenario_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. "
                   f"Use GET /reasoning/test-scenarios for the full list.",
        )
    return ApiResponse(success=True, data=result)


class ValidateReasoningRequest(BaseModel):
    headline: str
    description: str = ""
    asset: str | None = None
    scenario_id: str | None = None


@router.post("/validate-reasoning", response_model=ApiResponse)
def validate_reasoning(body: ValidateReasoningRequest, db: Session = Depends(get_db)):
    """Validate reasoning quality for an ad-hoc headline.

    Optionally pass `scenario_id` to compare extracted event against known
    expected values, or `asset` to get asset-specific impact details.
    """
    result = validate_reasoning_from_headline(
        headline=body.headline,
        db=db,
        description=body.description,
        asset=body.asset,
        scenario_id=body.scenario_id,
    )
    return ApiResponse(success=True, data=result)


@router.get("/reasoning-audit/{signal_id}", response_model=ApiResponse)
def get_audit(signal_id: int, db: Session = Depends(get_db)):
    """Full reasoning audit for a stored signal.

    Returns:
    - Reasoning chain parsed into structured layers (event, TA, regime, conflict)
    - Step-by-step confidence journey from baseline to final value
    - Quality metrics: consistency, calibration, TA alignment, stale detection
    """
    result = get_reasoning_audit(signal_id, db)
    if result.get("error") == "signal_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Signal {signal_id} not found.",
        )
    return ApiResponse(success=True, data=result)
