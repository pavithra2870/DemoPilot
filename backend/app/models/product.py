"""Domain models for the founder-supplied product knowledge.

Nothing here is specific to any one product — these are the shapes a founder
fills in, and everything downstream (prompts, RAG, scoring) reads from them.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.security import sanitize_text


def _clean(value: str | None, limit: int = 2000) -> str:
    return sanitize_text(value, max_length=limit)


class Feature(BaseModel):
    name: str = ""
    description: str = ""
    keywords: list[str] = Field(default_factory=list)

    @field_validator("name", "description", mode="before")
    @classmethod
    def _s(cls, v):
        return _clean(v)


class PricingPlan(BaseModel):
    name: str = ""
    price: str = ""
    period: str = "month"
    includes: list[str] = Field(default_factory=list)
    best_for: str = ""


class Pricing(BaseModel):
    model: str = ""            # e.g. "per seat", "usage based", "flat"
    currency: str = "USD"
    plans: list[PricingPlan] = Field(default_factory=list)
    free_trial: str = ""
    notes: str = ""


class Integration(BaseModel):
    name: str = ""
    description: str = ""


class FAQ(BaseModel):
    question: str = ""
    answer: str = ""


class Objection(BaseModel):
    objection: str = ""
    response: str = ""


class CaseStudy(BaseModel):
    title: str = ""
    customer: str = ""
    outcome: str = ""
    details: str = ""


class IdealCustomerProfile(BaseModel):
    """Drives both demo personalisation and the deterministic lead score."""

    industries: list[str] = Field(default_factory=list)
    company_sizes: list[str] = Field(default_factory=list)
    job_titles: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    budget_note: str = ""
    ideal_timeline_days: int = 90
    current_alternatives: list[str] = Field(default_factory=list)
    qualification_criteria: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)


class CallToAction(BaseModel):
    type: str = "book_call"        # book_call | request_trial | contact | waitlist | pricing
    label: str = "Book a call"
    url: str = ""
    note: str = ""


class DemoSectionModel(BaseModel):
    """One navigable screen of the interactive demo — an AI action target."""

    id: str = ""
    section_key: str
    title: str
    description: str = ""
    feature_explanation: str = ""
    visual_placeholder: str = ""
    highlights: list[dict] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    order_index: int = 0
