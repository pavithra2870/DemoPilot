"""The AI Sales Engineer agent.

Per turn:
  1. classify the message well enough to decide the stage      (heuristic, free)
  2. retrieve grounding knowledge if the turn is factual        (RAG)
  3. resolve the stage directive                                (state machine)
  4. build the prompt and call the model                        (LLM)
  5. validate and *sanitise* the structured response            (Pydantic + guards)

Step 5 is where the model stops being trusted: unknown action targets are
downgraded, hallucinated navigation is rejected, and repeated questions are
stripped. If the model is unreachable, a deterministic fallback turn keeps the
demo usable instead of showing an error.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai_services.llm import LLMProvider, Message, get_llm_provider
from app.ai_services.memory.conversation_memory import ConversationMemory
from app.ai_services.prompts import sales_engineer as prompts
from app.ai_services.state_machine import Stage, build_directive, next_stage
from app.ai_services.structured_outputs.parser import parse_model, plain_text_fallback
from app.ai_services.structured_outputs.schemas import (
    ActionType,
    AgentResponse,
    DemoAction,
    Intent,
)
from app.core.errors import LLMError
from app.core.logging_config import get_logger
from app.models.qualification import QualificationData
from rag.pipeline import RetrievedSource, build_context_block, retrieve

log = get_logger("ai.agent.sales")


@dataclass
class AgentTurn:
    response: AgentResponse
    stage: Stage
    sources: list[RetrievedSource] = field(default_factory=list)
    summary: str = ""
    degraded: bool = False


# ---------------------------------------------------------------------------
# Lightweight intent classification
# ---------------------------------------------------------------------------
# Done in Python rather than by a second model call: it is instant, free, and
# only needs to be good enough to pick a stage. The LLM still reports its own
# intent, and that value wins when the heuristic is unsure.

_OBJECTION_PATTERNS = (
    r"\btoo (expensive|pricey|costly)\b", r"\bcan'?t afford\b", r"\bout of (our )?budget\b",
    r"\balready (use|using|have|on)\b", r"\bwe use \w+", r"\bswitch(ing)? (cost|from|is)\b",
    r"\bmigrat(e|ion)\b", r"\b(is it|how) secure\b", r"\bsecurity concern",
    r"\bgdpr|soc ?2|hipaa\b", r"\bbuild (this|it) (in[- ]?house|ourselves|internally)\b",
    r"\bthink about it\b", r"\bnot (sure|convinced|ready)\b", r"\bwhy (should|would) (we|i)\b",
    r"\bwhat'?s the catch\b", r"\bcompetitor\b", r"\bvs\.? \w+", r"\bbetter than\b",
)

_PRICING_PATTERNS = (
    r"\bpric(e|ing)\b", r"\bcost\b", r"\bhow much\b", r"\bper (seat|user|month)\b",
    r"\bplan(s)?\b", r"\bfree tier\b", r"\btrial\b", r"\bdiscount\b", r"\bquote\b",
)

_DEMO_REQUEST_PATTERNS = (
    r"\bshow me\b", r"\bcan i see\b", r"\bwalk me through\b", r"\bdemo\b",
    r"\btake me to\b", r"\blet'?s see\b", r"\bwhat does .* look like\b", r"\bopen the\b",
)

_CONTACT_PATTERNS = (
    r"\bbook a (call|demo|meeting)\b", r"\btalk to (someone|a human|the team|sales)\b",
    r"\bcontact me\b", r"\bget in touch\b", r"\bsign (me )?up\b", r"\bstart a trial\b",
    r"\bemail me\b", r"\bhow do i (get started|sign up|buy)\b",
)

_END_PATTERNS = (
    r"^\s*(bye|goodbye|thanks,? bye|that'?s all|i'?m done|no thanks)\s*[.!]?\s*$",
    r"\bthat'?s (all|everything) (for now|thanks)\b",
)

_CONTEXT_PATTERNS = (
    r"\bwe (are|have|run|need|struggle|use)\b", r"\bour (team|company|business|company)\b",
    r"\bi'?m (the|a|an) \w+", r"\bi work (at|for)\b", r"\b\d+[- ]?(person|people|employees|seats)\b",
    r"\bmy (team|company|role)\b",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, re.I) for p in patterns)


def classify_intent(message: str, turn_count: int) -> Intent:
    text = (message or "").strip()
    if not text:
        return Intent.SMALLTALK

    if _matches(text, _END_PATTERNS):
        return Intent.END
    if _matches(text, _CONTACT_PATTERNS):
        return Intent.REQUEST_CONTACT
    if _matches(text, _OBJECTION_PATTERNS):
        return Intent.RAISE_OBJECTION
    if _matches(text, _PRICING_PATTERNS):
        return Intent.ASK_PRICING
    if _matches(text, _DEMO_REQUEST_PATTERNS):
        return Intent.REQUEST_DEMO_SECTION
    if "?" in text:
        return Intent.ASK_QUESTION
    if _matches(text, _CONTEXT_PATTERNS):
        return Intent.DESCRIBE_CONTEXT
    if turn_count <= 1:
        return Intent.GREETING
    return Intent.DESCRIBE_CONTEXT if len(text.split()) > 6 else Intent.SMALLTALK


# Turns where retrieval is worth the latency.
_RETRIEVAL_INTENTS = {
    Intent.ASK_QUESTION,
    Intent.ASK_PRICING,
    Intent.RAISE_OBJECTION,
    Intent.REQUEST_DEMO_SECTION,
}


# ---------------------------------------------------------------------------
# Response sanitisation
# ---------------------------------------------------------------------------

def sanitize_action(
    action: DemoAction, sections: list[dict], *, has_email: bool
) -> DemoAction:
    """Never let the model steer the UI somewhere that does not exist."""
    valid_keys = {s.get("section_key") for s in sections if s.get("section_key")}

    if action.type in (ActionType.NAVIGATE, ActionType.HIGHLIGHT):
        if not action.target:
            return DemoAction(type=ActionType.NONE)
        if action.type == ActionType.NAVIGATE and action.target not in valid_keys:
            resolved = _resolve_section(action.target, sections)
            if not resolved:
                log.info("Rejected navigate to unknown section '%s'", action.target)
                return DemoAction(type=ActionType.NONE)
            action = action.model_copy(update={"target": resolved})

    # Do not ask for contact details the prospect has already given.
    if action.type == ActionType.REQUEST_CONTACT and has_email:
        return DemoAction(type=ActionType.NONE)

    return action


def _resolve_section(target: str, sections: list[dict]) -> str | None:
    """Models often return a title ("Analytics Dashboard") instead of the id.
    Recover from that rather than dropping a legitimate navigation."""
    needle = (target or "").strip().lower()
    if not needle:
        return None

    for section in sections:
        if (section.get("title") or "").strip().lower() == needle:
            return section["section_key"]

    from app.core.security import slugify

    slug = slugify(needle, fallback="")
    for section in sections:
        if section.get("section_key") == slug:
            return section["section_key"]

    for section in sections:
        keywords = [k.lower() for k in (section.get("keywords") or [])]
        if needle in keywords:
            return section["section_key"]
    return None


def _strip_repeated_question(response: AgentResponse, qualification: QualificationData) -> None:
    """Guard against the model asking for something it already knows. The prompt
    forbids it; this makes it structurally impossible."""
    if not response.next_question:
        return
    lowered = response.next_question.lower()
    for field_name in qualification.known_fields():
        token = field_name.replace("_", " ")
        if token in lowered:
            response.next_question = None
            return


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class SalesEngineerAgent:
    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or get_llm_provider()

    async def opening_turn(self, *, product: dict, sections: list[dict]) -> AgentTurn:
        qualification = QualificationData()
        directive = build_directive(
            Stage.WELCOME,
            qualification,
            turn_count=0,
            has_knowledge=False,
            section_titles=[s.get("title", "") for s in sections],
        )

        messages = prompts.build_system_messages(
            product=product,
            sections=sections,
            qualification=qualification,
            directive=directive,
            active_section=None,
            sections_visited=[],
            turn_count=0,
        )
        messages.append(prompts.build_opening_message(product, sections))

        try:
            result = await self.provider.complete(messages, temperature=0.5, json_mode=True)
            response = parse_model(result.text, AgentResponse)
            if response is None:
                text = plain_text_fallback(result.text)
                response = _fallback_opening(product, sections, text)
            else:
                response.intent = Intent.GREETING
                response.action = sanitize_action(response.action, sections, has_email=False)
            degraded = False
        except LLMError as exc:
            log.warning("Opening turn fell back to a static greeting: %s", exc)
            response = _fallback_opening(product, sections)
            degraded = True

        return AgentTurn(response=response, stage=Stage.WELCOME, degraded=degraded)

    async def respond(
        self,
        *,
        product: dict,
        sections: list[dict],
        transcript: list[dict],
        qualification: QualificationData,
        current_stage: Stage,
        prospect_message: str,
        active_section: str | None = None,
        sections_visited: list[str] | None = None,
        conversation_summary: str = "",
    ) -> AgentTurn:
        memory = ConversationMemory(transcript, conversation_summary)
        turn_count = memory.turn_count + 1

        # 1 — classify
        heuristic_intent = classify_intent(prospect_message, turn_count)

        # 2 — retrieve
        sources: list[RetrievedSource] = []
        if heuristic_intent in _RETRIEVAL_INTENTS or turn_count <= 2:
            try:
                sources = retrieve(product["id"], prospect_message)
            except Exception as exc:  # noqa: BLE001 - retrieval must not break a turn
                log.warning("Retrieval failed for product %s: %s", product["id"], exc)
        context_block = build_context_block(sources)

        # 3 — resolve the stage
        stage = next_stage(
            current=current_stage,
            intent=heuristic_intent,
            qualification=qualification,
            turn_count=turn_count,
        )
        directive = build_directive(
            stage,
            qualification,
            turn_count=turn_count,
            has_knowledge=bool(sources),
            section_titles=[s.get("title", "") for s in sections],
        )

        # 4 — compress older history if the conversation has grown
        summary = conversation_summary
        if memory.needs_summary:
            summary = await memory.maybe_summarize(self.provider)

        messages: list[Message] = prompts.build_system_messages(
            product=product,
            sections=sections,
            qualification=qualification,
            directive=directive,
            active_section=active_section,
            sections_visited=sections_visited or [],
            turn_count=turn_count,
            conversation_summary=summary,
        )
        messages.extend(memory.as_messages())
        messages.append(prompts.build_turn_message(prospect_message, context_block))

        # 5 — generate, validate, sanitise
        try:
            result = await self.provider.complete(messages, json_mode=True)
        except LLMError as exc:
            log.warning("LLM unavailable, serving fallback turn: %s", exc)
            return AgentTurn(
                response=_fallback_turn(heuristic_intent, sources, product),
                stage=stage,
                sources=sources,
                summary=summary,
                degraded=True,
            )

        response = parse_model(result.text, AgentResponse)
        if response is None:
            text = plain_text_fallback(result.text)
            if not text:
                return AgentTurn(
                    response=_fallback_turn(heuristic_intent, sources, product),
                    stage=stage,
                    sources=sources,
                    summary=summary,
                    degraded=True,
                )
            response = AgentResponse(message=text, intent=heuristic_intent)

        # The heuristic is more reliable for objections and contact requests, where
        # the model tends to under-report; otherwise trust the model's own read.
        if heuristic_intent in (Intent.RAISE_OBJECTION, Intent.REQUEST_CONTACT, Intent.END):
            response.intent = heuristic_intent

        response.action = sanitize_action(
            response.action, sections, has_email=bool(qualification.email)
        )
        response.used_context = bool(sources) and response.used_context
        if not sources and response.confidence == "high" and heuristic_intent in _RETRIEVAL_INTENTS:
            response.confidence = "low"
        _strip_repeated_question(response, qualification)

        return AgentTurn(response=response, stage=stage, sources=sources, summary=summary)


# ---------------------------------------------------------------------------
# Deterministic fallbacks — the demo degrades, it does not break
# ---------------------------------------------------------------------------

def _fallback_opening(
    product: dict, sections: list[dict], text: str = ""
) -> AgentResponse:
    name = product.get("name") or "this product"
    message = text or (product.get("welcome_message") or "").strip() or (
        f"Welcome — I can walk you through {name} based on what your team is trying "
        "to solve. What brought you here today?"
    )
    action = (
        DemoAction(type=ActionType.NAVIGATE, target=sections[0]["section_key"])
        if sections
        else DemoAction(type=ActionType.NONE)
    )
    return AgentResponse(
        message=message,
        intent=Intent.GREETING,
        action=action,
        confidence="medium",
        suggested_replies=[
            "Tell me what it does",
            "What problem does it solve?",
            "How much does it cost?",
        ],
    )


def _fallback_turn(
    intent: Intent, sources: list[RetrievedSource], product: dict
) -> AgentResponse:
    """Used when the model is unreachable. Still honest, still grounded — it quotes
    retrieved knowledge if there is any rather than inventing an answer."""
    if sources:
        message = (
            "I'm having trouble reaching my language model right now, but here is the "
            f"most relevant thing from the knowledge base:\n\n{sources[0].snippet}\n\n"
            f"(Source: {sources[0].label})"
        )
    else:
        contact = (product.get("cta") or {}).get("label") or "get in touch with the team"
        message = (
            "I can't reach my language model at the moment, so I don't want to guess at "
            f"an answer. Please try again in a moment, or {contact.lower()} and someone "
            "will follow up directly."
        )

    return AgentResponse(
        message=message,
        intent=intent,
        action=DemoAction(type=ActionType.NONE),
        confidence="low",
        used_context=bool(sources),
    )
