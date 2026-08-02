from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentFounder
from app.schemas.lead import AnalyticsOut
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("", response_model=AnalyticsOut)
def analytics(founder: CurrentFounder, product_id: str | None = None) -> AnalyticsOut:
    return analytics_service.build_analytics(founder["id"], product_id)
