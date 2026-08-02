"""Founder-facing lead intelligence and analytics shapes."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.qualification import LeadReport, LeadScore, QualificationData
from app.schemas.demo import DemoActionOut, SourceOut


class LeadListItem(BaseModel):
    session_id: str
    product_id: str
    product_name: str = ""
    name: str = "Anonymous visitor"
    email: str | None = None
    company: str | None = None
    industry: str | None = None
    job_title: str | None = None
    score: int = 0
    classification: str = "Low Intent"
    pain_point: str | None = None
    message_count: int = 0
    contact_requested: bool = False
    status: str = "active"
    started_at: str | None = None
    last_activity_at: str | None = None
    recommended_action: str = ""


class TranscriptMessage(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None = None
    stage: str | None = None
    action: DemoActionOut | None = None
    sources: list[SourceOut] = Field(default_factory=list)
    confidence: str | None = None
    created_at: str | None = None


class LeadDetail(BaseModel):
    session_id: str
    product_id: str
    product_name: str = ""
    prospect: dict = Field(default_factory=dict)
    qualification: QualificationData = Field(default_factory=QualificationData)
    lead_score: LeadScore = Field(default_factory=LeadScore)
    report: LeadReport | None = None
    transcript: list[TranscriptMessage] = Field(default_factory=list)
    questions_asked: list[str] = Field(default_factory=list)
    objections_raised: list[str] = Field(default_factory=list)
    sections_visited: list[str] = Field(default_factory=list)
    features_viewed: list[str] = Field(default_factory=list)
    stage: str = "welcome"
    status: str = "active"
    contact_requested: bool = False
    duration_seconds: int = 0
    started_at: str | None = None
    last_activity_at: str | None = None


class OverviewStats(BaseModel):
    total_prospects: int = 0
    total_sessions: int = 0
    qualified_leads: int = 0
    high_intent_leads: int = 0
    contact_requests: int = 0
    conversion_rate: float = 0.0
    average_score: float = 0.0
    average_duration_seconds: int = 0
    products: int = 0
    published_products: int = 0
    recent_leads: list[LeadListItem] = Field(default_factory=list)


class CountItem(BaseModel):
    label: str
    count: int
    extra: str = ""


class AnalyticsOut(BaseModel):
    product_id: str | None = None
    sessions: int = 0
    completed_sessions: int = 0
    average_duration_seconds: int = 0
    average_messages: float = 0.0
    section_views: list[CountItem] = Field(default_factory=list)
    top_questions: list[CountItem] = Field(default_factory=list)
    top_objections: list[CountItem] = Field(default_factory=list)
    score_distribution: dict[str, int] = Field(default_factory=dict)
    contact_conversion_rate: float = 0.0
    intents: list[CountItem] = Field(default_factory=list)
    daily_sessions: list[CountItem] = Field(default_factory=list)
