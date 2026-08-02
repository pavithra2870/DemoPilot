-- ===========================================================================
-- DemoPilot — Supabase / Postgres schema
--
-- HOW TO RUN
--   1. Supabase dashboard → SQL Editor → New query
--   2. Paste this entire file and press Run
--   3. Set DB_BACKEND=supabase in backend/.env along with SUPABASE_URL and
--      SUPABASE_SERVICE_ROLE_KEY
--
-- Safe to re-run: every statement is idempotent.
--
-- SECURITY MODEL
--   The backend connects with the SERVICE ROLE key and enforces ownership in
--   code (see app/api/deps.py::owned_product). RLS is enabled on every table as
--   defence in depth so that the ANON key — the only key that could ever leak to
--   a browser — can read nothing at all.
-- ===========================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- founders
-- Mirrors auth.users when AUTH_BACKEND=supabase. `password_hash` is used only
-- in local-auth mode and stays null when Supabase Auth owns credentials.
-- ---------------------------------------------------------------------------
create table if not exists public.founders (
  id            uuid primary key default gen_random_uuid(),
  email         text not null unique,
  full_name     text,
  password_hash text,
  auth_provider text default 'local',
  created_at    timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- products
-- The product profile + ICP. Rich fields are jsonb so a founder can add
-- features, FAQs and plans without a migration.
-- ---------------------------------------------------------------------------
create table if not exists public.products (
  id               uuid primary key default gen_random_uuid(),
  founder_id       uuid not null references public.founders(id) on delete cascade,
  slug             text not null unique,          -- powers the public /d/:slug link
  name             text not null,
  tagline          text,
  description      text,
  category         text,
  target_customers text,
  main_problem     text,
  main_benefits    jsonb default '[]'::jsonb,
  features         jsonb default '[]'::jsonb,
  pricing          jsonb default '{}'::jsonb,
  integrations     jsonb default '[]'::jsonb,
  security_info    text,
  faqs             jsonb default '[]'::jsonb,
  objections       jsonb default '[]'::jsonb,
  case_studies     jsonb default '[]'::jsonb,
  icp              jsonb default '{}'::jsonb,
  cta              jsonb default '{}'::jsonb,
  welcome_message  text,
  is_published     boolean default false,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);

create index if not exists idx_products_founder_id on public.products(founder_id);
create index if not exists idx_products_slug       on public.products(slug);

-- ---------------------------------------------------------------------------
-- product_documents
-- Upload metadata + ingestion status. The extracted text lives in
-- document_chunks, not here.
-- ---------------------------------------------------------------------------
create table if not exists public.product_documents (
  id           uuid primary key default gen_random_uuid(),
  product_id   uuid not null references public.products(id) on delete cascade,
  filename     text not null,
  stored_path  text,
  content_type text,
  size_bytes   bigint default 0,
  status       text default 'pending',   -- pending | processing | indexed | failed
  chunk_count  integer default 0,
  char_count   integer default 0,
  error        text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists idx_product_documents_product_id
  on public.product_documents(product_id);

-- ---------------------------------------------------------------------------
-- document_chunks
-- Durable copy of every chunk. FAISS holds only the vectors, so this table is
-- what makes the index rebuildable and what lets retrieved answers cite a real
-- source. `source_kind = 'profile'` rows are derived from the product profile
-- itself and are regenerated on every reindex.
-- ---------------------------------------------------------------------------
create table if not exists public.document_chunks (
  id           uuid primary key default gen_random_uuid(),
  product_id   uuid not null references public.products(id) on delete cascade,
  document_id  uuid references public.product_documents(id) on delete cascade,
  chunk_index  integer default 0,
  content      text not null,
  source_label text,
  source_kind  text default 'document',  -- document | profile
  char_count   integer default 0,
  created_at   timestamptz not null default now()
);

create index if not exists idx_document_chunks_product_id  on public.document_chunks(product_id);
create index if not exists idx_document_chunks_document_id on public.document_chunks(document_id);

-- ---------------------------------------------------------------------------
-- demo_sections
-- The navigable screens of the interactive demo. `section_key` is the target the
-- AI emits in a navigate/highlight action.
-- ---------------------------------------------------------------------------
create table if not exists public.demo_sections (
  id                  uuid primary key default gen_random_uuid(),
  product_id          uuid not null references public.products(id) on delete cascade,
  section_key         text not null,
  title               text not null,
  description         text,
  feature_explanation text,
  visual_placeholder  text,
  highlights          jsonb default '[]'::jsonb,
  keywords            jsonb default '[]'::jsonb,
  order_index         integer default 0,
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

create index if not exists idx_demo_sections_product_id on public.demo_sections(product_id);
create unique index if not exists idx_demo_sections_product_key
  on public.demo_sections(product_id, section_key);

-- ---------------------------------------------------------------------------
-- prospects
-- Created lazily — only once the AI has learned something identifying. An
-- anonymous visitor stays a session and never becomes a contact record.
-- ---------------------------------------------------------------------------
create table if not exists public.prospects (
  id           uuid primary key default gen_random_uuid(),
  product_id   uuid not null references public.products(id) on delete cascade,
  name         text,
  email        text,
  company      text,
  job_title    text,
  industry     text,
  company_size text,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists idx_prospects_product_id on public.prospects(product_id);
create index if not exists idx_prospects_email      on public.prospects(product_id, email);

-- ---------------------------------------------------------------------------
-- demo_sessions
-- One prospect visit. Carries live qualification state, the latest deterministic
-- lead score, and the generated lead brief.
-- ---------------------------------------------------------------------------
create table if not exists public.demo_sessions (
  id                uuid primary key default gen_random_uuid(),
  product_id        uuid not null references public.products(id) on delete cascade,
  prospect_id       uuid references public.prospects(id) on delete set null,
  stage             text default 'welcome',
  status            text default 'active',    -- active | ended
  qualification     jsonb default '{}'::jsonb,
  lead_score        jsonb default '{}'::jsonb,
  report            jsonb,
  summary           text,                     -- rolling conversation summary
  sections_visited  jsonb default '[]'::jsonb,
  contact_requested boolean default false,
  message_count     integer default 0,
  duration_seconds  integer default 0,
  referrer          text,
  started_at        timestamptz not null default now(),
  last_activity_at  timestamptz not null default now(),
  ended_at          timestamptz
);

create index if not exists idx_demo_sessions_product_id  on public.demo_sessions(product_id);
create index if not exists idx_demo_sessions_prospect_id on public.demo_sessions(prospect_id);
create index if not exists idx_demo_sessions_activity
  on public.demo_sessions(product_id, last_activity_at desc);

-- ---------------------------------------------------------------------------
-- demo_messages
-- Full transcript. Assistant turns keep the structured action they issued and
-- the RAG sources they were grounded in, which is what makes the founder's
-- transcript view auditable.
-- ---------------------------------------------------------------------------
create table if not exists public.demo_messages (
  id         uuid primary key default gen_random_uuid(),
  session_id uuid not null references public.demo_sessions(id) on delete cascade,
  product_id uuid not null references public.products(id) on delete cascade,
  role       text not null,                -- user | assistant | system
  content    text not null,
  intent     text,
  stage      text,
  action     jsonb,
  sources    jsonb,
  confidence text,
  turn_index integer default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_demo_messages_session_id on public.demo_messages(session_id);
create index if not exists idx_demo_messages_product_id on public.demo_messages(product_id);

-- ---------------------------------------------------------------------------
-- demo_events
-- Analytics event stream: session_started, section_view, question_asked,
-- objection_raised, contact_submitted, session_ended, …
-- ---------------------------------------------------------------------------
create table if not exists public.demo_events (
  id         uuid primary key default gen_random_uuid(),
  product_id uuid not null references public.products(id) on delete cascade,
  session_id uuid references public.demo_sessions(id) on delete cascade,
  event_type text not null,
  payload    jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_demo_events_product_id on public.demo_events(product_id);
create index if not exists idx_demo_events_session_id on public.demo_events(session_id);
create index if not exists idx_demo_events_type       on public.demo_events(product_id, event_type);

-- ===========================================================================
-- Row Level Security
--
-- The service role bypasses RLS entirely, which is how the backend operates.
-- Enabling RLS with owner-scoped policies means the anon key can reach nothing,
-- so a leaked public key cannot enumerate another founder's leads.
-- ===========================================================================

alter table public.founders          enable row level security;
alter table public.products          enable row level security;
alter table public.product_documents enable row level security;
alter table public.document_chunks   enable row level security;
alter table public.demo_sections     enable row level security;
alter table public.prospects         enable row level security;
alter table public.demo_sessions     enable row level security;
alter table public.demo_messages     enable row level security;
alter table public.demo_events       enable row level security;

-- Founders can see only their own account row.
drop policy if exists "founders_self_access" on public.founders;
create policy "founders_self_access" on public.founders
  for all using (auth.uid() = id) with check (auth.uid() = id);

-- Founders can see only their own products.
drop policy if exists "products_owner_access" on public.products;
create policy "products_owner_access" on public.products
  for all using (auth.uid() = founder_id) with check (auth.uid() = founder_id);

-- Child tables inherit ownership through products.
create or replace function public.owns_product(target uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.products p
    where p.id = target and p.founder_id = auth.uid()
  );
$$;

drop policy if exists "documents_owner_access" on public.product_documents;
create policy "documents_owner_access" on public.product_documents
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "chunks_owner_access" on public.document_chunks;
create policy "chunks_owner_access" on public.document_chunks
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "sections_owner_access" on public.demo_sections;
create policy "sections_owner_access" on public.demo_sections
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "prospects_owner_access" on public.prospects;
create policy "prospects_owner_access" on public.prospects
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "sessions_owner_access" on public.demo_sessions;
create policy "sessions_owner_access" on public.demo_sessions
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "messages_owner_access" on public.demo_messages;
create policy "messages_owner_access" on public.demo_messages
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

drop policy if exists "events_owner_access" on public.demo_events;
create policy "events_owner_access" on public.demo_events
  for all using (public.owns_product(product_id))
  with check (public.owns_product(product_id));

-- ===========================================================================
-- Verify
-- ===========================================================================
select
  table_name,
  (select count(*) from information_schema.columns c
   where c.table_name = t.table_name and c.table_schema = 'public') as columns
from information_schema.tables t
where table_schema = 'public'
  and table_name in (
    'founders', 'products', 'product_documents', 'document_chunks',
    'demo_sections', 'prospects', 'demo_sessions', 'demo_messages', 'demo_events'
  )
order by table_name;
