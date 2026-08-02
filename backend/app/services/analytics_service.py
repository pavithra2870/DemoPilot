"""Demo analytics — what prospects actually care about.

Computed from the `demo_events` stream plus session rows. Aggregation happens in
Python because the volumes are small and it keeps the two storage backends
identical; if a founder ever outgrows that, this is the one module to move into
SQL views.
"""

from __future__ import annotations

import re
from collections import Counter

from app.core.errors import ForbiddenError
from app.database import get_db, parse_ts
from app.schemas.lead import AnalyticsOut, CountItem

EVENTS = "demo_events"
SESSIONS = "demo_sessions"
MESSAGES = "demo_messages"

_STOPWORDS = frozenset(
    """what how why when where who is are do does can could would will the a an
    of to for with your our this that it i we you my me and or if there any""".split()
)


def _scoped_products(founder_id: str, product_id: str | None) -> dict[str, dict]:
    products = {p["id"]: p for p in get_db().find("products", {"founder_id": founder_id})}
    if product_id:
        if product_id not in products:
            raise ForbiddenError("You do not have access to this product.")
        return {product_id: products[product_id]}
    return products


def _question_key(text: str) -> str:
    """Group near-identical questions so the top-questions list is not 40 rows of
    the same thing worded differently."""
    words = [
        w for w in re.findall(r"[a-z']+", (text or "").lower())
        if w not in _STOPWORDS and len(w) > 2
    ]
    return " ".join(sorted(set(words))[:5])


def _top_grouped(texts: list[str], limit: int = 10) -> list[CountItem]:
    groups: dict[str, list[str]] = {}
    for text in texts:
        key = _question_key(text)
        if key:
            groups.setdefault(key, []).append(text.strip())

    ranked = sorted(groups.values(), key=len, reverse=True)[:limit]
    return [
        CountItem(
            label=max(variants, key=len)[:160],
            count=len(variants),
            extra=f"{len(set(variants))} distinct phrasings" if len(set(variants)) > 1 else "",
        )
        for variants in ranked
    ]


def build_analytics(founder_id: str, product_id: str | None = None) -> AnalyticsOut:
    products = _scoped_products(founder_id, product_id)
    if not products:
        return AnalyticsOut(product_id=product_id)

    db = get_db()
    sessions: list[dict] = []
    events: list[dict] = []
    messages: list[dict] = []

    for pid in products:
        sessions.extend(db.find(SESSIONS, {"product_id": pid}))
        events.extend(db.find(EVENTS, {"product_id": pid}))
        messages.extend(db.find(MESSAGES, {"product_id": pid}))

    if not sessions:
        return AnalyticsOut(product_id=product_id)

    section_titles: dict[str, str] = {}
    for pid in products:
        for section in db.find("demo_sections", {"product_id": pid}):
            section_titles[section["section_key"]] = section.get("title") or section["section_key"]

    # -- section engagement -------------------------------------------------
    section_counter: Counter[str] = Counter()
    for event in events:
        if event.get("event_type") == "section_view":
            key = (event.get("payload") or {}).get("section")
            if key:
                section_counter[key] += 1

    section_views = [
        CountItem(label=section_titles.get(key, key), count=count, extra=key)
        for key, count in section_counter.most_common(12)
    ]

    # -- questions and objections ------------------------------------------
    # Taken from the prospect's own words: the AI's classification marks the
    # assistant turn, so the question is the message immediately before it.
    by_session: dict[str, list[dict]] = {}
    for message in messages:
        by_session.setdefault(message["session_id"], []).append(message)

    question_texts: list[str] = []
    objection_texts: list[str] = []

    for turns in by_session.values():
        turns.sort(key=lambda m: int(m.get("turn_index") or 0))
        for index, message in enumerate(turns):
            if message.get("role") != "assistant" or index == 0:
                continue
            previous = turns[index - 1]
            if previous.get("role") != "user":
                continue
            text = (previous.get("content") or "").strip()
            if not text:
                continue
            if message.get("intent") in ("ask_question", "ask_pricing"):
                question_texts.append(text)
            elif message.get("intent") == "raise_objection":
                objection_texts.append(text)

    # -- intents ------------------------------------------------------------
    intent_counter = Counter(
        m["intent"] for m in messages if m.get("role") == "assistant" and m.get("intent")
    )
    intents = [
        CountItem(label=intent.replace("_", " ").title(), count=count)
        for intent, count in intent_counter.most_common()
    ]

    # -- score distribution -------------------------------------------------
    distribution = {"Low Intent": 0, "Medium Intent": 0, "High Intent": 0}
    engaged = [s for s in sessions if int(s.get("message_count") or 0) >= 2]
    for session in engaged:
        classification = (session.get("lead_score") or {}).get("classification")
        if classification in distribution:
            distribution[classification] += 1

    # -- sessions over time -------------------------------------------------
    day_counter: Counter[str] = Counter()
    for session in sessions:
        started = parse_ts(session.get("started_at"))
        if started:
            day_counter[started.date().isoformat()] += 1
    daily = [
        CountItem(label=day, count=count) for day, count in sorted(day_counter.items())[-30:]
    ]

    durations = [int(s.get("duration_seconds") or 0) for s in engaged]
    message_counts = [int(s.get("message_count") or 0) for s in engaged]
    contact_requests = sum(1 for s in sessions if s.get("contact_requested"))

    return AnalyticsOut(
        product_id=product_id,
        sessions=len(sessions),
        completed_sessions=sum(1 for s in sessions if s.get("status") == "ended"),
        average_duration_seconds=int(sum(durations) / len(durations)) if durations else 0,
        average_messages=round(sum(message_counts) / len(message_counts), 1)
        if message_counts else 0.0,
        section_views=section_views,
        top_questions=_top_grouped(question_texts),
        top_objections=_top_grouped(objection_texts),
        score_distribution=distribution,
        contact_conversion_rate=round(contact_requests / len(sessions) * 100, 1)
        if sessions else 0.0,
        intents=intents,
        daily_sessions=daily,
    )
