"""Request/response shapes for the public prospect-facing demo."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.core.security import sanitize_text
from app.models.qualification import LeadScore, QualificationData
from app.schemas.product import DemoSectionOut


class PublicPricingPlan(BaseModel):
    name: str = ""
    price: str = ""
    period: str = ""
    includes: list[str] = Field(default_factory=list)
    best_for: str = ""


class PublicDemoConfig(BaseModel):
    """Everything the demo page needs. Deliberately excludes founder-only data
    such as the ICP, qualification criteria, objection playbook and disqualifiers."""

    product_id: str
    slug: str
    name: str
    tagline: str = ""
    description: str = ""
    category: str = ""
    main_problem: str = ""
    main_benefits: list[str] = Field(default_factory=list)
    pricing_model: str = ""
    pricing_currency: str = "USD"
    pricing_plans: list[PublicPricingPlan] = Field(default_factory=list)
    free_trial: str = ""
    pricing_notes: str = ""
    integrations: list[dict] = Field(default_factory=list)
    faqs: list[dict] = Field(default_factory=list)
    security_info: str = ""
    sections: list[DemoSectionOut] = Field(default_factory=list)
    cta: dict = Field(default_factory=dict)
    welcome_message: str = ""


class StartSessionRequest(BaseModel):
    referrer: str = ""
    name: str = ""
    email: str = ""
    company: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=200)


class DemoActionOut(BaseModel):
    type: str = "none"
    target: str | None = None
    label: str | None = None


class SourceOut(BaseModel):
    id: str
    label: str
    kind: str = "document"
    snippet: str = ""
    score: float = 0.0


class AgentTurnOut(BaseModel):
    message_id: str
    session_id: str
    message: str
    intent: str = "smalltalk"
    stage: str = "welcome"
    action: DemoActionOut = Field(default_factory=DemoActionOut)
    sources: list[SourceOut] = Field(default_factory=list)
    confidence: str = "medium"
    qualification: QualificationData = Field(default_factory=QualificationData)
    lead_score: LeadScore = Field(default_factory=LeadScore)
    suggested_replies: list[str] = Field(default_factory=list)
    contact_requested: bool = False
    degraded: bool = False


class StartSessionResponse(BaseModel):
    session_id: str
    config: PublicDemoConfig
    opening: AgentTurnOut


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    active_section: str | None = None

    @field_validator("message", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=4000)


class DemoEventRequest(BaseModel):
    event_type: str = Field(max_length=48)
    payload: dict = Field(default_factory=dict)

    @field_validator("event_type", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=48)


class ContactRequest(BaseModel):
    name: str = ""
    email: str = ""
    company: str = ""
    job_title: str = ""
    note: str = ""
    cta_type: str = ""

    @field_validator("*", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=500)


class SessionEndResponse(BaseModel):
    session_id: str
    lead_score: LeadScore
    next_step: dict = Field(default_factory=dict)
