from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.replay.engine import (
    run_scenario_replay,
    run_all_scenarios,
    list_replay_scenarios,
)

router = APIRouter(prefix="/historical-replay", tags=["Historical Replay"])


@router.get("/scenarios", response_model=ApiResponse)
def list_scenarios():
    """List all replayable historical event scenarios."""
    scenarios = list_replay_scenarios()
    return ApiResponse(
        success=True,
        data={"scenarios": scenarios, "total": len(scenarios)},
    )


@router.get("/run/{scenario_id}", response_model=ApiResponse)
def replay_scenario(scenario_id: str, db: Session = Depends(get_db)):
    """Replay a specific historical scenario.

    Extracts the event, generates signals for affected assets using current
    price data, simulates outcomes using recent bar movement, and returns a
    full replay report with directional accuracy analysis.
    """
    result = run_scenario_replay(scenario_id, db)
    if result.get("error") == "scenario_not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' not found. "
                   f"Use GET /historical-replay/scenarios for the full list.",
        )
    return ApiResponse(success=True, data=result)


@router.post("/run-all", response_model=ApiResponse)
def replay_all(db: Session = Depends(get_db)):
    """Run all 11 historical scenarios and return aggregate results.

    Shows extraction rate, directional accuracy across scenarios,
    and per-scenario signal generation results.
    """
    result = run_all_scenarios(db)
    return ApiResponse(success=True, data=result)
