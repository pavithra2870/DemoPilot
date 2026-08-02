"""Explainable lead scoring.

Deliberately NOT an LLM call. A founder deciding how to spend their week needs a
number that is stable, reproducible and auditable — ask a model to score the same
conversation twice and you get two answers. Every component here returns points
*and* the sentence explaining them, so the dashboard can always show its work.

    Problem fit    0-25   does their pain match what this product solves
    Urgency        0-20   how much it hurts right now
    Budget fit     0-20   stated budget against the ICP range
    Company fit    0-20   industry / size / title against the ICP
    Buying timeline 0-15  how soon they intend to act
                   -----
                   0-100  → Low (<40) / Medium (40-69) / High (70+)

Fields the prospect never revealed score low but are reported in
`missing_signals`, which the QUALIFY stage then targets. Unknown is not the same
as bad, and the founder can see the difference.
"""

from __future__ import annotations

import re

from app.core.logging_config import get_logger
from app.models.qualification import LeadScore, QualificationData, ScoreComponent

log = get_logger("service.scoring")

MAX_PROBLEM_FIT = 25
MAX_URGENCY = 20
MAX_BUDGET = 20
MAX_COMPANY = 20
MAX_TIMELINE = 15

_STOPWORDS = frozenset(
    """the a an and or of to for with our we is are in on at by from that this it
    have has had need needs our their your""".split()
)


def _tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(w) > 2 and w not in _STOPWORDS
    }


def _overlap(a: str, b: str) -> float:
    """Jaccard-ish overlap, normalised by the smaller set so a short ICP pain point
    can still fully match a long prospect description."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def _matches_any(value: str | None, candidates: list[str]) -> str | None:
    if not value or not candidates:
        return None
    lowered = value.lower()
    for candidate in candidates:
        c = (candidate or "").strip().lower()
        if not c:
            continue
        if c in lowered or lowered in c or _overlap(value, candidate) >= 0.5:
            return candidate
    return None


# ---------------------------------------------------------------------------
# Numeric helpers
# ---------------------------------------------------------------------------

_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?", re.I)


def parse_amount(text: str | None) -> float | None:
    """'$2k per month' → 2000.0. Returns the upper bound of a range."""
    if not text:
        return None
    values: list[float] = []
    for raw, suffix in _NUMBER.findall(text):
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix.lower() == "k":
            value *= 1_000
        elif suffix.lower() == "m":
            value *= 1_000_000
        values.append(value)
    return max(values) if values else None


_SIZE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("1-10", 1, 10),
    ("11-50", 11, 50),
    ("51-200", 51, 200),
    ("201-500", 201, 500),
    ("501-1000", 501, 1000),
    ("1000+", 1001, 10_000_000),
)


def parse_headcount(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"(\d[\d,]*)", text)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def size_bucket(text: str | None) -> str | None:
    count = parse_headcount(text)
    if count is None:
        return None
    for label, low, high in _SIZE_BUCKETS:
        if low <= count <= high:
            return label
    return None


_TIMELINE_DAYS: tuple[tuple[str, int], ...] = (
    (r"immediately|asap|right away|urgent|this week|yesterday", 7),
    (r"within 30 days|this month|next month|30 days", 30),
    (r"within (\d+)\s*days?", 0),          # parsed numerically below
    (r"within (\d+)\s*weeks?", 0),
    (r"within (\d+)\s*months?", 0),
    (r"this quarter|by end of quarter|q[1-4]", 90),
    (r"next quarter", 180),
    (r"by end of year|this year", 180),
    (r"next year", 365),
    (r"exploring|browsing|researching|no timeline|no rush|someday|eventually", 999),
)


def timeline_to_days(text: str | None) -> int | None:
    if not text:
        return None
    lowered = text.lower()

    match = re.search(r"within (\d+)\s*(day|week|month)s?", lowered)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        return amount * {"day": 1, "week": 7, "month": 30}[unit]

    for pattern, days in _TIMELINE_DAYS:
        if days and re.search(pattern, lowered):
            return days
    return None


# ---------------------------------------------------------------------------
# Components
# ---------------------------------------------------------------------------

def _score_problem_fit(q: QualificationData, product: dict, icp: dict) -> ScoreComponent:
    if not q.pain_point:
        return ScoreComponent(
            points=0, max=MAX_PROBLEM_FIT,
            reason="They never described a specific problem.",
        )

    icp_pains: list[str] = icp.get("pain_points") or []
    matched = _matches_any(q.pain_point, icp_pains)
    product_overlap = _overlap(q.pain_point, product.get("main_problem") or "")

    if matched:
        return ScoreComponent(
            points=MAX_PROBLEM_FIT, max=MAX_PROBLEM_FIT,
            reason=f"Their pain point '{q.pain_point}' matches the target pain '{matched}'.",
        )
    if product_overlap >= 0.4:
        return ScoreComponent(
            points=21, max=MAX_PROBLEM_FIT,
            reason=f"'{q.pain_point}' closely overlaps the core problem the product solves.",
        )
    if product_overlap >= 0.2:
        return ScoreComponent(
            points=15, max=MAX_PROBLEM_FIT,
            reason=f"'{q.pain_point}' partially overlaps what the product addresses.",
        )
    if q.current_solution:
        return ScoreComponent(
            points=11, max=MAX_PROBLEM_FIT,
            reason=(
                f"They described a problem ('{q.pain_point}') and already use "
                f"{q.current_solution}, but it is not an obvious match for this product."
            ),
        )
    return ScoreComponent(
        points=8, max=MAX_PROBLEM_FIT,
        reason=f"They stated a problem ('{q.pain_point}') outside the product's stated focus.",
    )


_URGENCY_POINTS: dict[str, tuple[int, str]] = {
    "critical": (MAX_URGENCY, "They described the problem as critical or actively costly."),
    "high": (16, "They described the problem as serious."),
    "low": (4, "They described this as exploratory rather than pressing."),
}


def _score_urgency(q: QualificationData) -> ScoreComponent:
    if q.urgency:
        for key, (points, reason) in _URGENCY_POINTS.items():
            if key in q.urgency.lower():
                return ScoreComponent(points=points, max=MAX_URGENCY, reason=reason)

    days = timeline_to_days(q.timeline)
    if days is not None and days <= 30:
        return ScoreComponent(
            points=15, max=MAX_URGENCY,
            reason="No explicit urgency stated, but their timeline is within 30 days.",
        )
    if q.current_solution and re.search(
        r"manual|by hand|spreadsheet|excel|nothing", q.current_solution, re.I
    ):
        return ScoreComponent(
            points=13, max=MAX_URGENCY,
            reason=f"They handle this manually today ({q.current_solution}) — real ongoing cost.",
        )
    if q.pain_point:
        return ScoreComponent(
            points=8, max=MAX_URGENCY,
            reason="A problem exists but they did not signal how urgent it is.",
        )
    return ScoreComponent(
        points=0, max=MAX_URGENCY, reason="No urgency signal was given."
    )


def _score_budget(q: QualificationData, icp: dict) -> ScoreComponent:
    if not q.budget:
        return ScoreComponent(
            points=0, max=MAX_BUDGET, reason="Budget was never discussed."
        )

    if re.search(r"no budget|nothing allocated|free|can'?t pay|zero", q.budget, re.I):
        return ScoreComponent(
            points=2, max=MAX_BUDGET,
            reason=f"They indicated no budget is available ('{q.budget}').",
        )

    amount = parse_amount(q.budget)
    low = icp.get("budget_min")
    high = icp.get("budget_max")

    if amount is None:
        return ScoreComponent(
            points=11, max=MAX_BUDGET,
            reason=f"They mentioned budget ('{q.budget}') but gave no figure to compare.",
        )
    if low is None and high is None:
        return ScoreComponent(
            points=14, max=MAX_BUDGET,
            reason=f"They stated a budget of {q.budget}; no ICP budget range is configured "
                   "to compare it against.",
        )
    if low is not None and amount < low * 0.7:
        return ScoreComponent(
            points=5, max=MAX_BUDGET,
            reason=f"Their budget ({q.budget}) is well below the target range "
                   f"(from {low:,.0f}).",
        )
    if low is not None and amount < low:
        return ScoreComponent(
            points=12, max=MAX_BUDGET,
            reason=f"Their budget ({q.budget}) is slightly under the target range "
                   f"(from {low:,.0f}) — possibly workable.",
        )
    return ScoreComponent(
        points=MAX_BUDGET, max=MAX_BUDGET,
        reason=f"Their budget ({q.budget}) sits inside the target range.",
    )


def _score_company_fit(q: QualificationData, icp: dict) -> ScoreComponent:
    """Three sub-signals worth ~7 each: industry, size, seniority."""
    points = 0
    reasons: list[str] = []
    unknown: list[str] = []

    industries = icp.get("industries") or []
    if q.industry:
        matched = _matches_any(q.industry, industries)
        if matched:
            points += 7
            reasons.append(f"industry '{q.industry}' is a target industry")
        elif not industries:
            points += 4
            reasons.append(f"industry '{q.industry}' recorded (no ICP industries configured)")
        else:
            reasons.append(f"industry '{q.industry}' is outside the target industries")
    else:
        unknown.append("industry")

    sizes = icp.get("company_sizes") or []
    if q.company_size:
        bucket = size_bucket(q.company_size)
        matched = _matches_any(q.company_size, sizes) or (
            _matches_any(bucket, sizes) if bucket else None
        )
        if matched:
            points += 7
            reasons.append(f"company size '{q.company_size}' fits the target size")
        elif not sizes:
            points += 4
            reasons.append(f"company size '{q.company_size}' recorded (no ICP sizes configured)")
        else:
            reasons.append(f"company size '{q.company_size}' is outside the target range")
    else:
        unknown.append("company size")

    titles = icp.get("job_titles") or []
    if q.job_title:
        matched = _matches_any(q.job_title, titles)
        if matched:
            points += 6
            reasons.append(f"role '{q.job_title}' matches a target buyer title")
        elif not titles:
            points += 3
            reasons.append(f"role '{q.job_title}' recorded (no ICP titles configured)")
        else:
            reasons.append(f"role '{q.job_title}' is not a typical buyer title")
    else:
        unknown.append("job title")

    if q.authority and "decision maker" in q.authority.lower():
        points = min(MAX_COMPANY, points + 3)
        reasons.append("they can make the decision themselves")

    if not reasons:
        return ScoreComponent(
            points=0, max=MAX_COMPANY,
            reason="Nothing is known about their company or role.",
        )

    text = "Company fit: " + "; ".join(reasons) + "."
    if unknown:
        text += f" Not established: {', '.join(unknown)}."
    return ScoreComponent(points=min(points, MAX_COMPANY), max=MAX_COMPANY, reason=text)


def _score_timeline(q: QualificationData, icp: dict) -> ScoreComponent:
    if not q.timeline:
        return ScoreComponent(
            points=0, max=MAX_TIMELINE, reason="They did not indicate a timeline."
        )

    days = timeline_to_days(q.timeline)
    if days is None:
        return ScoreComponent(
            points=6, max=MAX_TIMELINE,
            reason=f"They mentioned timing ('{q.timeline}') but it is not specific.",
        )

    ideal = int(icp.get("ideal_timeline_days") or 90)
    if days <= 7:
        return ScoreComponent(points=MAX_TIMELINE, max=MAX_TIMELINE,
                              reason=f"They want to move immediately ('{q.timeline}').")
    if days <= 30:
        return ScoreComponent(points=14, max=MAX_TIMELINE,
                              reason=f"Buying timeline is within 30 days ('{q.timeline}').")
    if days <= max(ideal, 90):
        return ScoreComponent(points=10, max=MAX_TIMELINE,
                              reason=f"Timeline of '{q.timeline}' is within the typical "
                                     "buying window.")
    if days <= 365:
        return ScoreComponent(points=5, max=MAX_TIMELINE,
                              reason=f"Timeline of '{q.timeline}' is beyond the usual "
                                     "buying window.")
    return ScoreComponent(points=1, max=MAX_TIMELINE,
                          reason="They are exploring with no timeline to act.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify(score: int) -> str:
    if score >= 70:
        return "High Intent"
    if score >= 40:
        return "Medium Intent"
    return "Low Intent"


def _headline_reasons(breakdown: dict[str, ScoreComponent]) -> list[str]:
    """Short, scannable reasons for the lead card — the full text lives in the breakdown."""
    labels = {
        "problem_fit": ("Strong problem fit", "Weak problem fit"),
        "urgency": ("High urgency", "Low urgency"),
        "budget_fit": ("Budget aligns with pricing", "Budget not established"),
        "company_fit": ("Company matches the ICP", "Company fit unclear"),
        "buying_timeline": ("Near-term buying timeline", "No near-term timeline"),
    }
    reasons: list[str] = []
    for key, component in breakdown.items():
        strong, weak = labels.get(key, (key, key))
        ratio = component.points / component.max if component.max else 0
        if ratio >= 0.7:
            reasons.append(strong)
        elif ratio <= 0.25:
            reasons.append(weak)
    return reasons


def calculate_lead_score(
    qualification: QualificationData,
    product: dict,
    *,
    contact_requested: bool = False,
    sections_visited: int = 0,
    message_count: int = 0,
) -> LeadScore:
    icp = product.get("icp") or {}

    breakdown = {
        "problem_fit": _score_problem_fit(qualification, product, icp),
        "urgency": _score_urgency(qualification),
        "budget_fit": _score_budget(qualification, icp),
        "company_fit": _score_company_fit(qualification, icp),
        "buying_timeline": _score_timeline(qualification, icp),
    }

    total = sum(c.points for c in breakdown.values())
    reasons = _headline_reasons(breakdown)

    # Behavioural signals are capped at +6 so engagement can nudge a borderline
    # lead but never manufacture a high-intent one out of curiosity alone.
    bonus = 0
    if contact_requested:
        bonus += 4
        reasons.insert(0, "Explicitly asked to be contacted")
    if sections_visited >= 4:
        bonus += 1
        reasons.append(f"Explored {sections_visited} demo sections")
    if message_count >= 8:
        bonus += 1
        reasons.append("Sustained, engaged conversation")
    total = min(100, total + min(bonus, 6))

    # Disqualifiers are the founder's explicit veto — they cap, not zero, so the
    # detail is preserved for review.
    for disqualifier in icp.get("disqualifiers") or []:
        for field_name in ("industry", "company_size", "current_solution", "budget"):
            value = getattr(qualification, field_name, None)
            if value and _matches_any(value, [disqualifier]):
                total = min(total, 30)
                reasons.insert(0, f"Matches a disqualifier: {disqualifier}")
                break

    missing = qualification.missing_critical()
    return LeadScore(
        score=int(total),
        classification=classify(int(total)),
        breakdown=breakdown,
        reasons=reasons[:6],
        missing_signals=missing,
    )


def recommended_action(score: LeadScore, qualification: QualificationData,
                       contact_requested: bool) -> str:
    """One-line suggestion for the lead list, available without generating a report."""
    if contact_requested:
        return "Reply today — they asked to be contacted."
    if score.score >= 70:
        pain = qualification.pain_point or "their stated problem"
        return f"Reach out this week referencing {pain}."
    if score.score >= 40:
        if score.missing_signals:
            return f"Worth a short follow-up to establish {score.missing_signals[0].replace('_', ' ')}."
        return "Send supporting material and check back in a week."
    return "Low signal — add to nurture."
