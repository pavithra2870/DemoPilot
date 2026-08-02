"""Prompt for the founder-facing lead intelligence report.

The score itself is never asked of the model — it is computed deterministically
and passed in as an input, so the narrative and the number can never disagree.
"""

from __future__ import annotations

from app.ai_services.llm import Message
from app.ai_services.structured_outputs.schemas import LEAD_REPORT_TEMPLATE
from app.models.qualification import LeadScore, QualificationData

SYSTEM = """You write lead intelligence briefs for a founder who was not on the call.

They will read this in fifteen seconds and decide whether to spend an hour on
this prospect. So: concrete over flattering, specific over generic.

Rules:
- Use only what is in the transcript and the qualification data. Invent nothing.
- Name real details: the company, the tool they use today, the number they gave.
- If the prospect is a poor fit, say so plainly. A false positive wastes the
  founder's week.
- "recommended_action" must be a specific action, not "follow up soon". Say what
  to send and what to say.
- The lead score is already computed and given to you. Explain what it means for
  the founder's next move; do not recompute or dispute it.
- Reply with ONE JSON object and nothing else."""


def _format_qualification(qualification: QualificationData) -> str:
    known = qualification.known_fields()
    if not known:
        return "Nothing was learned about this prospect."
    return "\n".join(
        f"- {field.replace('_', ' ')}: {getattr(qualification, field)}" for field in known
    )


def _format_score(score: LeadScore) -> str:
    lines = [f"Score: {score.score}/100 ({score.classification})"]
    for name, component in score.breakdown.items():
        lines.append(
            f"- {name.replace('_', ' ')}: {component.points}/{component.max} — {component.reason}"
        )
    if score.missing_signals:
        lines.append("Unknown: " + ", ".join(score.missing_signals))
    return "\n".join(lines)


def build_report_messages(
    *,
    product: dict,
    qualification: QualificationData,
    lead_score: LeadScore,
    transcript: list[dict],
    sections_visited: list[str],
    contact_requested: bool,
) -> list[Message]:
    lines = []
    for message in transcript[-40:]:
        role = "Prospect" if message.get("role") == "user" else "AI Sales Engineer"
        lines.append(f"{role}: {(message.get('content') or '').strip()}")
    conversation = "\n".join(lines) or "(no conversation took place)"

    icp = product.get("icp") or {}
    context = f"""PRODUCT
{product.get('name', '')} — {product.get('tagline') or product.get('description', '')[:200]}
Ideal customer: industries {icp.get('industries') or 'any'}, sizes {icp.get('company_sizes') or 'any'}, titles {icp.get('job_titles') or 'any'}

QUALIFICATION DATA COLLECTED
{_format_qualification(qualification)}

LEAD SCORE (already computed — do not change it)
{_format_score(lead_score)}

DEMO ENGAGEMENT
Sections viewed: {', '.join(sections_visited) or 'none'}
Requested contact: {'yes' if contact_requested else 'no'}

TRANSCRIPT
{conversation}

Write the brief as this JSON object:

{LEAD_REPORT_TEMPLATE}"""

    return [
        Message(role="system", content=SYSTEM),
        Message(role="user", content=context),
    ]


SUMMARY_SYSTEM = """You compress the earlier part of a sales conversation so it can be
dropped from the context window without losing anything that matters.

Keep: what the prospect said about their company, problem, current tools, budget,
timeline and authority; which parts of the product they reacted to; any objection
they raised and whether it was resolved.

Drop: pleasantries, restatements, anything the AI said that they did not respond to.

Write 4-8 terse factual lines. No preamble, no JSON."""


def build_summary_messages(transcript: list[dict], existing_summary: str = "") -> list[Message]:
    lines = []
    for message in transcript:
        role = "Prospect" if message.get("role") == "user" else "AI"
        lines.append(f"{role}: {(message.get('content') or '').strip()}")

    prefix = f"Summary so far:\n{existing_summary}\n\nNew exchanges:\n" if existing_summary else ""
    return [
        Message(role="system", content=SUMMARY_SYSTEM),
        Message(role="user", content=prefix + "\n".join(lines)),
    ]
