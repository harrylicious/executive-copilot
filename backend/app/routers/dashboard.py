"""Dashboard analytics router for aggregated KPI metrics."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardAnalytics
from app.services.dashboard_service import get_dashboard_analytics

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/analytics", response_model=DashboardAnalytics)
def dashboard_analytics(db: Session = Depends(get_db)):
    """Return aggregated dashboard analytics including KPIs, department distribution,
    query trends, and recent activities.
    """
    try:
        return get_dashboard_analytics(db)
    except Exception as e:
        logger.error("Failed to compute dashboard analytics: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Analytics could not be computed. Please try again later.",
        )
