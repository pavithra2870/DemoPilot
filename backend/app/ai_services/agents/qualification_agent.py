"""Qualification extraction.

Two layers, deliberately:

  * `extract_deterministic` — regex over the raw message. Catches team size,
    timelines, currency amounts and named incumbent tools reliably and for free.
  * the sales agent's own `qualification` field — catches everything expressed in
    natural language that regex cannot.

Deterministic wins on conflict for the fields it is confident about, because a
model paraphrasing "we're about 50 people" into "medium-sized" loses information
the founder actually wants.
"""

from __future__ import annotations

import re

from app.core.logging_config import get_logger
from app.models.qualification import QualificationData

log = get_logger("ai.agent.qualification")

_SIZE = re.compile(
    r"\b(?:we(?:'re| are)?|team of|about|around|roughly|company of|approx\.?)?\s*"
    r"(\d{1,3}(?:,\d{3})*|\d+)\s*[- ]?\s*"
    r"(people|person|employees|staff|engineers|devs|developers|seats|users|agents|reps)\b",
    re.I,
)

_TIMELINE_PHRASES: tuple[tuple[str, str], ...] = (
    (r"\b(asap|immediately|right away|urgently|this week|yesterday)\b", "immediately"),
    (r"\b(this|next) month\b", "within 30 days"),
    (r"\bwithin (?:the )?(?:next )?(\d+)\s*(day|week|month)s?\b", r"within \1 \2s"),
    (r"\bin (?:the )?next (\d+)\s*(day|week|month)s?\b", r"within \1 \2s"),
    (r"\b(?:by|before) (?:the )?end of (?:the )?(quarter|month|year)\b", r"by end of \1"),
    (r"\b(q[1-4])\b", r"\1"),
    (r"\bnext (quarter|year)\b", r"next \1"),
    (r"\b(just )?(looking|browsing|exploring|researching|evaluating)\b", "exploring"),
    (r"\bno (?:real )?(?:timeline|rush|hurry)\b", "no timeline"),
)

_BUDGET = re.compile(
    r"([$€£]\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m)?)"
    r"(?:\s*(?:-|to|–)\s*([$€£]?\s?\d[\d,]*(?:\.\d+)?\s*(?:k|m)?))?"
    r"(?:\s*(?:per|/|a)\s*(month|year|seat|user|mo|yr))?",
    re.I,
)

_NO_BUDGET = re.compile(
    r"\b(no budget|nothing allocated|not budgeted|free (?:tier|only|plan)|"
    r"can'?t (?:pay|spend)|zero budget)\b",
    re.I,
)

_AUTHORITY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bi (?:make|own|have) the (?:final )?(?:decision|call|budget)\b", "decision maker"),
    (r"\bi(?:'m| am) the (?:ceo|cto|coo|cfo|founder|co-?founder|owner|vp|head of)\b",
     "decision maker"),
    (r"\bmy (?:call|decision|budget)\b", "decision maker"),
    (r"\bi(?:'ll| will) (?:need to )?(?:check|ask|run it by|talk to|loop in)\b", "influencer"),
    (r"\b(?:my|our) (?:boss|manager|cto|ceo|team|committee) (?:would|will|needs to|has to)\b",
     "influencer"),
    (r"\bjust (?:researching|gathering|looking) for (?:my|the) team\b", "researcher"),
    (r"\bprocurement\b", "committee purchase"),
)

_URGENCY_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(critical|urgent|blocking|on fire|bleeding|losing (?:customers|money|deals))\b",
     "critical"),
    (r"\b(major|serious|big) (?:problem|issue|pain|headache)\b", "high"),
    (r"\b(?:really|badly) need\b", "high"),
    (r"\b(?:nice to have|not urgent|someday|eventually|down the (?:road|line))\b", "low"),
    (r"\bjust (?:curious|browsing|looking)\b", "low"),
)

_CURRENT_SOLUTION = re.compile(
    r"\b(?:we|i|they)\s+(?:currently\s+)?(?:use|using|are on|have|rely on|work with|"
    r"run on|do it (?:in|with))\s+([A-Za-z][\w .+&/-]{1,40}?)"
    r"(?=[.,;!?]|\s+(?:but|and|for|to|which|right now|today|at the moment)\b|$)",
    re.I,
)

_MANUAL_SOLUTION = re.compile(
    r"\b(manually|by hand|spreadsheets?|excel|google sheets|nothing (?:at all|right now)|"
    r"no (?:tool|system|solution))\b",
    re.I,
)

# Words that end a job title. Without these, "I'm the Head of Support so it's my
# call" captures the whole clause as the title.
_TITLE_STOP = (
    r"and|so|but|because|here|there|at|for|which|who|that|then|now|since|while|"
    r"plus|though|although|however|therefore|thus|hence|also|too"
)

_JOB_TITLE = re.compile(
    r"\bi(?:'m| am)\s+(?:the\s+|a\s+|an\s+)?"
    r"("
    r"co-?founder|founder|ceo|cto|coo|cfo|cmo|cio|"
    r"(?:vp|vice president)(?:\s+of\s+(?:(?!" + _TITLE_STOP + r")\w+)(?:\s+(?:(?!" + _TITLE_STOP + r")\w+)){0,2})?|"
    r"head\s+of\s+(?:(?!" + _TITLE_STOP + r")\w+)(?:\s+(?:(?!" + _TITLE_STOP + r")\w+)){0,2}|"
    r"director(?:\s+of\s+(?:(?!" + _TITLE_STOP + r")\w+)(?:\s+(?:(?!" + _TITLE_STOP + r")\w+)){0,2})?|"
    r"(?:product|engineering|operations|marketing|sales|support|project)\s+(?:manager|lead|director)|"
    r"(?:senior\s+|lead\s+|staff\s+|principal\s+)?(?:software\s+)?"
    r"(?:engineer|developer|designer|analyst|consultant|architect|marketer|recruiter)|"
    r"manager|operations lead"
    r")\b",
    re.I,
)

_COMPANY = re.compile(
    r"\b(?:i work (?:at|for)|we(?:'re| are) (?:called|at)|"
    r"(?:my|our) company is(?: called)?|here at)\s+"
    r"([A-Z][\w.&'-]*(?:\s+[A-Z][\w.&'-]*){0,3})",
)

# Pain points are normally extracted by the model, which handles phrasing far
# better than regex. This is a backstop for the clearest constructions, so the
# problem-fit score is not zero when the model misses it or is unavailable.
_PAIN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(?:we|our team|our \w+ team|i)\s+(?:are|'re|is)?\s*"
        r"(?:currently\s+)?(?:struggling with|drowning in|overwhelmed by|"
        r"buried in|bottlenecked by|blocked by|losing \w+ to)\s+"
        r"([^.!?;]{4,90})",
        re.I,
    ),
    re.compile(
        r"\b(?:our|the|my)\s+(?:main|biggest|core|real)\s+"
        r"(?:problem|issue|challenge|pain|bottleneck)\s+(?:is|are)\s+([^.!?;]{4,90})",
        re.I,
    ),
    re.compile(
        r"\b(?:we|i)\s+(?:really\s+)?(?:need|want)\s+(?:to|a way to)\s+([^.!?;]{4,90})",
        re.I,
    ),
    re.compile(
        r"\b(?:trying|looking)\s+to\s+(?:solve|fix|reduce|automate|eliminate|speed up)\s+"
        r"([^.!?;]{4,90})",
        re.I,
    ),
    re.compile(
        r"\b(?:too much|too many|way too many)\s+([^.!?;]{4,80})",
        re.I,
    ),
)


def _extract_pain_point(text: str) -> str | None:
    for pattern in _PAIN_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        phrase = match.group(1).strip(" .,;:")
        phrase = re.sub(r"\s+", " ", phrase)
        if 4 <= len(phrase) <= 90:
            return phrase
    return None


def _first_match(text: str, patterns: tuple[tuple[str, str], ...]) -> str | None:
    for pattern, replacement in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return match.expand(replacement) if "\\" in replacement else replacement
            except re.error:
                return replacement
    return None


def extract_deterministic(message: str) -> QualificationData:
    """Regex pass. Returns only what it is genuinely confident about."""
    text = (message or "").strip()
    if not text:
        return QualificationData()

    data: dict[str, str] = {}

    size = _SIZE.search(text)
    if size:
        data["company_size"] = f"{size.group(1)} {size.group(2).lower()}"

    timeline = _first_match(text, _TIMELINE_PHRASES)
    if timeline:
        data["timeline"] = timeline

    if _NO_BUDGET.search(text):
        data["budget"] = "no budget allocated"
    else:
        budget = _BUDGET.search(text)
        if budget:
            amount = budget.group(1).strip()
            if budget.group(2):
                amount += f" - {budget.group(2).strip()}"
            if budget.group(3):
                amount += f" per {budget.group(3).lower()}"
            data["budget"] = amount

    authority = _first_match(text, _AUTHORITY_PATTERNS)
    if authority:
        data["authority"] = authority

    urgency = _first_match(text, _URGENCY_PATTERNS)
    if urgency:
        data["urgency"] = urgency

    if _MANUAL_SOLUTION.search(text):
        data["current_solution"] = _MANUAL_SOLUTION.search(text).group(1).lower()
    else:
        solution = _CURRENT_SOLUTION.search(text)
        if solution:
            candidate = solution.group(1).strip(" .,")
            # Avoid capturing verb phrases like "use it to track".
            if 2 <= len(candidate) <= 40 and not candidate.lower().startswith(
                ("it ", "them", "that", "this", "a lot")
            ):
                data["current_solution"] = candidate

    title = _JOB_TITLE.search(text)
    if title:
        data["job_title"] = title.group(1).strip(" .,")

    company = _COMPANY.search(text)
    if company:
        data["company"] = company.group(1).strip(" .,")

    pain = _extract_pain_point(text)
    if pain:
        data["pain_point"] = pain

    return QualificationData(**data)


def merge_extractions(
    existing: QualificationData,
    llm_extracted: QualificationData | None,
    message: str,
) -> QualificationData:
    """Deterministic > model > existing, per field.

    Applied in that order so a precise "50 people" is never clobbered by a vaguer
    model paraphrase on the same turn.
    """
    merged = existing.merge(llm_extracted)
    deterministic = extract_deterministic(message)

    updates = merged.model_dump()
    for field_name in ("company_size", "timeline", "budget", "authority",
                       "urgency", "current_solution", "job_title", "company"):
        value = getattr(deterministic, field_name, None)
        if value:
            updates[field_name] = value

    # Pain point is the one field the model reliably beats regex on, so the
    # deterministic value only fills a gap rather than overwriting.
    if deterministic.pain_point and not updates.get("pain_point"):
        updates["pain_point"] = deterministic.pain_point

    return QualificationData(**updates)


class QualificationAgent:
    """Thin object wrapper so the demo service has one obvious collaborator."""

    def update(
        self,
        existing: QualificationData,
        llm_extracted: QualificationData | None,
        message: str,
    ) -> QualificationData:
        updated = merge_extractions(existing, llm_extracted, message)
        gained = set(updated.known_fields()) - set(existing.known_fields())
        if gained:
            log.debug("Qualification gained: %s", ", ".join(sorted(gained)))
        return updated
