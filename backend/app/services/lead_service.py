"""Founder-facing lead intelligence: the list, the detail view, the report."""

from __future__ import annotations

from app.ai_services.memory.conversation_memory import extract_questions
from app.core.errors import ForbiddenError, NotFoundError
from app.core.logging_config import get_logger
from app.database import get_db, utc_now
from app.models.qualification import LeadReport, LeadScore, QualificationData
from app.schemas.demo import DemoActionOut, SourceOut
from app.schemas.lead import LeadDetail, LeadListItem, OverviewStats, TranscriptMessage
from app.services.lead_scoring_service import recommended_action

log = get_logger("service.lead")

SESSIONS = "demo_sessions"
MESSAGES = "demo_messages"

QUALIFIED_THRESHOLD = 40
HIGH_INTENT_THRESHOLD = 70


def _product_map(founder_id: str) -> dict[str, dict]:
    rows = get_db().find("products", {"founder_id": founder_id})
    return {row["id"]: row for row in rows}


def _score_of(session: dict) -> LeadScore:
    data = session.get("lead_score") or {}
    return LeadScore(**data) if data else LeadScore()


def _qualification_of(session: dict) -> QualificationData:
    return QualificationData(**(session.get("qualification") or {}))


def _display_name(qualification: QualificationData, session: dict) -> str:
    if qualification.name:
        return qualification.name
    if qualification.company:
        return f"Visitor from {qualification.company}"
    return f"Anonymous visitor · {session['id'][:8]}"


def _to_list_item(session: dict, product: dict) -> LeadListItem:
    qualification = _qualification_of(session)
    score = _score_of(session)
    report = session.get("report") or {}

    action = report.get("recommended_action") or recommended_action(
        score, qualification, bool(session.get("contact_requested"))
    )

    return LeadListItem(
        session_id=session["id"],
        product_id=session["product_id"],
        product_name=product.get("name", ""),
        name=_display_name(qualification, session),
        email=qualification.email,
        company=qualification.company,
        industry=qualification.industry,
        job_title=qualification.job_title,
        score=score.score,
        classification=score.classification,
        pain_point=qualification.pain_point,
        message_count=int(session.get("message_count") or 0),
        contact_requested=bool(session.get("contact_requested")),
        status=session.get("status") or "active",
        started_at=session.get("started_at"),
        last_activity_at=session.get("last_activity_at"),
        recommended_action=action,
    )


# ---------------------------------------------------------------------------
# Lead list
# ---------------------------------------------------------------------------

def list_leads(
    founder_id: str,
    *,
    product_id: str | None = None,
    min_score: int | None = None,
    intent: str | None = None,
    only_engaged: bool = True,
    limit: int = 200,
) -> list[LeadListItem]:
    products = _product_map(founder_id)
    if not products:
        return []

    if product_id:
        if product_id not in products:
            raise ForbiddenError("You do not have access to this product.")
        product_ids = [product_id]
    else:
        product_ids = list(products)

    db = get_db()
    sessions: list[dict] = []
    for pid in product_ids:
        sessions.extend(
            db.find(SESSIONS, {"product_id": pid}, order_by="last_activity_at",
                    descending=True, limit=limit)
        )

    items: list[LeadListItem] = []
    for session in sessions:
        # A visitor who opened the link and left is noise on the lead list, but
        # still counted in analytics.
        if only_engaged and int(session.get("message_count") or 0) < 2:
            continue

        item = _to_list_item(session, products[session["product_id"]])
        if min_score is not None and item.score < min_score:
            continue
        if intent and item.classification.lower() != intent.lower():
            continue
        items.append(item)

    items.sort(key=lambda i: (i.score, i.last_activity_at or ""), reverse=True)
    return items[:limit]


# ---------------------------------------------------------------------------
# Lead detail
# ---------------------------------------------------------------------------

def get_lead(founder_id: str, session_id: str) -> LeadDetail:
    db = get_db()
    session = db.get(SESSIONS, session_id)
    if not session:
        raise NotFoundError("Lead not found.")

    product = db.get("products", session["product_id"])
    if not product or product.get("founder_id") != founder_id:
        raise ForbiddenError("You do not have access to this lead.")

    messages = db.find(MESSAGES, {"session_id": session_id}, order_by="turn_index")
    qualification = _qualification_of(session)
    prospect = db.get("prospects", session["prospect_id"]) if session.get("prospect_id") else None

    transcript: list[TranscriptMessage] = []
    features_viewed: list[str] = []
    objections: list[str] = []

    for message in messages:
        action = message.get("action") or None
        if action and action.get("type") in ("navigate", "highlight") and action.get("target"):
            if action["target"] not in features_viewed:
                features_viewed.append(action["target"])
        if message.get("intent") == "raise_objection":
            objections.append((message.get("content") or "")[:200])

        transcript.append(
            TranscriptMessage(
                id=message["id"],
                role=message["role"],
                content=message.get("content") or "",
                intent=message.get("intent"),
                stage=message.get("stage"),
                action=DemoActionOut(**action) if action else None,
                sources=[SourceOut(**s) for s in (message.get("sources") or [])],
                confidence=message.get("confidence"),
                created_at=message.get("created_at"),
            )
        )

    # Objections are attributed to the *prospect's* message, not the AI's reply.
    prospect_objections: list[str] = []
    for index, message in enumerate(messages):
        if message.get("intent") == "raise_objection" and index > 0:
            previous = messages[index - 1]
            if previous.get("role") == "user":
                prospect_objections.append((previous.get("content") or "")[:200])

    report_data = session.get("report") or None

    return LeadDetail(
        session_id=session_id,
        product_id=session["product_id"],
        product_name=product.get("name", ""),
        prospect=prospect or {},
        qualification=qualification,
        lead_score=_score_of(session),
        report=LeadReport(**report_data) if report_data else None,
        transcript=transcript,
        questions_asked=extract_questions(messages),
        objections_raised=prospect_objections or objections,
        sections_visited=list(session.get("sections_visited") or []),
        features_viewed=features_viewed,
        stage=session.get("stage") or "welcome",
        status=session.get("status") or "active",
        contact_requested=bool(session.get("contact_requested")),
        duration_seconds=int(session.get("duration_seconds") or 0),
        started_at=session.get("started_at"),
        last_activity_at=session.get("last_activity_at"),
    )


async def regenerate_report(founder_id: str, session_id: str) -> LeadReport:
    from app.services import demo_service, product_service
    from app.services.lead_scoring_service import calculate_lead_score

    db = get_db()
    session = db.get(SESSIONS, session_id)
    if not session:
        raise NotFoundError("Lead not found.")

    product = product_service.get_product(session["product_id"])
    if product.get("founder_id") != founder_id:
        raise ForbiddenError("You do not have access to this lead.")

    qualification = _qualification_of(session)
    transcript = db.find(MESSAGES, {"session_id": session_id}, order_by="turn_index")
    sections_visited = list(session.get("sections_visited") or [])
    contact_requested = bool(session.get("contact_requested"))

    score = calculate_lead_score(
        qualification,
        product,
        contact_requested=contact_requested,
        sections_visited=len(sections_visited),
        message_count=len(transcript),
    )
    report = await demo_service.generate_report(
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
            "lead_score": score.model_dump(),
            "report": report.model_dump(),
            "last_activity_at": utc_now(),
        },
    )
    return report


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

def overview(founder_id: str, product_id: str | None = None) -> OverviewStats:
    products = _product_map(founder_id)
    if not products:
        return OverviewStats()

    if product_id:
        if product_id not in products:
            raise ForbiddenError("You do not have access to this product.")
        scoped = {product_id: products[product_id]}
    else:
        scoped = products

    db = get_db()
    sessions: list[dict] = []
    for pid in scoped:
        sessions.extend(db.find(SESSIONS, {"product_id": pid}))

    engaged = [s for s in sessions if int(s.get("message_count") or 0) >= 2]
    scores = [_score_of(s).score for s in engaged]

    qualified = sum(1 for s in scores if s >= QUALIFIED_THRESHOLD)
    high_intent = sum(1 for s in scores if s >= HIGH_INTENT_THRESHOLD)
    contact_requests = sum(1 for s in sessions if s.get("contact_requested"))

    prospects = sum(db.count("prospects", {"product_id": pid}) for pid in scoped)
    durations = [int(s.get("duration_seconds") or 0) for s in engaged]

    recent = sorted(
        engaged, key=lambda s: s.get("last_activity_at") or "", reverse=True
    )[:5]

    return OverviewStats(
        total_prospects=prospects,
        total_sessions=len(sessions),
        qualified_leads=qualified,
        high_intent_leads=high_intent,
        contact_requests=contact_requests,
        conversion_rate=round(contact_requests / len(sessions) * 100, 1) if sessions else 0.0,
        average_score=round(sum(scores) / len(scores), 1) if scores else 0.0,
        average_duration_seconds=int(sum(durations) / len(durations)) if durations else 0,
        products=len(products),
        published_products=sum(1 for p in products.values() if p.get("is_published")),
        recent_leads=[_to_list_item(s, products[s["product_id"]]) for s in recent],
    )
