"""Single source of truth for the data model shape.

Both storage backends read this: SQLite uses it to build DDL and to know which
columns hold JSON, Supabase uses it only for the JSON-column hints (Postgres
handles jsonb natively).

Keeping the schema declarative here is what lets one generic repository serve
both backends instead of duplicating eight tables twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Table:
    name: str
    columns: dict[str, str]
    json_columns: set[str] = field(default_factory=set)
    indexes: tuple[tuple[str, ...], ...] = ()


FOUNDERS = Table(
    name="founders",
    columns={
        "id": "TEXT PRIMARY KEY",
        "email": "TEXT NOT NULL UNIQUE",
        "full_name": "TEXT",
        "password_hash": "TEXT",
        "auth_provider": "TEXT DEFAULT 'local'",
        "created_at": "TEXT NOT NULL",
    },
)

PRODUCTS = Table(
    name="products",
    columns={
        "id": "TEXT PRIMARY KEY",
        "founder_id": "TEXT NOT NULL",
        "slug": "TEXT NOT NULL UNIQUE",
        "name": "TEXT NOT NULL",
        "tagline": "TEXT",
        "description": "TEXT",
        "category": "TEXT",
        "target_customers": "TEXT",
        "main_problem": "TEXT",
        "main_benefits": "TEXT",          # json: list[str]
        "features": "TEXT",               # json: list[{name, description, keywords}]
        "pricing": "TEXT",                # json: {model, currency, plans:[{name,price,period,includes}], notes}
        "integrations": "TEXT",           # json: list[{name, description}]
        "security_info": "TEXT",
        "faqs": "TEXT",                   # json: list[{question, answer}]
        "objections": "TEXT",             # json: list[{objection, response}]
        "case_studies": "TEXT",           # json: list[{title, customer, outcome, details}]
        "icp": "TEXT",                    # json: IdealCustomerProfile
        "cta": "TEXT",                    # json: {type, label, url, note}
        "welcome_message": "TEXT",
        "is_published": "INTEGER DEFAULT 0",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    },
    json_columns={
        "main_benefits", "features", "pricing", "integrations",
        "faqs", "objections", "case_studies", "icp", "cta",
    },
    indexes=(("founder_id",), ("slug",)),
)

PRODUCT_DOCUMENTS = Table(
    name="product_documents",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "filename": "TEXT NOT NULL",
        "stored_path": "TEXT",
        "content_type": "TEXT",
        "size_bytes": "INTEGER DEFAULT 0",
        "status": "TEXT DEFAULT 'pending'",   # pending|processing|indexed|failed
        "chunk_count": "INTEGER DEFAULT 0",
        "char_count": "INTEGER DEFAULT 0",
        "error": "TEXT",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    },
    indexes=(("product_id",),),
)

DOCUMENT_CHUNKS = Table(
    name="document_chunks",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "document_id": "TEXT",
        "chunk_index": "INTEGER DEFAULT 0",
        "content": "TEXT NOT NULL",
        "source_label": "TEXT",
        "source_kind": "TEXT DEFAULT 'document'",   # document | profile
        "char_count": "INTEGER DEFAULT 0",
        "created_at": "TEXT NOT NULL",
    },
    indexes=(("product_id",), ("document_id",)),
)

DEMO_SECTIONS = Table(
    name="demo_sections",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "section_key": "TEXT NOT NULL",
        "title": "TEXT NOT NULL",
        "description": "TEXT",
        "feature_explanation": "TEXT",
        "visual_placeholder": "TEXT",
        "highlights": "TEXT",             # json: list[{id, label, detail}]
        "keywords": "TEXT",               # json: list[str]
        "order_index": "INTEGER DEFAULT 0",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    },
    json_columns={"keywords", "highlights"},
    indexes=(("product_id",),),
)

PROSPECTS = Table(
    name="prospects",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "name": "TEXT",
        "email": "TEXT",
        "company": "TEXT",
        "job_title": "TEXT",
        "industry": "TEXT",
        "company_size": "TEXT",
        "created_at": "TEXT NOT NULL",
        "updated_at": "TEXT NOT NULL",
    },
    indexes=(("product_id",),),
)

DEMO_SESSIONS = Table(
    name="demo_sessions",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "prospect_id": "TEXT",
        "stage": "TEXT DEFAULT 'welcome'",
        "status": "TEXT DEFAULT 'active'",       # active | ended
        "qualification": "TEXT",                 # json: QualificationData
        "lead_score": "TEXT",                    # json: LeadScore
        "report": "TEXT",                        # json: LeadReport
        "summary": "TEXT",                       # rolling conversation summary
        "sections_visited": "TEXT",              # json: list[str]
        "contact_requested": "INTEGER DEFAULT 0",
        "message_count": "INTEGER DEFAULT 0",
        "duration_seconds": "INTEGER DEFAULT 0",
        "referrer": "TEXT",
        "started_at": "TEXT NOT NULL",
        "last_activity_at": "TEXT NOT NULL",
        "ended_at": "TEXT",
    },
    json_columns={"qualification", "lead_score", "report", "sections_visited"},
    indexes=(("product_id",), ("prospect_id",)),
)

DEMO_MESSAGES = Table(
    name="demo_messages",
    columns={
        "id": "TEXT PRIMARY KEY",
        "session_id": "TEXT NOT NULL",
        "product_id": "TEXT NOT NULL",
        "role": "TEXT NOT NULL",                 # user | assistant | system
        "content": "TEXT NOT NULL",
        "intent": "TEXT",
        "stage": "TEXT",
        "action": "TEXT",                        # json: DemoAction
        "sources": "TEXT",                       # json: list[RetrievedSource]
        "confidence": "TEXT",
        "turn_index": "INTEGER DEFAULT 0",
        "created_at": "TEXT NOT NULL",
    },
    json_columns={"action", "sources"},
    indexes=(("session_id",), ("product_id",)),
)

DEMO_EVENTS = Table(
    name="demo_events",
    columns={
        "id": "TEXT PRIMARY KEY",
        "product_id": "TEXT NOT NULL",
        "session_id": "TEXT",
        "event_type": "TEXT NOT NULL",
        "payload": "TEXT",                       # json
        "created_at": "TEXT NOT NULL",
    },
    json_columns={"payload"},
    indexes=(("product_id",), ("session_id",)),
)


ALL_TABLES: tuple[Table, ...] = (
    FOUNDERS,
    PRODUCTS,
    PRODUCT_DOCUMENTS,
    DOCUMENT_CHUNKS,
    DEMO_SECTIONS,
    PROSPECTS,
    DEMO_SESSIONS,
    DEMO_MESSAGES,
    DEMO_EVENTS,
)

TABLES_BY_NAME: dict[str, Table] = {t.name: t for t in ALL_TABLES}


def json_columns_for(table_name: str) -> set[str]:
    table = TABLES_BY_NAME.get(table_name)
    return set(table.json_columns) if table else set()
