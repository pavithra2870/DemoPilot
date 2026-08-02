"""Generates the founder-facing lead intelligence brief when a session ends.

The lead score is computed before this runs and passed in as fact, so the report
never invents or contradicts the number. If the model is unavailable, a
deterministic report is assembled from the qualification data — the founder still
gets something actionable.
"""

from __future__ import annotations

from app.ai_services.llm import LLMProvider, get_llm_provider
from app.ai_services.prompts.lead_report import build_report_messages
from app.ai_services.structured_outputs.parser import parse_model
from app.ai_services.structured_outputs.schemas import LeadReportResponse
from app.core.errors import LLMError
from app.core.logging_config import get_logger
from app.models.qualification import LeadReport, LeadScore, QualificationData

log = get_logger("ai.agent.report")


class LeadReportAgent:
    def __init__(self, provider: LLMProvider | None = None):
        self.provider = provider or get_llm_provider()

    async def generate(
        self,
        *,
        product: dict,
        qualification: QualificationData,
        lead_score: LeadScore,
        transcript: list[dict],
        sections_visited: list[str],
        contact_requested: bool,
    ) -> LeadReport:
        prospect_turns = [m for m in transcript if m.get("role") == "user"]
        if not prospect_turns:
            return _empty_report()

        messages = build_report_messages(
            product=product,
            qualification=qualification,
            lead_score=lead_score,
            transcript=transcript,
            sections_visited=sections_visited,
            contact_requested=contact_requested,
        )

        try:
            result = await self.provider.complete(
                messages, temperature=0.3, max_tokens=900, json_mode=True
            )
        except LLMError as exc:
            log.warning("Lead report fell back to deterministic: %s", exc)
            return _deterministic_report(qualification, lead_score, contact_requested)

        parsed = parse_model(result.text, LeadReportResponse)
        if parsed is None:
            return _deterministic_report(qualification, lead_score, contact_requested)

        return LeadReport(
            summary=parsed.summary,
            key_takeaways=parsed.key_takeaways,
            interests=parsed.interests,
            concerns=parsed.concerns,
            recommended_action=parsed.recommended_action,
            should_follow_up=parsed.should_follow_up,
            follow_up_urgency=parsed.follow_up_urgency,
            suggested_opening_line=parsed.suggested_opening_line,
        )


def _empty_report() -> LeadReport:
    return LeadReport(
        summary="This visitor opened the demo but never sent a message.",
        recommended_action="No follow-up needed — there is nothing to act on.",
        should_follow_up=False,
        follow_up_urgency="nurture",
    )


def _deterministic_report(
    qualification: QualificationData, score: LeadScore, contact_requested: bool
) -> LeadReport:
    """No-LLM fallback assembled purely from collected facts."""
    who = qualification.company or "An anonymous visitor"
    bits: list[str] = []

    if qualification.company_size:
        bits.append(f"about {qualification.company_size}")
    if qualification.industry:
        bits.append(f"in {qualification.industry}")
    descriptor = f" ({', '.join(bits)})" if bits else ""

    sentences = [f"{who}{descriptor} went through the demo."]
    if qualification.pain_point:
        sentences.append(f"Their stated problem: {qualification.pain_point}.")
    if qualification.current_solution:
        sentences.append(f"They currently use {qualification.current_solution}.")
    if qualification.timeline:
        sentences.append(f"Timeline: {qualification.timeline}.")
    sentences.append(f"Lead score {score.score}/100 — {score.classification}.")

    if contact_requested:
        action = "They asked to be contacted. Reply today while the demo is fresh."
        urgency = "now"
    elif score.score >= 70:
        action = "Strong fit. Send a personalised follow-up referencing their stated problem."
        urgency = "this_week"
    elif score.score >= 40:
        action = (
            "Partial fit. Follow up with the specific material that answers what they "
            "were unsure about."
        )
        urgency = "this_month"
    else:
        action = "Weak signal. Add to nurture rather than spending outreach time."
        urgency = "nurture"

    return LeadReport(
        summary=" ".join(sentences),
        key_takeaways=[
            f"{field.replace('_', ' ').title()}: {getattr(qualification, field)}"
            for field in qualification.known_fields()[:6]
        ],
        concerns=[f"Unknown: {s}" for s in score.missing_signals[:4]],
        recommended_action=action,
        should_follow_up=score.score >= 40 or contact_requested,
        follow_up_urgency=urgency,  # type: ignore[arg-type]
        suggested_opening_line=(
            f"Hi{' ' + qualification.name if qualification.name else ''} — you mentioned "
            f"{qualification.pain_point or 'what you are working on'} when you went through "
            "the demo. Here is how other teams handled that."
        ),
    )
