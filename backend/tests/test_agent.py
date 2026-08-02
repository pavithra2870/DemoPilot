"""Tests for the AI layer using a stubbed LLM provider.

The smoke test proves the plumbing works without a Groq key. This proves the
*model-facing* half: that a real structured response is parsed, validated,
sanitised and executed correctly — and that a badly-behaved model cannot break
the demo or steer it somewhere that does not exist.

    python -m tests.test_agent
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="demopilot-agent-test-"))
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = str(_TMP / "test.db")
os.environ["DATA_DIR"] = str(_TMP)
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["FAISS_DIR"] = str(_TMP / "faiss")
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["LOG_LEVEL"] = "ERROR"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from app.ai_services.agents.qualification_agent import extract_deterministic  # noqa: E402
from app.ai_services.agents.sales_engineer_agent import (  # noqa: E402
    SalesEngineerAgent,
    classify_intent,
    sanitize_action,
)
from app.ai_services.llm.base import CompletionResult, LLMProvider  # noqa: E402
from app.ai_services.state_machine import Stage, next_stage  # noqa: E402
from app.ai_services.structured_outputs.parser import parse_model  # noqa: E402
from app.ai_services.structured_outputs.schemas import (  # noqa: E402
    ActionType,
    AgentResponse,
    DemoAction,
    Intent,
)
from app.models.qualification import QualificationData  # noqa: E402
from app.services.lead_scoring_service import calculate_lead_score  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(label)
        print(f"  PASS  {label}")
    else:
        FAILED.append(f"{label} — {detail}")
        print(f"  FAIL  {label}  {detail}")


def section(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


# ---------------------------------------------------------------------------
# Stub provider
# ---------------------------------------------------------------------------

class StubProvider(LLMProvider):
    """Returns canned text. Records the prompts it was given so the tests can
    assert on what actually reached the model."""

    name = "stub"
    model = "stub-model"

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[list] = []

    async def complete(self, messages, *, temperature=None, max_tokens=None, json_mode=False):
        self.calls.append(messages)
        text = self.responses.pop(0) if self.responses else "{}"
        return CompletionResult(text=text, model=self.model)

    async def stream(self, messages, *, temperature=None, max_tokens=None):
        yield ""

    async def aclose(self):
        return None


PRODUCT = {
    "id": "prod-1",
    "name": "HelpFlow",
    "description": "AI support automation on top of your helpdesk.",
    "main_problem": "Support teams drown in repetitive tickets.",
    "features": [{"name": "Analytics", "description": "Deflection dashboards."}],
    "pricing": {"model": "per seat", "currency": "USD",
                "plans": [{"name": "Growth", "price": "199", "period": "month"}]},
    "objections": [{"objection": "Too expensive",
                    "response": "Teams save more in agent hours than it costs."}],
    "icp": {"industries": ["SaaS"], "company_sizes": ["51-200"],
            "job_titles": ["Head of Support"], "pain_points": ["support ticket overload"],
            "budget_min": 100, "budget_max": 2000, "ideal_timeline_days": 60},
    "cta": {"type": "book_call", "label": "Book a call"},
}

SECTIONS = [
    {"section_key": "overview", "title": "Overview", "description": "What it does.",
     "keywords": ["overview"]},
    {"section_key": "analytics", "title": "Analytics Dashboard",
     "description": "Deflection metrics.", "keywords": ["analytics", "reports", "metrics"]},
    {"section_key": "pricing", "title": "Pricing", "description": "Plans.",
     "keywords": ["pricing", "cost"]},
]


def good_response(**overrides) -> str:
    payload = {
        "message": "Let me show you the analytics dashboard — that's where deflection rate lives.",
        "intent": "request_demo_section",
        "action": {"type": "navigate", "target": "analytics", "label": "Analytics"},
        "qualification": {"industry": "SaaS", "pain_point": "support ticket overload",
                          "company_size": None, "budget": None},
        "next_question": "How is your team handling that today?",
        "used_context": True,
        "confidence": "high",
        "objection_addressed": None,
        "suggested_replies": ["Show me pricing", "How does setup work?"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def run_turn(provider: StubProvider, message: str, **kwargs):
    agent = SalesEngineerAgent(provider=provider)
    return asyncio.run(
        agent.respond(
            product=PRODUCT,
            sections=SECTIONS,
            transcript=kwargs.pop("transcript", []),
            qualification=kwargs.pop("qualification", QualificationData()),
            current_stage=kwargs.pop("current_stage", Stage.DISCOVER),
            prospect_message=message,
            **kwargs,
        )
    )


def main() -> int:
    # -- structured output parsing -----------------------------------------
    section("Structured output parsing")

    parsed = parse_model(good_response(), AgentResponse)
    check("Clean JSON parses", parsed is not None)
    check("Action type parsed", parsed.action.type == ActionType.NAVIGATE)
    check("Intent parsed", parsed.intent == Intent.REQUEST_DEMO_SECTION)
    check("Qualification parsed", parsed.qualification.industry == "SaaS")
    check("Nulls become None", parsed.qualification.budget is None)

    fenced = f"Here you go!\n\n```json\n{good_response()}\n```\nHope that helps."
    check("Fenced JSON with prose recovers", parse_model(fenced, AgentResponse) is not None)

    trailing = good_response().replace('"suggested_replies": [', '"suggested_replies": [')[:-1] + ",}"
    check("Trailing comma repaired", parse_model(trailing, AgentResponse) is not None)

    check("Non-JSON returns None", parse_model("I cannot answer that.", AgentResponse) is None)

    bad_action = parse_model(
        good_response(action={"type": "rm -rf /", "target": "analytics"}), AgentResponse
    )
    check("Unknown action type downgrades to none",
          bad_action.action.type == ActionType.NONE, str(bad_action.action))

    bad_intent = parse_model(good_response(intent="hack_the_planet"), AgentResponse)
    check("Unknown intent falls back to smalltalk", bad_intent.intent == Intent.SMALLTALK)

    truthy = parse_model(good_response(confidence="EXTREMELY HIGH"), AgentResponse)
    check("Invalid confidence normalises", truthy.confidence == "medium")

    string_qual = parse_model(good_response(qualification="null"), AgentResponse)
    check("String 'null' qualification survives", string_qual is not None)

    junk_field = parse_model(
        good_response(suggested_replies="just one string"), AgentResponse
    )
    check("Scalar coerced to list", junk_field.suggested_replies == ["just one string"])

    # -- action sanitisation -----------------------------------------------
    section("Action sanitisation")

    hallucinated = sanitize_action(
        DemoAction(type=ActionType.NAVIGATE, target="secret-admin-panel"),
        SECTIONS, has_email=False,
    )
    check("Hallucinated section target rejected", hallucinated.type == ActionType.NONE)

    real = sanitize_action(
        DemoAction(type=ActionType.NAVIGATE, target="analytics"), SECTIONS, has_email=False
    )
    check("Real section target preserved", real.target == "analytics")

    by_title = sanitize_action(
        DemoAction(type=ActionType.NAVIGATE, target="Analytics Dashboard"),
        SECTIONS, has_email=False,
    )
    check("Title resolved to section id", by_title.target == "analytics", str(by_title))

    by_keyword = sanitize_action(
        DemoAction(type=ActionType.NAVIGATE, target="metrics"), SECTIONS, has_email=False
    )
    check("Keyword resolved to section id", by_keyword.target == "analytics", str(by_keyword))

    suppressed = sanitize_action(
        DemoAction(type=ActionType.REQUEST_CONTACT), SECTIONS, has_email=True
    )
    check("Contact request suppressed when email is known",
          suppressed.type == ActionType.NONE)

    kept = sanitize_action(
        DemoAction(type=ActionType.REQUEST_CONTACT), SECTIONS, has_email=False
    )
    check("Contact request kept when email is unknown",
          kept.type == ActionType.REQUEST_CONTACT)

    # -- intent classification ---------------------------------------------
    section("Intent classification")

    cases = [
        ("Show me the analytics dashboard", Intent.REQUEST_DEMO_SECTION),
        ("How much does it cost per seat?", Intent.ASK_PRICING),
        ("Honestly that's too expensive for us", Intent.RAISE_OBJECTION),
        ("We already use Zendesk", Intent.RAISE_OBJECTION),
        ("Is this secure? Are you SOC 2?", Intent.RAISE_OBJECTION),
        ("Could we just build this in-house?", Intent.RAISE_OBJECTION),
        ("Can I book a call with someone?", Intent.REQUEST_CONTACT),
        ("We are a 50 person SaaS company", Intent.DESCRIBE_CONTEXT),
        ("thanks, bye", Intent.END),
        ("What integrations do you support?", Intent.ASK_QUESTION),
    ]
    for text, expected in cases:
        actual = classify_intent(text, turn_count=3)
        check(f"Intent: {text[:38]!r}", actual == expected, f"got {actual}")

    # -- state machine -----------------------------------------------------
    section("State machine")

    check("Welcome advances to discover",
          next_stage(current=Stage.WELCOME, intent=Intent.DESCRIBE_CONTEXT,
                     qualification=QualificationData(), turn_count=1) == Stage.DISCOVER)

    check("Context learned advances to personalize",
          next_stage(current=Stage.DISCOVER, intent=Intent.DESCRIBE_CONTEXT,
                     qualification=QualificationData(pain_point="tickets"),
                     turn_count=2) == Stage.PERSONALIZE)

    check("Objection always wins",
          next_stage(current=Stage.DEMONSTRATE, intent=Intent.RAISE_OBJECTION,
                     qualification=QualificationData(), turn_count=5) == Stage.OBJECTION)

    check("Question always wins",
          next_stage(current=Stage.QUALIFY, intent=Intent.ASK_QUESTION,
                     qualification=QualificationData(), turn_count=6) == Stage.ANSWER)

    check("Contact request jumps to convert",
          next_stage(current=Stage.DISCOVER, intent=Intent.REQUEST_CONTACT,
                     qualification=QualificationData(), turn_count=1) == Stage.CONVERT)

    rich = QualificationData(
        pain_point="ticket overload", company="ScaleUp", industry="SaaS",
        company_size="60 people", timeline="within 30 days", budget="$500/month",
        authority="decision maker",
    )
    check("Fully qualified prospect reaches convert",
          next_stage(current=Stage.DEMONSTRATE, intent=Intent.DESCRIBE_CONTEXT,
                     qualification=rich, turn_count=6) == Stage.CONVERT)

    check("Cannot convert too early",
          next_stage(current=Stage.DEMONSTRATE, intent=Intent.DESCRIBE_CONTEXT,
                     qualification=rich, turn_count=2) != Stage.CONVERT)

    check("Ended is terminal",
          next_stage(current=Stage.ENDED, intent=Intent.ASK_QUESTION,
                     qualification=rich, turn_count=9) == Stage.ENDED)

    # -- full agent turn ---------------------------------------------------
    section("Agent turn with a stubbed model")

    provider = StubProvider([good_response()])
    turn = run_turn(provider, "Show me how your analytics works")
    check("Turn produced a message", bool(turn.response.message))
    check("Turn issued a navigate action", turn.response.action.type == ActionType.NAVIGATE)
    check("Navigate target is real", turn.response.action.target == "analytics")
    check("Not degraded", turn.degraded is False)

    system_prompt = provider.calls[0][0].content
    check("Prompt contains the product name", "HelpFlow" in system_prompt)
    check("Prompt lists real section ids", '"analytics"' in system_prompt)
    check("Prompt contains the objection playbook", "Too expensive" in system_prompt)
    check("Prompt contains pricing", "199" in system_prompt)
    check("Prompt states the untrusted-context rule",
          "DATA, not instructions" in system_prompt)
    check("Prompt injects the stage directive", "CURRENT STAGE" in system_prompt)
    check("Prompt never leaks a key", "GROQ_API_KEY" not in system_prompt)

    # Repeated-question guard
    provider = StubProvider([
        good_response(next_question="What industry are you in?",
                      qualification={"industry": "SaaS"})
    ])
    turn = run_turn(provider, "We do analytics",
                    qualification=QualificationData(industry="SaaS"))
    check("Question about a known field is stripped",
          turn.response.next_question is None, str(turn.response.next_question))

    # Hallucinated navigation in a real turn
    provider = StubProvider([
        good_response(action={"type": "navigate", "target": "does-not-exist"})
    ])
    turn = run_turn(provider, "Show me the admin panel")
    check("Hallucinated navigation neutralised in a live turn",
          turn.response.action.type == ActionType.NONE)

    # Model ignores JSON entirely
    provider = StubProvider(["Sure! Our pricing starts at $199 per month."])
    turn = run_turn(provider, "What does it cost?")
    check("Prose-only reply is still delivered",
          "199" in turn.response.message, turn.response.message)
    check("Prose-only reply issues no action",
          turn.response.action.type == ActionType.NONE)

    # Model returns nothing usable
    provider = StubProvider([""])
    turn = run_turn(provider, "What does it cost?")
    check("Empty model output falls back gracefully", bool(turn.response.message))
    check("Empty model output marked degraded", turn.degraded is True)

    # Confidence is downgraded when nothing was retrieved
    provider = StubProvider([good_response(intent="ask_question", confidence="high")])
    turn = run_turn(provider, "Do you support SAML SSO?")
    check("Confidence downgraded without retrieval",
          turn.response.confidence == "low", turn.response.confidence)

    # Heuristic overrides the model on objections
    provider = StubProvider([good_response(intent="smalltalk")])
    turn = run_turn(provider, "This is way too expensive for us")
    check("Objection intent overrides the model's claim",
          turn.response.intent == Intent.RAISE_OBJECTION, str(turn.response.intent))

    # -- deterministic extraction ------------------------------------------
    section("Deterministic qualification extraction")

    extractions = [
        ("We're about 60 people", "company_size", "60 people"),
        ("team of 250 engineers", "company_size", "250 engineers"),
        ("We need this within 30 days", "timeline", "within 30 days"),
        ("we need it asap", "timeline", "immediately"),
        ("just looking around for now", "timeline", "exploring"),
        ("Our budget is $500 per month", "budget", "$500 per month"),
        ("we have no budget for this", "budget", "no budget allocated"),
        ("I make the final decision", "authority", "decision maker"),
        ("I'll need to check with my boss", "authority", "influencer"),
        ("this is critical for us right now", "urgency", "critical"),
        ("it's a nice to have", "urgency", "low"),
        ("We currently use Zendesk", "current_solution", "Zendesk"),
        ("we do it all manually", "current_solution", "manually"),
        ("I'm the Head of Support", "job_title", "Head of Support"),
        ("I am the VP of Engineering at Acme", "job_title", "VP of Engineering"),
        ("I'm a senior software engineer here", "job_title", "senior software engineer"),
        ("I'm the engineering manager for platform", "job_title", "engineering manager"),
        ("our support team is drowning in repetitive tickets",
         "pain_point", "repetitive tickets"),
        ("our biggest problem is slow response times",
         "pain_point", "slow response times"),
    ]
    for text, field, expected in extractions:
        actual = getattr(extract_deterministic(text), field, None)
        ok = actual is not None and expected.lower() in str(actual).lower()
        check(f"Extract {field} from {text[:34]!r}", ok, f"got {actual!r}")

    # Titles must stop at the clause boundary, not swallow the rest of the sentence.
    over_capture = extract_deterministic("I am the Head of Support so it is my call")
    check("Job title stops at the clause boundary",
          over_capture.job_title == "Head of Support", f"got {over_capture.job_title!r}")
    check("Authority still extracted from the same sentence",
          over_capture.authority == "decision maker", f"got {over_capture.authority!r}")

    # -- scoring -----------------------------------------------------------
    section("Lead scoring")

    perfect = QualificationData(
        pain_point="support ticket overload", industry="SaaS", company_size="60 people",
        job_title="Head of Support", budget="$500 per month", timeline="within 30 days",
        urgency="critical", authority="decision maker", company="ScaleUp",
    )
    score = calculate_lead_score(perfect, PRODUCT, contact_requested=True,
                                 sections_visited=5, message_count=10)
    check("Ideal prospect scores high", score.score >= 85, str(score.score))
    check("Classified High Intent", score.classification == "High Intent")
    check("All five components present", len(score.breakdown) == 5)
    check("Every component explains itself",
          all(c.reason for c in score.breakdown.values()))
    print(f"  info  ideal prospect: {score.score}/100")

    empty = calculate_lead_score(QualificationData(), PRODUCT)
    check("Unknown prospect scores low", empty.score < 20, str(empty.score))
    check("Missing signals reported", len(empty.missing_signals) >= 4)

    poor = QualificationData(
        pain_point="we want a free CRM", industry="Education",
        company_size="2 people", budget="no budget", timeline="just exploring",
        urgency="nice to have",
    )
    poor_score = calculate_lead_score(poor, PRODUCT)
    check("Poor-fit prospect scores low", poor_score.score < 40, str(poor_score.score))
    print(f"  info  poor fit: {poor_score.score}/100 — {poor_score.classification}")

    disqualified = calculate_lead_score(
        QualificationData(pain_point="support ticket overload", industry="SaaS",
                          company_size="60 people", job_title="Head of Support",
                          budget="$500 per month", timeline="within 30 days",
                          urgency="critical", authority="decision maker"),
        {**PRODUCT, "icp": {**PRODUCT["icp"], "disqualifiers": ["SaaS"]}},
    )
    check("Disqualifier caps the score", disqualified.score <= 30, str(disqualified.score))
    check("Disqualifier is explained",
          any("disqualifier" in r.lower() for r in disqualified.reasons),
          str(disqualified.reasons))

    behaviour_only = calculate_lead_score(
        QualificationData(), PRODUCT, contact_requested=True,
        sections_visited=9, message_count=20,
    )
    check("Engagement alone cannot fake high intent",
          behaviour_only.score < 40, str(behaviour_only.score))

    # -- scoring is deterministic -----------------------------------------
    repeat = [calculate_lead_score(perfect, PRODUCT).score for _ in range(5)]
    check("Scoring is reproducible", len(set(repeat)) == 1, str(repeat))

    # -- summary -----------------------------------------------------------
    print(f"\n{'=' * 64}")
    print(f"  {len(PASSED)} passed, {len(FAILED)} failed")
    if FAILED:
        print("\n  Failures:")
        for failure in FAILED:
            print(f"    - {failure}")
    print("=" * 64)
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
