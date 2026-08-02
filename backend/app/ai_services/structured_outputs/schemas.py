"""The contract the LLM must satisfy.

Everything the model returns is validated against these before it reaches a
service, a database row, or the browser. The frontend then re-validates the
action against its own whitelist — model output is treated as data, never code.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.security import sanitize_text
from app.models.qualification import QualificationData


class ActionType(str, Enum):
    NAVIGATE = "navigate"
    HIGHLIGHT = "highlight"
    OPEN_PRICING = "open_pricing"
    SHOW_FAQ = "show_faq"
    SHOW_INTEGRATION = "show_integration"
    REQUEST_CONTACT = "request_contact"
    END_DEMO = "end_demo"
    NONE = "none"


ACTION_VALUES = frozenset(a.value for a in ActionType)


class DemoAction(BaseModel):
    """A command the AI issues to the demo UI. `target` is validated against the
    founder's real section keys before it ever leaves the server."""

    type: ActionType = ActionType.NONE
    target: str | None = None
    label: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, v):
        if isinstance(v, ActionType):
            return v
        text = sanitize_text(str(v or ""), max_length=40).lower().strip()
        return text if text in ACTION_VALUES else ActionType.NONE.value

    @field_validator("target", "label", mode="before")
    @classmethod
    def _clean(cls, v):
        text = sanitize_text(v, max_length=80)
        return text or None


class Intent(str, Enum):
    GREETING = "greeting"
    DESCRIBE_CONTEXT = "describe_context"
    REQUEST_DEMO_SECTION = "request_demo_section"
    ASK_QUESTION = "ask_question"
    ASK_PRICING = "ask_pricing"
    RAISE_OBJECTION = "raise_objection"
    REQUEST_CONTACT = "request_contact"
    SMALLTALK = "smalltalk"
    END = "end"


INTENT_VALUES = frozenset(i.value for i in Intent)


class AgentResponse(BaseModel):
    """One turn of the AI Sales Engineer."""

    message: str = Field(default="", max_length=4000)
    intent: Intent = Intent.SMALLTALK
    action: DemoAction = Field(default_factory=DemoAction)
    qualification: QualificationData = Field(default_factory=QualificationData)
    next_question: str | None = None
    used_context: bool = False
    confidence: Literal["high", "medium", "low"] = "medium"
    objection_addressed: str | None = None
    suggested_replies: list[str] = Field(default_factory=list)

    @field_validator("intent", mode="before")
    @classmethod
    def _coerce_intent(cls, v):
        if isinstance(v, Intent):
            return v
        text = sanitize_text(str(v or ""), max_length=40).lower().strip()
        return text if text in INTENT_VALUES else Intent.SMALLTALK.value

    @field_validator("message", mode="before")
    @classmethod
    def _clean_message(cls, v):
        return sanitize_text(v, max_length=4000)

    @field_validator("next_question", "objection_addressed", mode="before")
    @classmethod
    def _clean_optional(cls, v):
        return sanitize_text(v, max_length=300) or None

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v):
        text = sanitize_text(str(v or ""), max_length=20).lower().strip()
        return text if text in {"high", "medium", "low"} else "medium"

    @field_validator("qualification", mode="before")
    @classmethod
    def _coerce_qualification(cls, v):
        if v in (None, "", [], "null"):
            return QualificationData()
        return v

    @field_validator("suggested_replies", mode="before")
    @classmethod
    def _clean_replies(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        cleaned = [sanitize_text(str(r), max_length=90) for r in v]
        return [r for r in cleaned if r][:3]


class LeadReportResponse(BaseModel):
    """Founder-facing lead intelligence, produced once a session ends."""

    summary: str = Field(default="", max_length=1500)
    key_takeaways: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    recommended_action: str = Field(default="", max_length=600)
    should_follow_up: bool = False
    follow_up_urgency: Literal["now", "this_week", "this_month", "nurture"] = "nurture"
    suggested_opening_line: str = Field(default="", max_length=400)

    @field_validator("summary", "recommended_action", "suggested_opening_line", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=1500)

    @field_validator("key_takeaways", "interests", "concerns", mode="before")
    @classmethod
    def _clean_list(cls, v):
        if not v:
            return []
        if isinstance(v, str):
            v = [v]
        cleaned = [sanitize_text(str(i), max_length=200) for i in v]
        return [i for i in cleaned if i][:8]

    @field_validator("should_follow_up", mode="before")
    @classmethod
    def _coerce_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in {"true", "yes", "1"}
        return bool(v)


# The JSON shape shown to the model. Kept next to the schema so the two cannot drift.
AGENT_RESPONSE_TEMPLATE = """{
  "message": "<what you say to the prospect — plain conversational text>",
  "intent": "greeting | describe_context | request_demo_section | ask_question | ask_pricing | raise_objection | request_contact | smalltalk | end",
  "action": {
    "type": "navigate | highlight | open_pricing | show_faq | show_integration | request_contact | end_demo | none",
    "target": "<a section id from AVAILABLE DEMO SECTIONS, or null>",
    "label": "<short label for the UI, or null>"
  },
  "qualification": {
    "name": null, "email": null, "company": null, "job_title": null,
    "industry": null, "company_size": null, "pain_point": null,
    "current_solution": null, "budget": null, "timeline": null,
    "authority": null, "urgency": null
  },
  "next_question": "<the single question you asked, or null>",
  "used_context": true,
  "confidence": "high | medium | low",
  "objection_addressed": "<the objection you handled, or null>",
  "suggested_replies": ["<short reply chip>", "<another>"]
}"""

LEAD_REPORT_TEMPLATE = """{
  "summary": "<3-5 sentences the founder can read in 15 seconds>",
  "key_takeaways": ["<fact>", "<fact>"],
  "interests": ["<what they engaged with>"],
  "concerns": ["<objections or hesitations they raised>"],
  "recommended_action": "<the specific next step for the founder>",
  "should_follow_up": true,
  "follow_up_urgency": "now | this_week | this_month | nurture",
  "suggested_opening_line": "<a first line for the founder's outreach email>"
}"""
