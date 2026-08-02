<div align="center">

# ◆ DemoPilot

**An AI Sales Engineer that runs your product demos while you sleep.**

Not a chatbot with your docs bolted on — an agent that *drives* an interactive
demo, answers only from your knowledge base, handles objections in your words,
qualifies the prospect conversationally, and leaves a scored lead brief in your
dashboard.

[Quick start](#quick-start) · [How it works](#how-it-works) · [Setup guide](SETUP.md) · [Architecture](ARCHITECTURE.md)

`React` · `Vite` · `Zustand` · `FastAPI` · `Pydantic` · `Groq` · `sentence-transformers` · `FAISS` · `Supabase`

</div>

---

## The problem

You're a technical founder or solopreneur. Prospects land on your site at 2am, in
a timezone you're asleep in, while you're at your day job. They have questions
about integrations, doubts about pricing, and a specific problem they're trying to
solve. A "Book a demo" button asks them to wait a week for a call you may not have
time to take.

Most of them just leave.

## What DemoPilot does

Describe your product once. Every visitor gets a personalised, interactive
walkthrough from an AI Sales Engineer that:

- **Understands their situation first.** Opens with a question, not a pitch.
- **Shows instead of tells.** Returns structured actions that navigate the demo,
  highlight features and open pricing — the prospect watches the product move.
- **Answers only from your knowledge.** Your docs, FAQs, pricing and integrations
  are chunked, embedded and retrieved per question, with sources cited. When the
  answer isn't there it says *"I don't have enough information to confirm that"*
  rather than inventing a capability you'd have to walk back.
- **Handles objections with your playbook.** Not the model's improvisation.
- **Qualifies like a person would.** One question per turn, never repeating what
  it already knows.
- **Hands you a decision.** A transparent score with reasons, a full transcript,
  and a specific recommended next step.

---

## Quick start

Needs Python 3.11+, Node 18+, and a free [Groq API key](https://console.groq.com/keys).

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then set GROQ_API_KEY and JWT_SECRET
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd frontend
npm install && npm run dev
```

Open <http://localhost:5173>. No database to provision — it runs on a local SQLite
file until you point it at Supabase.

Full walkthrough, Supabase setup and deployment: **[SETUP.md](SETUP.md)**.

---

## How it works

### 1 · The AI controls the demo

Every reply is a validated JSON object, never free text:

```json
{
  "message": "Let me show you the analytics dashboard — that's where deflection rate lives.",
  "intent": "request_demo_section",
  "action": { "type": "navigate", "target": "analytics" },
  "qualification": { "industry": "SaaS", "pain_point": "support ticket overload" },
  "confidence": "high"
}
```

The frontend validates the action type against a whitelist **and** the target
against your real section keys before it touches the UI. A hallucinated target
degrades to a no-op instead of breaking the walkthrough. Model output is data,
never code — no `eval`, no dynamic dispatch.

### 2 · A state machine, not a reply loop

A chatbot reacts to the last message. This agent always has a *job*, decided in
Python from observable state — current stage, detected intent, qualification
completeness, turn count:

```
WELCOME → DISCOVER → PERSONALIZE → DEMONSTRATE ⇄ { ANSWER · OBJECTION · QUALIFY } → CONVERT → ENDED
```

The resolved stage becomes a directive in the next prompt. The model picks the
words; the machine picks the purpose. Guardrails live in code rather than in
prompt wishes: at most one question per turn, never re-ask a known field, no
pushing toward a CTA before the prospect has actually had a conversation.

### 3 · Real RAG, grounded in your own material

```
upload → extract → clean & de-inject → chunk → embed (MiniLM) → FAISS
query  → embed → top-k → threshold → dedupe → cited context → Groq
```

Your **structured profile is indexed too** — features, FAQs, pricing plans,
integrations, security notes, objections and case studies each become individually
retrievable documents. So retrieval works before you upload anything, and a
pricing question returns your pricing rows rather than whichever paragraph of a
PDF happened to mention money.

Every answer carries source chips the prospect can see and the founder can audit.

### 4 · Lead scores you can actually defend

Deliberately **not** an LLM call. Ask a model to score the same conversation twice
and you get two answers; deciding how to spend your week needs a number that's
stable and auditable.

| Component | Max | Signal |
|---|---:|---|
| Problem fit | 25 | pain point vs. your ICP pain points and stated problem |
| Urgency | 20 | urgency language, severity, cost of their current workaround |
| Budget fit | 20 | stated budget vs. your ICP range |
| Company fit | 20 | industry + size + title vs. your ICP |
| Buying timeline | 15 | parsed to days, compared to your buying window |

```json
{
  "score": 78,
  "classification": "High Intent",
  "breakdown": {
    "problem_fit": { "points": 25, "max": 25,
      "reason": "Their pain point 'support ticket overload' matches the target pain 'support ticket overload'." }
  },
  "reasons": ["Strong problem fit", "Near-term buying timeline", "Company matches the ICP"],
  "missing_signals": ["budget"]
}
```

Behavioural signals add at most +6, so curiosity can't manufacture a high-intent
lead. Fields never mentioned land in `missing_signals`, which the QUALIFY stage
then targets — *unknown* isn't the same as *bad*, and the dashboard shows the
difference.

### 5 · Uploaded documents are treated as hostile

Two independent defences, because neither is sufficient alone:

1. **At ingestion** — instruction-override patterns are neutralised before storage
   (`ignore all previous instructions`, `you are now a…`, forged `<system>` tags).
2. **At prompt time** — retrieved text is fenced and the system prompt states
   plainly that context is data, never instructions.

---

## What's in the box

**For the founder**

- Product profile: features, pricing plans, integrations, security, FAQs,
  objection playbook, case studies
- Ideal Customer Profile that actually drives scoring
- Demo section builder — the screens the AI can navigate to, with keyword mapping
- Document upload with live ingestion status (PDF · DOCX · MD · TXT · CSV)
- One-click starter walkthrough generated from your profile
- Publish gate with a readiness checklist, and a shareable link
- Dashboard: sessions, prospects, qualified and high-intent counts, conversion
- Lead list with scores and recommended actions
- Lead detail: transcript with every action and source, qualification data, score
  breakdown with reasons, AI brief with a suggested opening line
- Analytics: section engagement, top questions, common objections, score
  distribution, sessions over time

**For the prospect**

- Two-pane demo: product stage on the left, AI Sales Engineer on the right
- AI-driven navigation and feature highlighting
- Source-cited answers with visible confidence
- Pricing, FAQ and integrations panels
- Natural qualification — no upfront form
- Contact capture pre-filled with what the AI already learned

---

## Architecture

```
frontend/src/
  components/  ui · editor/* · demo/*        pages/  console + public demo
  layouts/     console shell                 store/  auth · demo runtime
  services/    apiClient (single HTTP entry) styles/ base · app · demo

backend/app/
  api/routes/   auth · products · sections · documents · demo · demo_ws · leads · analytics
  core/         config · errors · security · rate_limit · logging
  models/       domain shapes (product, qualification, scoring)
  schemas/      API request/response contracts
  services/     product · document · demo · lead · lead_scoring · analytics · auth
  ai_services/  llm/ (provider protocol → Groq) · agents/ · prompts/
                structured_outputs/ · memory/ · state_machine.py
  database/     Database protocol → SQLiteDatabase | SupabaseDatabase

backend/rag/
  ingestion/    extractors · cleaner · chunker · profile_docs
  embeddings/   MiniLM + local fallback
  vector_store/ FAISS + NumPy fallback
  pipeline.py   ingest · index · retrieve · cite
```

Two service layers on purpose: `services/` is business logic that would exist if
the AI were a human; `ai_services/` is everything that knows about models,
prompts, retrieval and agent state. Prompt changes never touch scoring.

Full detail in **[ARCHITECTURE.md](ARCHITECTURE.md)**.

---

## Degrades instead of breaking

| Unavailable | Behaviour |
|---|---|
| Groq | Deterministic replies that quote retrieved knowledge rather than invent answers; the UI says so honestly |
| `sentence-transformers` | Local hashing + char-n-gram vectoriser with its own relevance floor |
| `faiss` | NumPy brute-force cosine search, identical interface |
| Supabase | SQLite via the same repository protocol |

`GET /api/health` reports exactly which path is live, and the console surfaces
configuration problems as a banner instead of letting you discover them mid-demo.

---

## Security

- API keys are server-side only and never reach a prompt, a log line or a response
- Every founder route re-checks product ownership; RLS on all 9 Supabase tables as
  defence in depth
- Public demo config excludes founder-only data — ICP, qualification criteria and
  the objection playbook never leave the server
- Upload validation: extension allowlist, magic-byte sniffing, size and page caps
- Prompt-injection scrubbing at ingestion plus delimiter isolation at prompt time
- Tolerant-but-strict LLM parsing: syntax repaired, Pydantic decides validity,
  invalid actions downgraded, frontend re-validates
- Token-bucket rate limiting per IP on public routes and uploads
- PBKDF2-HMAC-SHA256 password hashing, or delegated Supabase Auth

---

## Tests

Both suites run without a Groq key.

```bash
cd backend
python -m tests.test_smoke    # 71 checks — full founder → prospect → lead workflow
python -m tests.test_agent    # 83 checks — AI layer against a stubbed model
```

`test_smoke` drives the real API through auth, tenant isolation, ingestion,
retrieval, injection scrubbing, a five-turn conversation, scoring, contact
capture, reporting and analytics — on a throwaway database.

`test_agent` stubs the LLM to assert what a live model makes non-deterministic:
hallucinated navigation is rejected, prose-only replies still land, confidence
drops when retrieval finds nothing, scoring is reproducible, and no key ever
reaches a prompt.

---

## Roadmap

Deliberately not built until the core loop is solid: AI avatars, video generation,
CRM and calendar integrations, automated email follow-up, multi-tenant enterprise
architecture.

---

<div align="center">
<sub>Built to run on free tiers — Groq inference, local embeddings, FAISS, Supabase.</sub>
</div>
