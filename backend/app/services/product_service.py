"""Product profiles, ICP and demo sections — the founder's knowledge of their own product."""

from __future__ import annotations

from app.core.config import settings
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import random_suffix, slugify
from app.database import get_db, new_id, utc_now
from app.schemas.product import (
    DemoSectionCreate,
    DemoSectionOut,
    DemoSectionUpdate,
    KnowledgeStatus,
    ProductCreate,
    ProductOut,
    ProductSummary,
    ProductUpdate,
)

log = get_logger("service.product")

PRODUCTS = "products"
SECTIONS = "demo_sections"

_JSON_DEFAULTS: dict[str, object] = {
    "main_benefits": [],
    "features": [],
    "pricing": {},
    "integrations": [],
    "faqs": [],
    "objections": [],
    "case_studies": [],
    "icp": {},
    "cta": {},
}


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def demo_url(slug: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/d/{slug}"


def _row_to_out(row: dict) -> ProductOut:
    data = dict(row)
    for key, default in _JSON_DEFAULTS.items():
        if data.get(key) in (None, ""):
            data[key] = default
    data["is_published"] = bool(data.get("is_published"))
    for key in ("tagline", "description", "category", "target_customers",
                "main_problem", "security_info", "welcome_message"):
        data[key] = data.get(key) or ""
    data["demo_url"] = demo_url(data["slug"])
    return ProductOut(**data)


def _unique_slug(name: str) -> str:
    db = get_db()
    base = slugify(name, fallback="demo")
    candidate = base
    for _ in range(6):
        if not db.find_one(PRODUCTS, {"slug": candidate}):
            return candidate
        candidate = f"{base}-{random_suffix(4)}"
    raise ConflictError("Could not generate a unique demo link. Try a different product name.")


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def create_product(founder_id: str, payload: ProductCreate) -> ProductOut:
    now = utc_now()
    data = payload.model_dump()
    row = get_db().insert(
        PRODUCTS,
        {
            "id": new_id(),
            "founder_id": founder_id,
            "slug": _unique_slug(payload.name),
            "is_published": False,
            "created_at": now,
            "updated_at": now,
            **data,
        },
    )
    log.info("Created product %s for founder %s", row["id"], founder_id)
    return _row_to_out(row)


def list_products(founder_id: str) -> list[ProductSummary]:
    db = get_db()
    rows = db.find(PRODUCTS, {"founder_id": founder_id}, order_by="updated_at", descending=True)

    summaries = []
    for row in rows:
        chunks = db.find("document_chunks", {"product_id": row["id"]})
        summaries.append(
            ProductSummary(
                id=row["id"],
                name=row["name"],
                slug=row["slug"],
                tagline=row.get("tagline") or "",
                is_published=bool(row.get("is_published")),
                section_count=db.count(SECTIONS, {"product_id": row["id"]}),
                document_count=db.count("product_documents", {"product_id": row["id"]}),
                chunk_count=len(chunks),
                session_count=db.count("demo_sessions", {"product_id": row["id"]}),
                updated_at=row.get("updated_at"),
                demo_url=demo_url(row["slug"]),
            )
        )
    return summaries


def get_product(product_id: str) -> dict:
    row = get_db().get(PRODUCTS, product_id)
    if not row:
        raise NotFoundError("Product not found.")
    return row


def get_product_out(product_id: str) -> ProductOut:
    return _row_to_out(get_product(product_id))


def get_product_by_slug(slug: str) -> dict | None:
    return get_db().find_one(PRODUCTS, {"slug": slug})


def update_product(product_id: str, payload: ProductUpdate) -> ProductOut:
    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return get_product_out(product_id)

    if "is_published" in updates:
        updates["is_published"] = bool(updates["is_published"])
    updates["updated_at"] = utc_now()

    row = get_db().update(PRODUCTS, product_id, updates)
    if not row:
        raise NotFoundError("Product not found.")

    # Profile edits change the knowledge base, so the index must follow.
    _reindex_quietly(product_id)
    return _row_to_out(row)


def set_published(product_id: str, published: bool) -> ProductOut:
    product = get_product(product_id)

    if published:
        problems = publish_blockers(product_id, product)
        if problems:
            raise ValidationError(
                "This demo is not ready to publish yet.", details={"blockers": problems}
            )

    row = get_db().update(
        PRODUCTS, product_id, {"is_published": bool(published), "updated_at": utc_now()}
    )
    if published:
        _reindex_quietly(product_id)
    return _row_to_out(row)  # type: ignore[arg-type]


def publish_blockers(product_id: str, product: dict | None = None) -> list[str]:
    """What still needs doing before a prospect should see this demo."""
    product = product or get_product(product_id)
    db = get_db()
    problems: list[str] = []

    if not (product.get("description") or "").strip():
        problems.append("Add a product description so the AI knows what it is selling.")
    if not (product.get("main_problem") or "").strip():
        problems.append("Describe the main problem the product solves.")
    if db.count(SECTIONS, {"product_id": product_id}) == 0:
        problems.append("Add at least one demo section for the AI to navigate to.")
    if db.count("document_chunks", {"product_id": product_id}) == 0:
        problems.append(
            "No knowledge is indexed yet — fill in features/FAQs or upload a document."
        )
    return problems


def delete_product(product_id: str) -> None:
    from rag.pipeline import delete_product_knowledge

    db = get_db()
    sessions = db.find("demo_sessions", {"product_id": product_id})
    for session in sessions:
        db.delete_where("demo_messages", {"session_id": session["id"]})

    for table in ("demo_events", "demo_messages", "demo_sessions", "prospects",
                  "product_documents", SECTIONS):
        db.delete_where(table, {"product_id": product_id})

    delete_product_knowledge(product_id)
    db.delete(PRODUCTS, product_id)
    log.info("Deleted product %s and all related data", product_id)


def _reindex_quietly(product_id: str) -> None:
    """Reindexing must never break a save. If embeddings are unavailable the
    founder still keeps their edits and can retry from the Knowledge tab."""
    from rag.pipeline import reindex_product

    try:
        reindex_product(product_id)
    except Exception as exc:  # noqa: BLE001
        log.warning("Reindex after update failed for %s: %s", product_id, exc)


# ---------------------------------------------------------------------------
# Demo sections
# ---------------------------------------------------------------------------

def _section_out(row: dict) -> DemoSectionOut:
    return DemoSectionOut(
        id=row["id"],
        product_id=row["product_id"],
        section_key=row["section_key"],
        title=row["title"],
        description=row.get("description") or "",
        feature_explanation=row.get("feature_explanation") or "",
        visual_placeholder=row.get("visual_placeholder") or "",
        highlights=row.get("highlights") or [],
        keywords=row.get("keywords") or [],
        order_index=int(row.get("order_index") or 0),
    )


def list_sections(product_id: str) -> list[DemoSectionOut]:
    rows = get_db().find(SECTIONS, {"product_id": product_id}, order_by="order_index")
    return [_section_out(r) for r in rows]


def list_section_rows(product_id: str) -> list[dict]:
    return get_db().find(SECTIONS, {"product_id": product_id}, order_by="order_index")


def create_section(
    product_id: str, payload: DemoSectionCreate, *, reindex: bool = True
) -> DemoSectionOut:
    db = get_db()
    existing = db.find(SECTIONS, {"product_id": product_id})

    key = payload.section_key
    if any(s["section_key"] == key for s in existing):
        key = f"{key}-{random_suffix(3)}"

    now = utc_now()
    row = db.insert(
        SECTIONS,
        {
            "id": new_id(),
            "product_id": product_id,
            **payload.model_dump(),
            "section_key": key,
            "highlights": [h.model_dump() for h in payload.highlights],
            "order_index": payload.order_index or len(existing),
            "created_at": now,
            "updated_at": now,
        },
    )
    if reindex:
        _reindex_quietly(product_id)
    return _section_out(row)


def update_section(product_id: str, section_id: str, payload: DemoSectionUpdate) -> DemoSectionOut:
    db = get_db()
    row = db.get(SECTIONS, section_id)
    if not row or row.get("product_id") != product_id:
        raise NotFoundError("Demo section not found.")

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "highlights" in updates:
        updates["highlights"] = [
            h if isinstance(h, dict) else h.model_dump() for h in updates["highlights"]
        ]
    if "section_key" in updates:
        updates["section_key"] = slugify(updates["section_key"], fallback="section")
    updates["updated_at"] = utc_now()

    updated = db.update(SECTIONS, section_id, updates)
    _reindex_quietly(product_id)
    return _section_out(updated)  # type: ignore[arg-type]


def delete_section(product_id: str, section_id: str) -> None:
    db = get_db()
    row = db.get(SECTIONS, section_id)
    if not row or row.get("product_id") != product_id:
        raise NotFoundError("Demo section not found.")
    db.delete(SECTIONS, section_id)
    _reindex_quietly(product_id)


def reorder_sections(product_id: str, ordered_ids: list[str]) -> list[DemoSectionOut]:
    db = get_db()
    for index, section_id in enumerate(ordered_ids):
        row = db.get(SECTIONS, section_id)
        if row and row.get("product_id") == product_id:
            db.update(SECTIONS, section_id, {"order_index": index, "updated_at": utc_now()})
    return list_sections(product_id)


def seed_sections(product_id: str) -> list[DemoSectionOut]:
    """Generate a starter walkthrough from whatever the founder has already filled in.

    Not a fixed template: Overview/Problem/CTA are always useful, and the middle is
    built from the founder's real features, integrations and pricing. A product with
    no features gets no feature sections.
    """
    product = get_product(product_id)
    db = get_db()
    if db.count(SECTIONS, {"product_id": product_id}):
        raise ConflictError("This product already has demo sections.")

    name = product.get("name") or "the product"
    drafts: list[DemoSectionCreate] = [
        DemoSectionCreate(
            section_key="overview",
            title="Overview",
            description=product.get("tagline") or f"What {name} does and who it is for.",
            feature_explanation=product.get("description") or "",
            visual_placeholder="Product home screen",
            keywords=["overview", "what is", "about", "summary", "product"],
            order_index=0,
        )
    ]

    if product.get("main_problem"):
        drafts.append(
            DemoSectionCreate(
                section_key="problem",
                title="The problem",
                description="The pain this removes.",
                feature_explanation=product["main_problem"],
                visual_placeholder="Before / after comparison",
                keywords=["problem", "pain", "why", "challenge", "issue"],
                order_index=len(drafts),
            )
        )

    for feature in (product.get("features") or [])[:5]:
        title = (feature.get("name") or "Feature").strip()
        drafts.append(
            DemoSectionCreate(
                section_key=slugify(title, fallback="feature"),
                title=title,
                description=(feature.get("description") or "")[:280],
                feature_explanation=feature.get("description") or "",
                visual_placeholder=f"{title} screen",
                keywords=(feature.get("keywords") or []) + [title.lower()],
                order_index=len(drafts),
            )
        )

    if product.get("integrations"):
        names = ", ".join(i.get("name", "") for i in product["integrations"][:8])
        drafts.append(
            DemoSectionCreate(
                section_key="integrations",
                title="Integrations",
                description=f"Connects with {names}." if names else "How it fits your stack.",
                feature_explanation="\n".join(
                    f"{i.get('name', '')}: {i.get('description', '')}"
                    for i in product["integrations"]
                ),
                visual_placeholder="Integrations directory",
                keywords=["integration", "connect", "api", "stack", "sync", "webhook"],
                order_index=len(drafts),
            )
        )

    if (product.get("pricing") or {}).get("plans"):
        drafts.append(
            DemoSectionCreate(
                section_key="pricing",
                title="Pricing",
                description="Plans and what each one includes.",
                feature_explanation=(product["pricing"].get("notes") or ""),
                visual_placeholder="Pricing table",
                keywords=["pricing", "cost", "price", "plan", "budget", "how much"],
                order_index=len(drafts),
            )
        )

    if product.get("faqs"):
        drafts.append(
            DemoSectionCreate(
                section_key="faq",
                title="FAQ",
                description="Common questions answered.",
                visual_placeholder="FAQ list",
                keywords=["faq", "question", "common", "help"],
                order_index=len(drafts),
            )
        )

    cta = product.get("cta") or {}
    drafts.append(
        DemoSectionCreate(
            section_key="next-steps",
            title="Next steps",
            description=cta.get("note") or "How to get started.",
            feature_explanation=cta.get("note") or "",
            visual_placeholder="Call to action",
            keywords=["next", "start", "trial", "demo", "call", "contact", "signup"],
            order_index=len(drafts),
        )
    )

    # One rebuild at the end rather than one per section — seeding creates up to
    # nine sections and each rebuild re-embeds the whole knowledge base.
    created = [create_section(product_id, draft, reindex=False) for draft in drafts]
    _reindex_quietly(product_id)
    return created


# ---------------------------------------------------------------------------
# Knowledge status
# ---------------------------------------------------------------------------

def knowledge_status(product_id: str) -> KnowledgeStatus:
    from rag.embeddings import embedder_info
    from rag.pipeline import knowledge_stats
    from rag.vector_store import vector_store_info

    db = get_db()
    documents = db.find("product_documents", {"product_id": product_id})
    stats = knowledge_stats(product_id)
    info = embedder_info()

    return KnowledgeStatus(
        product_id=product_id,
        documents_total=len(documents),
        documents_indexed=sum(1 for d in documents if d.get("status") == "indexed"),
        documents_failed=sum(1 for d in documents if d.get("status") == "failed"),
        documents_processing=sum(
            1 for d in documents if d.get("status") in ("pending", "processing")
        ),
        chunks_total=stats["chunks_total"],
        profile_chunks=stats["profile_chunks"],
        vectors_indexed=stats["vectors_indexed"],
        embedding_model=info.get("model") or info.get("configured_model") or "",
        vector_backend=vector_store_info().get("backend", ""),
        ready=stats["vectors_indexed"] > 0,
    )
