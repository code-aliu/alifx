from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.portfolio_intelligence.service import compute_portfolio_intelligence

router = APIRouter(prefix="/portfolio", tags=["Portfolio Intelligence"])


@router.get("/intelligence", response_model=ApiResponse)
def get_portfolio_intelligence(db: Session = Depends(get_db)):
    """Portfolio intelligence snapshot.

    Returns:
    - Concentration risk per asset (% of open notional)
    - Directional exposure (risk-on vs. risk-off balance)
    - Highly correlated position pairs (correlation ≥ 0.70)
    - Conflicting positions (correlated assets with opposing directions)
    - Automated risk warnings
    """
    result = compute_portfolio_intelligence(db)
    return ApiResponse(success=True, data=result)
