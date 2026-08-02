"""Qualification state and the explainable lead score."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.security import sanitize_text

# Fields the agent tries to learn conversationally. Order matters: it is the
# priority order the QUALIFY stage uses when picking the next natural question.
QUALIFICATION_FIELDS: tuple[str, ...] = (
    "pain_point",
    "company",
    "industry",
    "company_size",
    "current_solution",
    "timeline",
    "budget",
    "authority",
    "job_title",
    "urgency",
    "name",
    "email",
)

# Which fields the founder actually needs to decide on follow-up.
CRITICAL_FIELDS: tuple[str, ...] = ("pain_point", "company", "timeline", "budget", "authority")


class QualificationData(BaseModel):
    """Everything learned about the prospect so far. Every field optional by design —
    the agent collects it over the conversation, never as an upfront form."""

    name: str | None = None
    email: str | None = None
    company: str | None = None
    job_title: str | None = None
    industry: str | None = None
    company_size: str | None = None
    pain_point: str | None = None
    current_solution: str | None = None
    budget: str | None = None
    timeline: str | None = None
    authority: str | None = None
    urgency: str | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, v):
        if v is None:
            return None
        text = sanitize_text(str(v), max_length=400)
        # Models love emitting these instead of null.
        if text.lower() in {"", "null", "none", "n/a", "na", "unknown", "unspecified", "-"}:
            return None
        return text

    def known_fields(self) -> list[str]:
        return [f for f in QUALIFICATION_FIELDS if getattr(self, f, None)]

    def missing_fields(self) -> list[str]:
        return [f for f in QUALIFICATION_FIELDS if not getattr(self, f, None)]

    def missing_critical(self) -> list[str]:
        return [f for f in CRITICAL_FIELDS if not getattr(self, f, None)]

    def completeness(self) -> float:
        return len(self.known_fields()) / len(QUALIFICATION_FIELDS)

    def merge(self, incoming: "QualificationData | dict | None") -> "QualificationData":
        """Merge newly extracted values. Existing values win unless the new value is
        materially richer — prevents the model from overwriting good data with vaguer
        restatements on later turns."""
        if incoming is None:
            return self.model_copy()
        if isinstance(incoming, dict):
            incoming = QualificationData(**incoming)

        merged = self.model_dump()
        for field in QUALIFICATION_FIELDS:
            new_value = getattr(incoming, field, None)
            if not new_value:
                continue
            current = merged.get(field)
            if not current or len(str(new_value)) > len(str(current)) * 1.3:
                merged[field] = new_value
        return QualificationData(**merged)


class ScoreComponent(BaseModel):
    points: int
    max: int
    reason: str


class Intent(str, Enum):
    LOW = "Low Intent"
    MEDIUM = "Medium Intent"
    HIGH = "High Intent"


class LeadScore(BaseModel):
    score: int = 0
    classification: Literal["Low Intent", "Medium Intent", "High Intent"] = "Low Intent"
    breakdown: dict[str, ScoreComponent] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)


class LeadReport(BaseModel):
    """The founder-facing lead intelligence summary."""

    summary: str = ""
    key_takeaways: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    should_follow_up: bool = False
    follow_up_urgency: Literal["now", "this_week", "this_month", "nurture"] = "nurture"
    suggested_opening_line: str = ""
