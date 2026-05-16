from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.schemas import ApiResponse
from app.evaluation import service as eval_service

router = APIRouter(prefix="/evaluation", tags=["Evaluation"])


@router.get("", response_model=ApiResponse)
def get_evaluation_summary(db: Session = Depends(get_db)):
    """Overall intelligence quality dashboard — fast, no benchmark run."""
    result = eval_service.get_evaluation_summary(db, run_benchmarks=False)
    return ApiResponse(success=True, data=result)


@router.get("/full", response_model=ApiResponse)
def get_full_evaluation(db: Session = Depends(get_db)):
    """Full evaluation including replay benchmarks (~2s)."""
    result = eval_service.get_evaluation_summary(db, run_benchmarks=True)
    return ApiResponse(success=True, data=result)


@router.get("/signal-utility", response_model=ApiResponse)
def get_signal_utility(db: Session = Depends(get_db)):
    """Signal utility metrics: false-positive rate, HOLD accuracy, calibration."""
    from app.evaluation.metrics import compute_signal_utility
    return ApiResponse(success=True, data=compute_signal_utility(db))


@router.get("/timing", response_model=ApiResponse)
def get_timing_quality(db: Session = Depends(get_db)):
    """Signal timing quality: early signal rate, stale rate, avg resolution hours."""
    from app.evaluation.timing import compute_timing_quality
    return ApiResponse(success=True, data=compute_timing_quality(db))


@router.get("/explainability", response_model=ApiResponse)
def get_explainability_scores(db: Session = Depends(get_db)):
    """Explainability scoring: coherence, actionability, conciseness, financial meaning."""
    from app.evaluation.explainability_scorer import compute_explainability_summary
    return ApiResponse(success=True, data=compute_explainability_summary(db))


@router.get("/benchmarks", response_model=ApiResponse)
def get_benchmarks(db: Session = Depends(get_db)):
    """Full replay benchmark suite across all 11 predefined market scenarios."""
    result = eval_service.get_reasoning_quality(db)
    return ApiResponse(success=True, data=result)
