"""Public, prospect-facing demo API.

No authentication — the demo link is the credential. Every route is rate limited
and scoped to a single session id, and responses never include founder-only data
(ICP, qualification criteria, objection playbook).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.rate_limit import public_rate_limit
from app.schemas.demo import (
    AgentTurnOut,
    ContactRequest,
    DemoEventRequest,
    PublicDemoConfig,
    SendMessageRequest,
    StartSessionRequest,
    StartSessionResponse,
)
from app.services import demo_service

router = APIRouter(
    prefix="/demo",
    tags=["public-demo"],
    dependencies=[Depends(public_rate_limit)],
)


@router.get("/{slug}", response_model=PublicDemoConfig)
def get_demo(slug: str) -> PublicDemoConfig:
    _, config = demo_service.get_public_config(slug)
    return config


@router.post("/{slug}/sessions", response_model=StartSessionResponse, status_code=201)
async def start_session(slug: str, payload: StartSessionRequest) -> StartSessionResponse:
    session, config, opening = await demo_service.start_session(slug, payload)
    return StartSessionResponse(session_id=session["id"], config=config, opening=opening)


@router.post("/sessions/{session_id}/messages", response_model=AgentTurnOut)
async def send_message(session_id: str, payload: SendMessageRequest) -> AgentTurnOut:
    """REST turn. The WebSocket at /ws/demo/{session_id} is preferred for streaming;
    this is the fallback and behaves identically."""
    return await demo_service.handle_message(
        session_id, payload.message, payload.active_section
    )


@router.post("/sessions/{session_id}/events")
def track_event(session_id: str, payload: DemoEventRequest) -> dict:
    return demo_service.track_event(session_id, payload.event_type, payload.payload)


@router.post("/sessions/{session_id}/contact")
def submit_contact(session_id: str, payload: ContactRequest) -> dict:
    return demo_service.submit_contact(session_id, payload)


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str) -> dict:
    return await demo_service.end_session(session_id)
