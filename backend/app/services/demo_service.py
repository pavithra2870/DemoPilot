"""Demo session orchestration — the heart of the prospect experience.

Per prospect message this service:
  1. persists the message and records analytics
  2. asks the SalesEngineerAgent for a turn (stage → retrieval → LLM → validation)
  3. merges qualification data (regex + model extraction)
  4. recomputes the lead score deterministically
  5. persists everything and returns a fully-typed turn to the UI

Written so both the REST route and the WebSocket route call the same code — the
transport differs, the behaviour cannot drift.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.ai_services.agents import LeadReportAgent, QualificationAgent, SalesEngineerAgent
from app.ai_services.state_machine import Stage, coerce_stage
from app.ai_services.structured_outputs.schemas import ActionType, AgentResponse
from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging_config import get_logger
from app.database import get_db, new_id, parse_ts, utc_now
from app.models.qualification import LeadReport, LeadScore, QualificationData
from app.schemas.demo import (
    AgentTurnOut,
    ContactRequest,
    DemoActionOut,
    PublicDemoConfig,
    PublicPricingPlan,
    SourceOut,
    StartSessionRequest,
)
from app.services import product_service
from app.services.lead_scoring_service import calculate_lead_score

log = get_logger("service.demo")

SESSIONS = "demo_sessions"
MESSAGES = "demo_messages"
EVENTS = "demo_events"
PROSPECTS = "prospects"

_sales_agent = SalesEngineerAgent()
_qualification_agent = QualificationAgent()
_report_agent = LeadReportAgent()


# ---------------------------------------------------------------------------
# Public demo config
# ---------------------------------------------------------------------------

def get_public_config(slug: str) -> tuple[dict, PublicDemoConfig]:
    product = product_service.get_product_by_slug(slug)
    if not product:
        raise NotFoundError("This demo link is not valid.")
    if not product.get("is_published"):
        raise ForbiddenError("This demo has not been published yet.")

    sections = product_service.list_sections(product["id"])
    pricing = product.get("pricing") or {}

    config = PublicDemoConfig(
        product_id=product["id"],
        slug=product["slug"],
        name=product["name"],
        tagline=product.get("tagline") or "",
        description=product.get("description") or "",
        category=product.get("category") or "",
        main_problem=product.get("main_problem") or "",
        main_benefits=product.get("main_benefits") or [],
        pricing_model=pricing.get("model") or "",
        pricing_currency=pricing.get("currency") or "USD",
        pricing_plans=[PublicPricingPlan(**p) for p in (pricing.get("plans") or [])],
        free_trial=pricing.get("free_trial") or "",
        pricing_notes=pricing.get("notes") or "",
        integrations=product.get("integrations") or [],
        faqs=product.get("faqs") or [],
        security_info=product.get("security_info") or "",
        sections=sections,
        cta=product.get("cta") or {},
        welcome_message=product.get("welcome_message") or "",
    )
    return product, config


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def get_session(session_id: str) -> dict:
    row = get_db().get(SESSIONS, session_id)
    if not row:
        raise NotFoundError("Demo session not found or expired.")
    return row


def _qualification_of(session: dict) -> QualificationData:
    return QualificationData(**(session.get("qualification") or {}))


def _lead_score_of(session: dict) -> LeadScore:
    data = session.get("lead_score") or {}
    return LeadScore(**data) if data else LeadScore()


def get_transcript(session_id: str) -> list[dict]:
    return get_db().find(MESSAGES, {"session_id": session_id}, order_by="turn_index")


async def start_session(slug: str, payload: StartSessionRequest) -> tuple[dict, PublicDemoConfig, AgentTurnOut]:
    product, config = get_public_config(slug)
    db = get_db()
    now = utc_now()

    prospect_id = None
    if payload.name or payload.email or payload.company:
        prospect_id = _upsert_prospect(
            product["id"],
            None,
            QualificationData(
                name=payload.name or None,
                email=payload.email or None,
                company=payload.company or None,
            ),
        )

    session = db.insert(
        SESSIONS,
        {
            "id": new_id(),
            "product_id": product["id"],
            "prospect_id": prospect_id,
            "stage": Stage.WELCOME.value,
            "status": "active",
            "qualification": {
                "name": payload.name or None,
                "email": payload.email or None,
                "company": payload.company or None,
            },
            "lead_score": {},
            "report": None,
            "summary": "",
            "sections_visited": [],
            "contact_requested": False,
            "message_count": 0,
            "duration_seconds": 0,
            "referrer": payload.referrer or "",
            "started_at": now,
            "last_activity_at": now,
            "ended_at": None,
        },
    )

    record_event(product["id"], session["id"], "session_started", {"referrer": payload.referrer})

    section_rows = product_service.list_section_rows(product["id"])
    turn = await _sales_agent.opening_turn(product=product, sections=section_rows)

    stored = _persist_assistant_turn(
        session=session,
        response=turn.response,
        stage=Stage.WELCOME,
        sources=[],
        turn_index=0,
    )

    qualification = _qualification_of(session)
    score = calculate_lead_score(qualification, product)
    db.update(
        SESSIONS,
        session["id"],
        {"lead_score": score.model_dump(), "message_count": 1, "last_activity_at": now},
    )

    out = _turn_out(
        message_id=stored["id"],
        session_id=session["id"],
        response=turn.response,
        stage=Stage.WELCOME,
        sources=[],
        qualification=qualification,
        score=score,
        contact_requested=False,
        degraded=turn.degraded,
    )
    return session, config, out


async def handle_message(
    session_id: str, message: str, active_section: str | None = None
) -> AgentTurnOut:
    db = get_db()
    session = get_session(session_id)

    if session.get("status") == "ended":
        raise ForbiddenError("This demo session has already ended.")

    product = product_service.get_product(session["product_id"])
    sections = product_service.list_section_rows(product["id"])
    transcript = get_transcript(session_id)
    qualification = _qualification_of(session)
    stage = coerce_stage(session.get("stage"))
    sections_visited = list(session.get("sections_visited") or [])

    # 1 — persist the prospect turn first, so nothing is lost if generation fails.
    turn_index = len(transcript)
    db.insert(
        MESSAGES,
        {
            "id": new_id(),
            "session_id": session_id,
            "product_id": product["id"],
            "role": "user",
            "content": message,
            "intent": None,
            "stage": stage.value,
            "action": None,
            "sources": None,
            "confidence": None,
            "turn_index": turn_index,
            "created_at": utc_now(),
        },
    )

    # 2 — generate
    turn = await _sales_agent.respond(
        product=product,
        sections=sections,
        transcript=transcript,
        qualification=qualification,
        current_stage=stage,
        prospect_message=message,
        active_section=active_section,
        sections_visited=sections_visited,
        conversation_summary=session.get("summary") or "",
    )
    response = turn.response

    # 3 — qualification
    qualification = _qualification_agent.update(
        qualification, response.qualification, message
    )

    # 4 — demo state driven by the action the AI issued
    if response.action.type == ActionType.NAVIGATE and response.action.target:
        if response.action.target not in sections_visited:
            sections_visited.append(response.action.target)
        record_event(product["id"], session_id, "section_view",
                     {"section": response.action.target, "source": "ai"})

    contact_requested = bool(session.get("contact_requested"))
    if response.action.type == ActionType.REQUEST_CONTACT:
        record_event(product["id"], session_id, "contact_prompted", {})

    record_event(
        product["id"], session_id, "message",
        {"intent": response.intent.value, "stage": turn.stage.value},
    )
    if response.intent.value == "raise_objection":
        record_event(product["id"], session_id, "objection_raised", {"text": message[:300]})
    elif response.intent.value in ("ask_question", "ask_pricing"):
        record_event(product["id"], session_id, "question_asked", {"text": message[:300]})

    # 5 — score
    score = calculate_lead_score(
        qualification,
        product,
        contact_requested=contact_requested,
        sections_visited=len(sections_visited),
        message_count=turn_index + 2,
    )

    stored = _persist_assistant_turn(
        session=session,
        response=response,
        stage=turn.stage,
        sources=[s.as_dict() for s in turn.sources],
        turn_index=turn_index + 1,
    )

    prospect_id = _upsert_prospect(product["id"], session.get("prospect_id"), qualification)

    db.update(
        SESSIONS,
        session_id,
        {
            "stage": turn.stage.value,
            "qualification": qualification.model_dump(),
            "lead_score": score.model_dump(),
            "summary": turn.summary or session.get("summary") or "",
            "sections_visited": sections_visited,
            "prospect_id": prospect_id,
            "message_count": turn_index + 2,
            "last_activity_at": utc_now(),
            "duration_seconds": _elapsed(session),
        },
    )

    return _turn_out(
        message_id=stored["id"],
        session_id=session_id,
        response=response,
        stage=turn.stage,
        sources=turn.sources,
        qualification=qualification,
        score=score,
        contact_requested=contact_requested,
        degraded=turn.degraded,
    )


def _persist_assistant_turn(
    *, session: dict, response: AgentResponse, stage: Stage,
    sources: list[dict], turn_index: int,
) -> dict:
    return get_db().insert(
        MESSAGES,
        {
            "id": new_id(),
            "session_id": session["id"],
            "product_id": session["product_id"],
            "role": "assistant",
            "content": response.message,
            "intent": response.intent.value,
            "stage": stage.value,
            "action": response.action.model_dump(mode="json"),
            "sources": sources,
            "confidence": response.confidence,
            "turn_index": turn_index,
            "created_at": utc_now(),
        },
    )


def _elapsed(session: dict) -> int:
    started = parse_ts(session.get("started_at"))
    if not started:
        return int(session.get("duration_seconds") or 0)
    return max(0, int((datetime.now(timezone.utc) - started).total_seconds()))


def _turn_out(
    *, message_id: str, session_id: str, response: AgentResponse, stage: Stage,
    sources, qualification: QualificationData, score: LeadScore,
    contact_requested: bool, degraded: bool = False,
) -> AgentTurnOut:
    source_list = []
    for source in sources or []:
        data = source if isinstance(source, dict) else source.as_dict()
        source_list.append(SourceOut(**data))

    return AgentTurnOut(
        message_id=message_id,
        session_id=session_id,
        message=response.message,
        intent=response.intent.value,
        stage=stage.value,
        action=DemoActionOut(**response.action.model_dump(mode="json")),
        sources=source_list,
        confidence=response.confidence,
        qualification=qualification,
        lead_score=score,
        suggested_replies=response.suggested_replies,
        contact_requested=contact_requested,
        degraded=degraded,
    )


# ---------------------------------------------------------------------------
# Prospects, events, contact capture
# ---------------------------------------------------------------------------

def _upsert_prospect(
    product_id: str, prospect_id: str | None, qualification: QualificationData
) -> str | None:
    """Prospect rows are created lazily — only once the AI has learned something
    identifying. An anonymous visitor stays a session, not a contact."""
    fields = {
        "name": qualification.name,
        "email": qualification.email,
        "company": qualification.company,
        "job_title": qualification.job_title,
        "industry": qualification.industry,
        "company_size": qualification.company_size,
    }
    known = {k: v for k, v in fields.items() if v}
    if not known:
        return prospect_id

    db = get_db()
    now = utc_now()

    if prospect_id:
        db.update(PROSPECTS, prospect_id, {**known, "updated_at": now})
        return prospect_id

    if qualification.email:
        existing = db.find_one(PROSPECTS, {"product_id": product_id, "email": qualification.email})
        if existing:
            db.update(PROSPECTS, existing["id"], {**known, "updated_at": now})
            return existing["id"]

    row = db.insert(
        PROSPECTS,
        {
            "id": new_id(),
            "product_id": product_id,
            **{k: known.get(k) for k in fields},
            "created_at": now,
            "updated_at": now,
        },
    )
    return row["id"]


def record_event(product_id: str, session_id: str | None, event_type: str,
                 payload: dict | None = None) -> None:
    try:
        get_db().insert(
            EVENTS,
            {
                "id": new_id(),
                "product_id": product_id,
                "session_id": session_id,
                "event_type": event_type,
                "payload": payload or {},
                "created_at": utc_now(),
            },
        )
    except Exception as exc:  # noqa: BLE001 - analytics must never break a demo
        log.warning("Could not record event %s: %s", event_type, exc)


def track_event(session_id: str, event_type: str, payload: dict) -> dict:
    """Public endpoint for UI-driven events (manual section clicks, CTA clicks)."""
    session = get_session(session_id)
    db = get_db()

    allowed = {
        "section_view", "cta_clicked", "faq_opened", "pricing_opened",
        "integration_opened", "highlight_viewed", "session_heartbeat",
    }
    if event_type not in allowed:
        return {"recorded": False, "reason": "unsupported_event"}

    if event_type == "section_view":
        section = payload.get("section")
        visited = list(session.get("sections_visited") or [])
        if section and section not in visited:
            visited.append(section)
            db.update(SESSIONS, session_id, {"sections_visited": visited})

    db.update(
        SESSIONS,
        session_id,
        {"last_activity_at": utc_now(), "duration_seconds": _elapsed(session)},
    )
    record_event(session["product_id"], session_id, event_type, payload)
    return {"recorded": True}


def submit_contact(session_id: str, payload: ContactRequest) -> dict:
    db = get_db()
    session = get_session(session_id)
    product = product_service.get_product(session["product_id"])

    qualification = _qualification_of(session).merge(
        QualificationData(
            name=payload.name or None,
            email=payload.email or None,
            company=payload.company or None,
            job_title=payload.job_title or None,
        )
    )

    prospect_id = _upsert_prospect(product["id"], session.get("prospect_id"), qualification)
    score = calculate_lead_score(
        qualification,
        product,
        contact_requested=True,
        sections_visited=len(session.get("sections_visited") or []),
        message_count=int(session.get("message_count") or 0),
    )

    db.update(
        SESSIONS,
        session_id,
        {
            "qualification": qualification.model_dump(),
            "lead_score": score.model_dump(),
            "prospect_id": prospect_id,
            "contact_requested": True,
            "last_activity_at": utc_now(),
            "duration_seconds": _elapsed(session),
        },
    )
    record_event(
        product["id"], session_id, "contact_submitted",
        {"cta_type": payload.cta_type, "note": payload.note[:300]},
    )

    log.info("Contact captured for session %s (score %d)", session_id, score.score)
    return {
        "submitted": True,
        "lead_score": score.model_dump(),
        "next_step": product.get("cta") or {},
    }


async def end_session(session_id: str) -> dict:
    db = get_db()
    session = get_session(session_id)
    product = product_service.get_product(session["product_id"])

    qualification = _qualification_of(session)
    transcript = get_transcript(session_id)
    sections_visited = list(session.get("sections_visited") or [])
    contact_requested = bool(session.get("contact_requested"))

    score = calculate_lead_score(
        qualification,
        product,
        contact_requested=contact_requested,
        sections_visited=len(sections_visited),
        message_count=len(transcript),
    )

    report = await generate_report(
        product=product,
        qualification=qualification,
        score=score,
        transcript=transcript,
        sections_visited=sections_visited,
        contact_requested=contact_requested,
    )

    db.update(
        SESSIONS,
        session_id,
        {
            "status": "ended",
            "stage": Stage.ENDED.value,
            "lead_score": score.model_dump(),
            "report": report.model_dump(),
            "ended_at": utc_now(),
            "last_activity_at": utc_now(),
            "duration_seconds": _elapsed(session),
        },
    )
    record_event(product["id"], session_id, "session_ended", {"score": score.score})

    return {
        "session_id": session_id,
        "lead_score": score.model_dump(),
        "next_step": product.get("cta") or {},
        "report": report.model_dump(),
    }


async def generate_report(
    *, product: dict, qualification: QualificationData, score: LeadScore,
    transcript: list[dict], sections_visited: list[str], contact_requested: bool,
) -> LeadReport:
    return await _report_agent.generate(
        product=product,
        qualification=qualification,
        lead_score=score,
        transcript=transcript,
        sections_visited=sections_visited,
        contact_requested=contact_requested,
    )
