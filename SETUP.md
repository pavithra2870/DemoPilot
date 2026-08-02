# DemoPilot — Setup Guide

Everything needed to run DemoPilot locally, understand how it fits together, and
deploy it on free tiers.

- [1. Prerequisites](#1-prerequisites)
- [2. Quick start (5 minutes, SQLite)](#2-quick-start-5-minutes-sqlite)
- [3. Getting a Groq API key](#3-getting-a-groq-api-key)
- [4. Switching to Supabase](#4-switching-to-supabase)
- [5. Every environment variable](#5-every-environment-variable)
- [6. Using the product end to end](#6-using-the-product-end-to-end)
- [7. Architecture notes](#7-architecture-notes)
- [8. Running the tests](#8-running-the-tests)
- [9. Troubleshooting](#9-troubleshooting)
- [10. Deployment](#10-deployment)

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | Tested on 3.12 |
| Node.js | 18+ | Tested on 20 |
| Groq API key | free | [console.groq.com/keys](https://console.groq.com/keys) |
| Supabase project | free, optional | Only if you want hosted Postgres |

Disk: about 500 MB, mostly the sentence-transformers model and its torch dependency.

---

## 2. Quick start (5 minutes, SQLite)

No cloud services except Groq. The database is a local file.

### Backend

```bash
cd backend

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env          # Windows: copy .env.example .env
```

Open `backend/.env` and set two values:

```ini
GROQ_API_KEY=gsk_your_key_here
JWT_SECRET=any-long-random-string-you-invent
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Check it: <http://localhost:8000/api/health> should return `"status": "ok"` with an
empty `warnings` array.

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

> The Vite dev server proxies `/api` and `/ws` to `localhost:8000`, so there is
> nothing to configure locally — no CORS, no `VITE_API_URL`.

### First run notes

- The **first document upload or profile save** downloads the embedding model
  (~90 MB) and takes 10–30 seconds. Every later operation is fast. Watch the
  backend log for `Embedding model ready`.
- `backend/data/` is created automatically and holds the SQLite database, uploaded
  files and FAISS indexes. It is gitignored.

---

## 3. Getting a Groq API key

1. Sign up at <https://console.groq.com> (free, no card).
2. **API Keys** → **Create API Key**, copy it.
3. Put it in `backend/.env` as `GROQ_API_KEY`.
4. Restart the backend.

### Choosing a model

`GROQ_MODEL` defaults to `llama-3.3-70b-versatile`, which follows the structured
JSON contract reliably. If your key does not have access to it, check
<https://console.groq.com/docs/models> and set any instruction-following model:

```ini
GROQ_MODEL=llama-3.1-8b-instant       # faster, cheaper, slightly less consistent JSON
```

Nothing else needs to change — the provider is abstracted behind
`app/ai_services/llm/base.py`.

### Without a key

DemoPilot still runs. Every AI call falls back to a deterministic response, and
the demo UI shows an honest "the AI model is unreachable" notice. RAG retrieval,
qualification extraction, lead scoring, the dashboard and analytics all keep
working — they do not depend on the LLM. Useful for developing UI without burning
quota.

---

## 4. Switching to Supabase

### 4.1 Create the project

1. <https://supabase.com> → **New project** (free tier).
2. Choose a region near you and save the database password.

### 4.2 Run the schema

1. Supabase dashboard → **SQL Editor** → **New query**.
2. Open [`supabase/schema.sql`](supabase/schema.sql) from this repo, paste the
   **entire file**, and press **Run**.
3. You should see a result table listing 9 tables:

   ```
   demo_events, demo_messages, demo_sections, demo_sessions,
   document_chunks, founders, product_documents, products, prospects
   ```

The script is idempotent — re-running it is safe and is how you apply updates.

**What it creates**

- 9 tables with foreign keys and `on delete cascade`, so deleting a product
  removes its documents, chunks, sections, sessions, messages and events.
- Indexes on every foreign key plus a `(product_id, last_activity_at desc)` index
  for the lead list.
- Row Level Security enabled on all 9 tables, with owner-scoped policies and an
  `owns_product()` helper so child tables inherit ownership through `products`.

### 4.3 Get your keys

Dashboard → **Project Settings** → **API**:

| Dashboard label | `.env` variable |
|---|---|
| Project URL | `SUPABASE_URL` |
| `service_role` secret | `SUPABASE_SERVICE_ROLE_KEY` |
| `anon` public | `SUPABASE_ANON_KEY` |

> The **service role key bypasses RLS**. It belongs only in `backend/.env`, never
> in the frontend and never in a commit. The backend enforces ownership in code
> (`app/api/deps.py::owned_product`); RLS is defence in depth so a leaked anon key
> reaches nothing.

### 4.4 Point the backend at it

```ini
DB_BACKEND=supabase
SUPABASE_URL=https://yourproject.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
SUPABASE_ANON_KEY=eyJhbGci...
```

Restart. `/api/health` should show `"backend": "supabase", "ok": true`.

### 4.5 Optional: Supabase Auth instead of local JWT

```ini
AUTH_BACKEND=supabase
```

Sign-up and sign-in are then delegated to Supabase Auth, and the returned user id
becomes `founders.id` so RLS policies line up. DemoPilot still issues its own
short-lived JWT for API calls, so the rest of the API has a single auth path.

Requires `DB_BACKEND=supabase` as well. Leave `AUTH_BACKEND=local` if you want
zero-config auth.

### What stays local either way

FAISS indexes and uploaded files live on the backend's disk (`data/faiss`,
`data/uploads`). Chunk **text** is stored in the database, so the index is always
rebuildable — if you redeploy onto fresh disk, hit **Rebuild index** on the
Knowledge tab and everything is restored.

---

## 5. Every environment variable

### `backend/.env`

| Variable | Default | What it does |
|---|---|---|
| `GROQ_API_KEY` | — | **Required for AI replies.** Server-side only. |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Any Groq instruction model. |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | OpenAI-compatible endpoint. |
| `GROQ_TIMEOUT_SECONDS` | `60` | Per-request timeout. |
| `GROQ_MAX_TOKENS` | `1200` | Cap per reply. |
| `GROQ_TEMPERATURE` | `0.4` | Low enough to keep JSON well-formed. |
| `DB_BACKEND` | `sqlite` | `sqlite` or `supabase`. |
| `SQLITE_PATH` | `data/demopilot.db` | Local database file. |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_ANON_KEY` | — | Required when `DB_BACKEND=supabase`. |
| `AUTH_BACKEND` | `local` | `local` or `supabase`. |
| `JWT_SECRET` | `change-me…` | **Set this.** Signs founder tokens. |
| `JWT_EXPIRE_MINUTES` | `10080` | 7 days. |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | 384-dim, runs on CPU. |
| `EMBEDDING_DEVICE` | `cpu` | Set `cuda` if you have a GPU. |
| `RAG_CHUNK_SIZE` | `900` | Characters per chunk. |
| `RAG_CHUNK_OVERLAP` | `150` | Overlap between chunks. |
| `RAG_TOP_K` | `6` | Chunks retrieved per query. |
| `RAG_MIN_SCORE` | `0.18` | Relevance floor. Raise for stricter grounding. |
| `DATA_DIR` / `UPLOAD_DIR` / `FAISS_DIR` | `data/*` | Storage paths. |
| `MAX_UPLOAD_MB` | `10` | Per-file limit. |
| `ALLOWED_UPLOAD_EXTENSIONS` | `.pdf,.docx,.txt,.md,.csv` | Extension allowlist. |
| `APP_ENV` | `development` | `production` enables stricter config warnings. |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose agent logs. |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated. Add your deployed frontend. |
| `PUBLIC_APP_URL` | `http://localhost:5173` | Used to build demo links. **Set in production.** |
| `RATE_LIMIT_ENABLED` | `true` | Token-bucket limiting. |
| `PUBLIC_RATE_LIMIT_PER_MINUTE` | `30` | Per IP, on public demo routes. |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | Per IP, on uploads. |

### `frontend/.env`

| Variable | Default | What it does |
|---|---|---|
| `VITE_API_URL` | empty | Leave empty locally (Vite proxies). Set to your API origin in production. |

---

## 6. Using the product end to end

### As the founder

1. **Register** at <http://localhost:5173/register>.
2. **Products → + New product.** Fill in name, tagline, what it does, who it's
   for, and the problem it solves. Create.
3. **Profile tab.** Add features, pricing plans, integrations, security notes,
   FAQs and — importantly — your **objection playbook**. Each entry becomes
   retrievable knowledge, so the AI answers with your words rather than
   improvising. Click **Save changes**; this also rebuilds the search index.
4. **Ideal customer tab.** Industries, company sizes, job titles, pain points and
   a budget range. This is what every lead score is measured against — an empty
   ICP makes scores far less meaningful. Set the call to action here too.
5. **Demo sections tab.** Click **Generate from profile** to get a starter
   walkthrough built from what you already entered, then edit it. Each section's
   **id** is what the AI targets in a `navigate` action, and its **keywords** are
   how it maps a prospect's words to a screen.
6. **Knowledge tab.** Optionally upload PDFs, DOCX, Markdown, text or CSV. Watch
   the status go `pending → processing → indexed`. Your profile is already
   indexed, so this is for depth, not to get started.
7. **Share tab.** Fix anything in the readiness checklist, click **Publish demo**,
   and copy the link.

### As a prospect

Open the demo link (or the **Preview demo** button):

1. Click **Start the demo** — the AI opens with a question, not a pitch.
2. Say something real: *"We're a 60 person SaaS company and our support team is
   drowning in repetitive tickets."*
3. Watch the left pane. The AI navigates to the section it judges most relevant.
4. Ask questions. Answers are grounded in the knowledge base and cite their
   sources as chips under each reply.
5. Push back — *"that's too expensive"* — and it uses your objection playbook.
6. Notice it asks at most one question per turn and never repeats itself.
7. Click the call-to-action button to leave contact details.

### Back as the founder

**Overview** shows sessions, prospects, qualified and high-intent counts.
**Leads** lists everyone with a score and a recommended action.
**Lead detail** gives you the full transcript with every action and source the AI
used, the qualification data, the five-component score breakdown with reasons,
and — after clicking **Generate brief** — an AI summary with a specific next step
and a suggested opening line.
**Analytics** shows which sections prospects visit, what they ask, what they
object to, and how scores are distributed.

---

## 7. Architecture notes

Full detail in [`ARCHITECTURE.md`](ARCHITECTURE.md). The decisions worth knowing:

### The AI controls the demo

Every reply is a validated JSON object, not free text:

```json
{
  "message": "Let me show you the analytics dashboard.",
  "intent": "request_demo_section",
  "action": { "type": "navigate", "target": "analytics" },
  "qualification": { "industry": "SaaS", "pain_point": "ticket overload" },
  "confidence": "high"
}
```

The frontend's `executeAction` (in `frontend/src/store/demoStore.js`) validates
the type against a whitelist **and** the target against the founder's real section
keys before touching the UI. A hallucinated target degrades to no-op rather than
breaking the demo. Supported actions: `navigate`, `highlight`, `open_pricing`,
`show_faq`, `show_integration`, `request_contact`, `end_demo`, `none`.

### A state machine, not a chatbot

`app/ai_services/state_machine.py` decides each turn's *job* in Python from
`(current stage, detected intent, qualification completeness, turn count)`:

```
WELCOME → DISCOVER → PERSONALIZE → DEMONSTRATE ⇄ {ANSWER, OBJECTION, QUALIFY} → CONVERT → ENDED
```

The resolved stage is injected into the system prompt as a directive. The model
chooses the words; the machine chooses the purpose. Guardrails live in code, not
in prompt wishes: at most one question per turn, never re-ask a known field,
cannot reach `CONVERT` before four prospect turns unless they ask.

### Your profile is indexed, not just prompted

`rag/ingestion/profile_docs.py` renders features, FAQs, pricing plans,
integrations, security notes, objections, case studies and demo sections into
individually retrievable documents labelled `Product profile → FAQ` and similar.
So RAG works before any upload, and a pricing question retrieves your pricing
rows rather than whichever paragraph of a PDF mentioned money.

### Scores are computed, not generated

`app/services/lead_scoring_service.py` is deliberately LLM-free. Ask a model to
score the same conversation twice and you get two answers; a founder deciding how
to spend their week needs a number that is stable and auditable.

| Component | Max | Signal |
|---|---|---|
| Problem fit | 25 | pain point vs. ICP pain points and the product's stated problem |
| Urgency | 20 | urgency language, severity, cost of the current workaround |
| Budget fit | 20 | stated budget vs. the ICP range |
| Company fit | 20 | industry + size + title vs. the ICP |
| Buying timeline | 15 | parsed into days and compared to your buying window |

0–39 Low · 40–69 Medium · 70–100 High. Behavioural signals (contact requested,
sections explored, long conversation) add at most +6, so curiosity alone cannot
manufacture a high-intent lead. Fields never mentioned appear in
`missing_signals`, which the QUALIFY stage then targets — unknown is not the same
as bad, and the dashboard shows the difference.

### Uploaded documents are untrusted

Two independent defences, because neither alone is enough:

1. **At ingestion** — `rag/ingestion/cleaner.py` neutralises instruction-override
   patterns ("ignore all previous instructions", "you are now a…", fake
   `<system>` tags) before anything is stored.
2. **At prompt time** — retrieved text is fenced in
   `<<<KNOWLEDGE_BASE_START>>>` / `<<<KNOWLEDGE_BASE_END>>>` and the system
   prompt states that context is data, never instructions.

### Model output is never trusted

`app/ai_services/structured_outputs/parser.py` repairs *syntax* only — code
fences, prose wrappers, trailing commas — then hands the result to Pydantic,
which is the sole authority on acceptability. It uses `json.loads`; never `eval`,
never `literal_eval`. If validation fails, the offending fields are dropped and
defaults apply, so one malformed field does not lose the whole reply.

### Graceful degradation everywhere

| If this is unavailable | What happens |
|---|---|
| Groq | Deterministic fallback replies that quote retrieved knowledge instead of inventing answers; the UI says so honestly |
| `sentence-transformers` | Local hashing + char-n-gram vectoriser, with its own relevance floor |
| `faiss` | NumPy brute-force cosine search, same interface |
| `numpy` | Pure-Python dot product |
| Supabase | SQLite with an identical repository interface |

`/api/health` reports which path is live.

### Two service layers

`app/services/` is business logic that would still exist if the AI were replaced
by a human: ownership, persistence, scoring arithmetic, analytics.
`app/ai_services/` is everything that knows about models, prompts, retrieval and
agent state. The split is what keeps prompt changes from touching scoring, and
scoring changes from touching prompts.

---

## 8. Running the tests

Both suites run without a Groq key.

```bash
cd backend

# Full founder → prospect → lead workflow against the real API (71 checks)
python -m tests.test_smoke

# The AI layer with a stubbed model: parsing, sanitisation, state machine,
# extraction, scoring (83 checks)
python -m tests.test_agent
```

`test_smoke` uses a throwaway temp database, so it never touches your dev data.
It covers auth, tenant isolation, product CRUD, upload validation, ingestion,
retrieval, prompt-injection scrubbing, publishing, a five-turn conversation,
qualification extraction, scoring, contact capture, report generation, the
dashboard and analytics.

`test_agent` injects a fake LLM provider so it can assert on things a live model
makes non-deterministic: that hallucinated navigation targets are rejected, that
a prose-only reply is still delivered, that confidence is downgraded when nothing
was retrieved, that scoring is reproducible, and that no API key ever reaches a
prompt.

Frontend build check:

```bash
cd frontend && npm run build
```

---

## 9. Troubleshooting

**`GROQ_API_KEY is not set` banner in the console**
Expected without a key. Add it to `backend/.env` and restart. Everything except
AI-generated replies works meanwhile.

**`Groq does not recognise the model '…'`**
Your key lacks access to `GROQ_MODEL`. Pick one from
<https://console.groq.com/docs/models>.

**First save or upload takes 30 seconds**
The embedding model is downloading (~90 MB, once). The log shows
`Loading embedding model…` then `Embedding model ready (dim=384)`.

**`/api/health` shows `"embedder": {"semantic": false}` or backend `numpy`**
`sentence-transformers` or `faiss-cpu` failed to install, so the local fallbacks
took over. The demo works but retrieval is lexical rather than semantic. Fix with
`pip install sentence-transformers faiss-cpu`, then click **Rebuild index**.

**Frontend can't reach the API**
Confirm the backend is on port 8000. Locally leave `VITE_API_URL` empty so the
Vite proxy is used. In production set it to your API origin and add that origin to
`CORS_ORIGINS` on the backend.

**"This demo has not been published yet."**
Publish it from the product's Share tab.

**Publishing is blocked**
The readiness checklist tells you exactly what is missing — usually a description,
the main problem, at least one demo section, or an indexed knowledge base.

**Uploaded PDF fails with "No readable text"**
It is a scanned image. OCR it first (macOS Preview, Adobe, `ocrmypdf`) or paste
the content into a `.md` file.

**Supabase: "Could not reach the Supabase `founders` table"**
`supabase/schema.sql` has not been run, or `SUPABASE_URL` /
`SUPABASE_SERVICE_ROLE_KEY` are wrong. Re-run the schema; it is idempotent.

**The AI navigates to the wrong section**
Add better `keywords` to your demo sections — that is the mapping from a
prospect's words to a screen. The lead detail transcript shows every action the AI
took, which makes this quick to diagnose.

**The AI says "I don't have enough information"**
Working as designed — that fact is not in the knowledge base. Add it to the
Profile tab or upload a document covering it, then rebuild the index.

**Scores look wrong**
Check the ICP tab. Company fit, budget fit and timeline are all measured against
it. The lead detail page shows the reason behind every component's points.

---

## 10. Deployment

### Backend → Hugging Face Spaces (free)

1. Create a **Docker** Space.
2. Add a `Dockerfile` at the repo root:

   ```dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY backend/requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   COPY backend/ .
   ENV DATA_DIR=/data UPLOAD_DIR=/data/uploads FAISS_DIR=/data/faiss \
       SQLITE_PATH=/data/demopilot.db
   EXPOSE 7860
   CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
   ```

3. Space **Settings → Variables and secrets**: add `GROQ_API_KEY`, `JWT_SECRET`,
   `DB_BACKEND=supabase`, the three `SUPABASE_*` values, `CORS_ORIGINS` (your
   frontend URL) and `PUBLIC_APP_URL` (also your frontend URL — demo links are
   built from it).

> Space disks are ephemeral. Use `DB_BACKEND=supabase` in production so accounts,
> products and leads persist. FAISS indexes rebuild from `document_chunks` with
> one click on the Knowledge tab.

### Frontend → Render (free static site)

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm install && npm run build` |
| Publish directory | `frontend/dist` |
| Environment variable | `VITE_API_URL=https://your-space.hf.space` |

Add a rewrite rule so client-side routing works: source `/*` → destination
`/index.html`, action **Rewrite**. Without it, refreshing `/d/your-slug` 404s.

### Database → Supabase (free)

Follow [section 4](#4-switching-to-supabase).

### Post-deploy checklist

- [ ] `https://your-api/api/health` returns `"status": "ok"` with no warnings
- [ ] `JWT_SECRET` is a long random string, not the default
- [ ] `PUBLIC_APP_URL` points at the frontend (demo links depend on it)
- [ ] `CORS_ORIGINS` includes the frontend origin
- [ ] `APP_ENV=production`
- [ ] The frontend has the SPA rewrite rule
- [ ] Register, publish a demo, open the public link, and confirm a lead appears
