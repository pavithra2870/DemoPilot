"""The demo conversation state machine.

This is the difference between an AI Sales Engineer and a chatbot. A chatbot
reacts to the last message. This agent always has a *job* for the current turn —
discover, personalise, demonstrate, answer, handle, qualify, convert — and the
job is decided here, in Python, from observable state:

    (current stage, detected intent, qualification completeness, turn count)

The resolved stage is injected into the next system prompt as a directive. The
model chooses words; the machine chooses purpose. That separation is also what
keeps behaviour predictable enough to debug.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai_services.structured_outputs.schemas import Intent
from app.models.qualification import QualificationData


class Stage(str, Enum):
    WELCOME = "welcome"
    DISCOVER = "discover"
    PERSONALIZE = "personalize"
    DEMONSTRATE = "demonstrate"
    ANSWER = "answer"
    OBJECTION = "objection"
    QUALIFY = "qualify"
    CONVERT = "convert"
    ENDED = "ended"


# A prospect should never be pushed toward a CTA before they have had a real
# conversation — unless they ask for it themselves.
MIN_TURNS_BEFORE_CONVERT = 4

# Only ask a qualification question every N turns, so the demo never feels like
# an interrogation.
QUALIFY_EVERY_N_TURNS = 3


@dataclass
class StageDirective:
    stage: Stage
    goal: str
    instruction: str
    should_ask_question: bool = False
    target_field: str | None = None


_FIELD_PROMPTS: dict[str, str] = {
    "pain_point": "what problem they are actually trying to solve",
    "company": "what company they work at",
    "industry": "what industry they operate in",
    "company_size": "roughly how big their team or company is",
    "current_solution": "what they use for this today",
    "timeline": "when they are hoping to have something in place",
    "budget": "what kind of budget range this sits in for them",
    "authority": "who else is involved in a decision like this",
    "job_title": "what their role is",
    "urgency": "how pressing this is right now",
    "name": "their name",
    "email": "the best email to send a follow-up to",
}


def next_stage(
    *,
    current: Stage,
    intent: Intent,
    qualification: QualificationData,
    turn_count: int,
    explicit_end: bool = False,
) -> Stage:
    """Pure transition function — no I/O, trivially testable."""
    if explicit_end or intent == Intent.END:
        return Stage.ENDED
    if current == Stage.ENDED:
        return Stage.ENDED

    # Prospect-driven intents always win: never talk over someone who just asked
    # a direct question.
    if intent == Intent.REQUEST_CONTACT:
        return Stage.CONVERT
    if intent == Intent.RAISE_OBJECTION:
        return Stage.OBJECTION
    if intent in (Intent.ASK_QUESTION, Intent.ASK_PRICING):
        return Stage.ANSWER
    if intent == Intent.REQUEST_DEMO_SECTION:
        return Stage.DEMONSTRATE

    if current == Stage.WELCOME:
        return Stage.DISCOVER

    known = qualification.known_fields()
    has_context = bool(qualification.pain_point or qualification.industry or qualification.company)

    if current == Stage.DISCOVER:
        return Stage.PERSONALIZE if has_context else Stage.DISCOVER

    if current == Stage.PERSONALIZE:
        return Stage.DEMONSTRATE

    # After demonstrating or resolving something, decide between qualifying more
    # and moving toward a next step.
    if current in (Stage.DEMONSTRATE, Stage.ANSWER, Stage.OBJECTION, Stage.QUALIFY):
        missing_critical = qualification.missing_critical()
        ready_to_convert = (
            turn_count >= MIN_TURNS_BEFORE_CONVERT
            and len(known) >= 5
            and len(missing_critical) <= 1
        )
        if ready_to_convert:
            return Stage.CONVERT
        if missing_critical and turn_count % QUALIFY_EVERY_N_TURNS == 0:
            return Stage.QUALIFY
        return Stage.DEMONSTRATE if current != Stage.QUALIFY else Stage.DEMONSTRATE

    if current == Stage.CONVERT:
        return Stage.CONVERT

    return Stage.DISCOVER


def pick_qualification_target(qualification: QualificationData) -> str | None:
    """The single most valuable thing still unknown. Critical fields first, and
    never something already answered."""
    for field in qualification.missing_critical():
        return field
    missing = qualification.missing_fields()
    return missing[0] if missing else None


def build_directive(
    stage: Stage,
    qualification: QualificationData,
    *,
    turn_count: int,
    has_knowledge: bool,
    section_titles: list[str],
) -> StageDirective:
    """Turn a stage into concrete, prompt-ready instructions for this exact turn."""
    target = pick_qualification_target(qualification)
    ask_hint = (
        f"If it fits naturally, ask about {_FIELD_PROMPTS.get(target, target)}."
        if target else "Do not ask a qualification question this turn."
    )

    sections = ", ".join(section_titles[:8]) or "no sections configured yet"

    directives: dict[Stage, StageDirective] = {
        Stage.WELCOME: StageDirective(
            stage=Stage.WELCOME,
            goal="Open the demo and invite the prospect to say what they need.",
            instruction=(
                "Greet them in one or two sentences. Say what you can walk them "
                "through, then ask what brought them here. Do not pitch yet. "
                "Set action.type to 'none' or navigate to the overview section."
            ),
            should_ask_question=True,
            target_field="pain_point",
        ),
        Stage.DISCOVER: StageDirective(
            stage=Stage.DISCOVER,
            goal="Understand their company, role and the problem they are solving.",
            instruction=(
                "Acknowledge what they said specifically — no generic affirmations. "
                "Ask exactly one open question that moves you closer to understanding "
                f"their situation. {ask_hint} Keep it under 70 words."
            ),
            should_ask_question=True,
            target_field=target,
        ),
        Stage.PERSONALIZE: StageDirective(
            stage=Stage.PERSONALIZE,
            goal="Choose the part of the demo that actually matters to them.",
            instruction=(
                f"Available sections: {sections}. Pick the ONE most relevant to what "
                "they told you and say briefly why it is the right starting point. "
                "Set action.type to 'navigate' with that section's id as the target. "
                "Do not walk them through anything irrelevant."
            ),
        ),
        Stage.DEMONSTRATE: StageDirective(
            stage=Stage.DEMONSTRATE,
            goal="Show the feature and tie it back to their stated problem.",
            instruction=(
                "Explain what they are looking at in terms of THEIR problem, not as a "
                "feature list. Use 'navigate' to move to a section or 'highlight' to "
                "draw attention to a specific element. End by checking whether that "
                f"addresses their situation. {ask_hint}"
            ),
            should_ask_question=bool(target),
            target_field=target,
        ),
        Stage.ANSWER: StageDirective(
            stage=Stage.ANSWER,
            goal="Answer the question accurately from the knowledge base.",
            instruction=(
                "Answer directly and only from the KNOWLEDGE BASE block. "
                if has_knowledge
                else "You have no retrieved knowledge for this question. "
                "Say plainly that you cannot confirm it and offer to flag it for the team. "
            )
            + (
                "If the knowledge base does not cover it, say 'I don't have enough "
                "information to confirm that' and offer to pass the question on. "
                "Never invent capabilities, numbers, customers or integrations. "
                "If a demo section shows what you just described, navigate to it."
            ),
        ),
        Stage.OBJECTION: StageDirective(
            stage=Stage.OBJECTION,
            goal="Address the concern honestly using the founder's own positioning.",
            instruction=(
                "Acknowledge the concern as legitimate — do not dismiss it. Respond "
                "using the objection guidance in the knowledge base if it is there; "
                "otherwise be honest about the limits of what you know. Never "
                "overpromise to win the point. Set objection_addressed to the concern "
                "in a few words."
            ),
        ),
        Stage.QUALIFY: StageDirective(
            stage=Stage.QUALIFY,
            goal="Learn one more thing that helps the founder decide on follow-up.",
            instruction=(
                "Continue being useful first — add something of value about the "
                f"product or their situation. Then ask ONE question about "
                f"{_FIELD_PROMPTS.get(target, 'their situation')}. Make it feel like "
                "genuine curiosity, not a form. Never ask about something they have "
                "already told you."
            ),
            should_ask_question=True,
            target_field=target,
        ),
        Stage.CONVERT: StageDirective(
            stage=Stage.CONVERT,
            goal="Recommend the right next step and offer to capture contact details.",
            instruction=(
                "Summarise in one or two sentences what you learned about their "
                "situation and why the product fits. Then recommend the specific next "
                "step configured for this product. Set action.type to 'request_contact' "
                "if you do not have their email yet. Do not be pushy — one clear offer."
            ),
        ),
        Stage.ENDED: StageDirective(
            stage=Stage.ENDED,
            goal="Close warmly.",
            instruction=(
                "Thank them, restate the next step in one line, and set "
                "action.type to 'end_demo'."
            ),
        ),
    }

    return directives.get(stage, directives[Stage.DISCOVER])


def coerce_stage(value: str | None) -> Stage:
    try:
        return Stage(str(value or "welcome").lower())
    except ValueError:
        return Stage.WELCOME
