# DemoPilot — Technical Architecture

> **AI Sales Engineer + Interactive Product Demonstrator + Lead Qualification Agent**
>
> An asynchronous demo runtime. A founder describes a product once; every prospect who
> opens the public link gets a personalised, AI-driven walkthrough that answers grounded
> questions, handles objections, qualifies them, and produces a lead intelligence report.

---

## 1. System overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             BROWSER                                      │
│                                                                          │
│  Founder console (/app/*)              Public demo (/d/:slug)            │
│  ─ product profile editor              ─ demo stage (sections)           │
│  ─ ICP + qualification config          ─ AI sales engineer chat panel    │
│  ─ demo section builder                ─ action executor (navigate /     │
│  ─ document upload                        highlight / pricing / faq …)   │
│  ─ lead list + lead detail             ─ contact capture                 │
│  ─ analytics                                                             │
│                                                                          │
│  React 18 · Vite · React Router 6 · Zustand · custom CSS                 │
└───────────────┬──────────────────────────────┬───────────────────────────┘
                │ REST (JSON, Bearer JWT)      │ WebSocket  /ws/demo/{sid}
                ▼                              ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                        FastAPI backend (Python 3.11+)                    │
│                                                                          │
│  api/routes ── auth · products · sections · documents · demo · chat_ws   │
│                · leads · analytics                                       │
│       │                                                                  │
│       ▼                                                                  │
│  services/            (application + business logic)                     │
│    product_service · document_service · demo_service                     │
│    conversation_service · qualification_service                          │
│    lead_scoring_service · analytics_service                              │
│       │                                                                  │
│       ▼                                                                  │
│  ai_services/         (AI orchestration — reusable AI capability layer)  │
│    llm/       LLMProvider protocol → GroqProvider (OpenAI-compatible)    │
│    agents/    SalesEngineerAgent · QualificationAgent · LeadReportAgent  │
│    prompts/   versioned system/user prompt builders                      │
│    structured_outputs/  Pydantic response schemas + tolerant JSON parser │
│    memory/    ConversationMemory (rolling window + running summary)      │
│    state_machine.py     8-stage demo conversation FSM                    │
│       │                                                                  │
│       ▼                                                                  │
│  rag/     ingestion (extract→clean→chunk) · embeddings · vector_store    │
│       │                                                                  │
│       ▼                                                                  │
│  database/  repository protocol → SupabaseRepository | SQLiteRepository  │
└───────────────┬─────────────────────────┬────────────────────────────────┘
                │                         │
                ▼                         ▼
      ┌──────────────────┐      ┌───────────────────────┐
      │ Supabase         │      │  Local disk           │
      │ (Postgres+Auth)  │      │  data/faiss/*.index   │
      │  — or local      │      │  data/uploads/*       │
      │    SQLite file   │      │  MiniLM model cache   │
      └──────────────────┘      └───────────────────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  Groq API        │
                                   │  (server-side    │
                                   │   only)          │
                                   └──────────────────┘
```

### Design rules baked into the layout

| Rule | How it is enforced |
|---|---|
| LLM provider swappable | Everything goes through `ai_services/llm/base.py::LLMProvider`. `GroqProvider` is one implementation; the model id comes from `GROQ_MODEL`. |
| No API keys in the browser | The frontend never sees `GROQ_API_KEY`. All model calls happen in the FastAPI process. |
| Nothing product-specific hardcoded | Every product fact — features, pricing, FAQs, objections, ICP, demo sections — is founder-supplied data read from the DB at request time. |
| Runs locally with zero cloud deps | `DB_BACKEND=sqlite` + local auth + local embeddings means the whole stack runs offline apart from Groq. |
| Untrusted uploads | Document text is sanitised, wrapped in delimiters, and the system prompt states that retrieved context is *data, never instructions*. |

---

## 2. Database schema

Postgres (Supabase) is the reference. The SQLite backend mirrors it with `TEXT` in
place of `uuid`/`jsonb`. The full runnable DDL lives in
[`supabase/schema.sql`](supabase/schema.sql); this section explains the model.

```
founders ─┬─< products ─┬─< product_documents ──< document_chunks
          │             ├─< demo_sections
          │             └─< demo_sessions ─┬─< demo_messages
          │                    │           └─< demo_events
          │                    └── prospects (1:1 optional)
          └──────────────────────────────────────┘
```

| Table | Purpose | Key columns |
|---|---|---|
| `founders` | Account record. Mirrors `auth.users.id` when Supabase Auth is on; holds `password_hash` only in local-auth mode. | `id`, `email` (unique), `full_name` |
| `products` | The product profile + ICP + published state. All rich fields are JSON so the founder can add features/FAQs/objections without migrations. | `slug` (unique, powers the public link), `features`, `faqs`, `objections`, `pricing`, `integrations`, `icp`, `is_published` |
| `product_documents` | Upload metadata + ingestion status (`pending`→`processing`→`indexed`/`failed`). | `filename`, `status`, `chunk_count`, `error` |
| `document_chunks` | Durable copy of every chunk with its metadata. FAISS stores only vectors; the text lives here so the index can always be rebuilt and so retrieved sources can be cited. | `chunk_index`, `content`, `source_label`, `token_estimate` |
| `demo_sections` | The interactive stage. Each row is a navigable screen the AI can drive. | `section_key` (AI action target), `title`, `description`, `feature_explanation`, `keywords[]`, `visual_placeholder`, `order_index` |
| `prospects` | Identity, collected conversationally. Created lazily the first time the AI learns a name/email. | `name`, `email`, `company`, `job_title`, `industry`, `company_size` |
| `demo_sessions` | One prospect visit. Holds live qualification state, the latest lead score, and the generated report. | `qualification`, `lead_score`, `report`, `stage`, `duration_seconds`, `contact_requested` |
| `demo_messages` | Full transcript, including the structured action and RAG sources attached to each assistant turn. | `role`, `content`, `action`, `sources`, `intent` |
| `demo_events` | Analytics event stream. | `event_type` ∈ `section_view, question_asked, objection_raised, cta_clicked, contact_submitted, session_started, session_ended` |

Row Level Security is enabled on every table. Founder-owned rows are readable only by
their owner; the backend uses the **service role** key and enforces ownership in code,
so the anon key can never reach another founder's data.

---

## 3. API surface

All routes are prefixed `/api`. Founder routes require `Authorization: Bearer <jwt>`.
Prospect routes are public but rate-limited and scoped to a session id.

### Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | email + password + name → token |
| POST | `/auth/login` | → token |
| GET | `/auth/me` | current founder |

### Products (founder)
| Method | Path |
|---|---|
| GET / POST | `/products` |
| GET / PUT / DELETE | `/products/{product_id}` |
| POST | `/products/{product_id}/publish` — toggles `is_published`, returns the demo URL |
| GET | `/products/{product_id}/knowledge-status` — index health, chunk counts |

### Demo sections (founder)
| Method | Path |
|---|---|
| GET / POST | `/products/{product_id}/sections` |
| PUT / DELETE | `/products/{product_id}/sections/{section_id}` |
| POST | `/products/{product_id}/sections/seed` — generate a starter set from the product profile |

### Documents (founder)
| Method | Path |
|---|---|
| POST | `/products/{product_id}/documents` (multipart) — validated, ingested in a background task |
| GET | `/products/{product_id}/documents` |
| DELETE | `/products/{product_id}/documents/{document_id}` |
| POST | `/products/{product_id}/documents/reindex` — rebuild the FAISS index from `document_chunks` + the structured profile |

### Public demo (prospect)
| Method | Path |
|---|---|
| GET | `/demo/{slug}` — public product config + ordered sections (never returns founder data) |
| POST | `/demo/{slug}/sessions` — start a session, returns `session_id` + the AI's opening turn |
| POST | `/demo/sessions/{session_id}/messages` — REST turn (WebSocket fallback) |
| POST | `/demo/sessions/{session_id}/events` — section views, CTA clicks |
| POST | `/demo/sessions/{session_id}/contact` — contact capture |
| POST | `/demo/sessions/{session_id}/end` — finalise, trigger report generation |
| WS | `/ws/demo/{session_id}` — streaming turn: `status` → `token`* → `final` |

### Leads + analytics (founder)
| Method | Path |
|---|---|
| GET | `/dashboard/overview?product_id=` |
| GET | `/leads?product_id=&min_score=&intent=` |
| GET | `/leads/{session_id}` — transcript, qualification, score breakdown, report |
| POST | `/leads/{session_id}/report` — (re)generate the AI lead report |
| GET | `/analytics?product_id=` — sections, questions, objections, score distribution |

---

## 4. Frontend routes

| Route | Screen |
|---|---|
| `/` | Landing / value prop, links to login |
| `/login`, `/register` | Founder auth |
| `/app` | Overview: prospects, sessions, qualified, high-intent, conversion rate |
| `/app/products` | Product list |
| `/app/products/new` | Create product |
| `/app/products/:id` | Editor with tabs: **Profile · ICP · Demo Sections · Knowledge · Share** |
| `/app/leads` | Lead list, sortable + filterable |
| `/app/leads/:sessionId` | Lead detail: transcript, qualification, score breakdown, AI report |
| `/app/analytics` | Section engagement, top questions, objections, score distribution |
| `/d/:slug` | **Public demo** — stage + AI sales engineer |

State: three Zustand stores — `authStore` (token/session), `builderStore` (product being
edited), `demoStore` (public demo runtime: messages, active section, highlights, actions).

---

## 5. Core Pydantic models

```python
# ai_services/structured_outputs/schemas.py

class ActionType(str, Enum):
    navigate = "navigate"; highlight = "highlight"; open_pricing = "open_pricing"
    show_faq = "show_faq"; show_integration = "show_integration"
    request_contact = "request_contact"; end_demo = "end_demo"; none = "none"

class DemoAction(BaseModel):
    type: ActionType = ActionType.none
    target: str | None = None          # must match a real section_key / faq id
    label: str | None = None

class QualificationData(BaseModel):
    name/email/company/job_title/industry/company_size: str | None
    pain_point/current_solution/budget/timeline/authority/urgency: str | None
    # every field optional — the AI fills them in over time, never interrogates

class Intent(str, Enum):
    greeting, describe_context, request_demo_section, ask_question,
    ask_pricing, raise_objection, request_contact, smalltalk, end

class AgentResponse(BaseModel):        # ← what the LLM must return
    message: str
    intent: Intent
    action: DemoAction
    qualification: QualificationData
    next_question: str | None
    used_context: bool                 # did it rely on retrieved knowledge
    confidence: Literal["high","medium","low"]

class LeadScore(BaseModel):
    score: int; classification: Literal["Low Intent","Medium Intent","High Intent"]
    breakdown: dict[str, ScoreComponent]   # component → {points, max, reason}
    reasons: list[str]
```

`AgentResponse` is what the model returns. The server then **recomputes** `lead_score`
deterministically (§7) — the LLM is never trusted to produce the number.

---

## 6. AI agent state machine

```
                 ┌──────────┐
   session start │ WELCOME  │  opening turn, no prospect input yet
                 └────┬─────┘
                      │ first prospect message
                 ┌────▼─────┐
      ┌─────────►│ DISCOVER │  learn company, role, problem, current tool
      │          └────┬─────┘
      │               │ pain_point OR industry known
      │          ┌────▼───────┐
      │          │ PERSONALIZE│  rank demo sections against the prospect's context
      │          └────┬───────┘
      │               │ relevant sections chosen
      │          ┌────▼────────┐
      │  ┌──────►│ DEMONSTRATE │  navigate/highlight, explain the feature
      │  │       └────┬────────┘
      │  │            │
      │  │   ┌────────┼─────────┐
      │  │   ▼        ▼         ▼
      │  │ ┌──────┐ ┌─────────┐ ┌────────┐
      │  └─┤ANSWER│ │OBJECTION│ │QUALIFY │  ← intent-driven, freely interleaved
      │    └──┬───┘ └────┬────┘ └───┬────┘
      │       └──────────┼──────────┘
      └──────────────────┤ missing critical qualification fields
                         │ enough signal collected / prospect signals intent
                    ┌────▼───┐
                    │ CONVERT│  recommend the CTA, request contact
                    └────┬───┘
                         ▼
                    ┌────────┐
                    │ ENDED  │  finalise score, generate lead report
                    └────────┘
```

Transitions are computed server-side each turn from `(current_stage, detected_intent,
qualification_completeness, turn_count)` — not by the LLM. The resolved stage is injected
into the next system prompt as a *directive* ("you are in the QUALIFY stage; weave at most
one natural question into your reply"). This is what keeps the agent from degenerating
into a chatbot: it always has a job for the current turn.

Guardrails encoded in the FSM:
- Never ask more than one qualification question per turn.
- Never re-ask a field already present in `QualificationData`.
- Cannot enter `CONVERT` before at least 4 prospect turns unless the prospect asks.
- `action.target` is validated against real `section_key`s; unknown targets degrade to `none`.

---

## 7. Lead scoring (deterministic + explainable)

Computed in `services/lead_scoring_service.py` from the session's `QualificationData`
matched against the product's ICP. No LLM involvement in the arithmetic.

| Component | Max | Signal |
|---|---|---|
| Problem fit | 25 | pain point present + semantic overlap with ICP pain points / product problem |
| Urgency | 20 | explicit urgency language, severity words, current workaround pain |
| Budget fit | 20 | stated budget vs. ICP budget range; "no budget" scores 0 with a reason |
| Company fit | 20 | industry ∈ ICP industries, size ∈ ICP sizes, job title ∈ ICP titles |
| Buying timeline | 15 | ≤30 days = full, ≤90 = partial, "exploring" = low |

Output is always the full breakdown:

```json
{ "score": 78, "classification": "High Intent",
  "breakdown": { "problem_fit": {"points": 22, "max": 25, "reason": "Pain point 'support ticket overload' matches ICP pain point 'high support volume'"}, … },
  "reasons": ["Strong problem fit", "Timeline within 30 days", "Company size matches ICP"],
  "missing_signals": ["budget"] }
```

`missing_signals` feeds straight back into the QUALIFY stage — the agent asks about what
is actually missing rather than running a fixed script.

---

## 8. RAG pipeline

```
 upload ──► validate (ext, mime, size, page cap)
        ──► extract    pdf (pypdf) | docx (python-docx) | md/txt/csv (native)
        ──► clean      normalise whitespace, drop control chars,
                       strip prompt-injection patterns, cap length
        ──► chunk      ~900 chars, 150 overlap, sentence-boundary aware
        ──► metadata   {document_id, filename, chunk_index, source_label, product_id}
        ──► embed      sentence-transformers all-MiniLM-L6-v2 (384-d, normalised)
        ──► index      FAISS IndexFlatIP, one index per product, persisted to disk
        ──► persist    chunk text + metadata → document_chunks (rebuild source of truth)

 query  ──► embed ──► FAISS top-k (k=6) ──► score threshold ──► dedupe by document
        ──► build a delimited, numbered context block with source labels
        ──► Groq generates a grounded answer citing [S1], [S2] …
        ──► server maps citations back to source metadata for the UI
```

**The structured product profile is indexed too.** Features, FAQs, pricing, integrations,
security notes, objection responses and case studies are each rendered into a synthetic
document (`source_label: "Product profile → FAQ"`), so RAG works on day one before any
file is uploaded — and pricing questions retrieve pricing rows, not random prose.

**Graceful degradation:** if `sentence-transformers`/`faiss-cpu` are unavailable, the
embedder falls back to a deterministic local hashing + character-n-gram vectoriser and the
store falls back to NumPy brute-force cosine search. Same interface, no cloud calls, so a
constrained machine still gets a working demo.

**Anti-hallucination:** the system prompt states that context is untrusted data; the model
must answer only from it for factual product claims, must say *"I don't have enough
information to confirm that"* otherwise, and must set `confidence: "low"` when retrieval
returned nothing above threshold.

---

## 9. Security model

- `GROQ_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET` are server-only env vars.
- Passwords hashed with PBKDF2-HMAC-SHA256 (local mode) or delegated to Supabase Auth.
- Every founder route re-checks `product.founder_id == current_founder.id`.
- Upload validation: extension allowlist, MIME sniff, 10 MB cap, page/char caps.
- Prompt-injection scrubbing on ingested text + delimiter isolation at prompt time.
- Tolerant-but-strict LLM output parsing: JSON extracted, validated by Pydantic, invalid
  actions downgraded to `none`. The frontend re-validates the action against a whitelist
  before executing. No `eval`, no dynamic imports, no HTML injection from model output.
- Token-bucket rate limiting per IP on public demo routes and per founder on uploads.

---

## 10. Implementation plan

| Phase | Deliverable | Verified by |
|---|---|---|
| 1 | Config, DB abstraction (Supabase + SQLite), auth, FastAPI app, Vite app, health wiring | `/api/health` green, login round-trip |
| 2 | Product profile + ICP + sections CRUD, upload → extract → chunk → embed → FAISS | Upload a PDF, see chunks indexed, search returns them |
| 3 | Groq provider, prompts, structured outputs, memory, sales engineer agent, RAG answers | Chat turn returns valid `AgentResponse` grounded in sources |
| 4 | Demo stage UI, action executor, section navigation + highlighting, WebSocket streaming | "Show me analytics" navigates the stage |
| 5 | Qualification extraction/merge, deterministic scoring, classification, missing-signal loop | Score + breakdown update live during a conversation |
| 6 | Dashboard overview, lead list, lead detail, AI report, analytics | Full lead visible after a demo session |
| 7 | Error/loading/empty states, responsive CSS, rate limits, README + SETUP.md | End-to-end walkthrough from §17 of the brief |
