from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentFounder
from app.models.qualification import LeadReport
from app.schemas.lead import LeadDetail, LeadListItem, OverviewStats
from app.services import lead_service

router = APIRouter(tags=["leads"])


@router.get("/dashboard/overview", response_model=OverviewStats)
def overview(founder: CurrentFounder, product_id: str | None = None) -> OverviewStats:
    return lead_service.overview(founder["id"], product_id)


@router.get("/leads", response_model=list[LeadListItem])
def list_leads(
    founder: CurrentFounder,
    product_id: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    intent: str | None = None,
    include_bounced: bool = False,
) -> list[LeadListItem]:
    return lead_service.list_leads(
        founder["id"],
        product_id=product_id,
        min_score=min_score,
        intent=intent,
        only_engaged=not include_bounced,
    )


@router.get("/leads/{session_id}", response_model=LeadDetail)
def get_lead(session_id: str, founder: CurrentFounder) -> LeadDetail:
    return lead_service.get_lead(founder["id"], session_id)


@router.post("/leads/{session_id}/report", response_model=LeadReport)
async def regenerate_report(session_id: str, founder: CurrentFounder) -> LeadReport:
    """Generate (or refresh) the AI lead intelligence brief for this session."""
    return await lead_service.regenerate_report(founder["id"], session_id)
