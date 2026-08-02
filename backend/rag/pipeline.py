"""The RAG pipeline, end to end.

    ingest:   file → extract → clean/sanitise → chunk → persist chunks
    index:    all chunks for a product (documents + profile) → embed → FAISS
    retrieve: query → embed → search → threshold → dedupe → build cited context

Chunks live in the database and vectors live on disk, so the index is always
rebuildable and every retrieved snippet can be traced back to a real source.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings
from app.core.logging_config import get_logger
from app.database import get_db, new_id, utc_now
from rag.embeddings import get_embedder
from rag.ingestion import Chunk, clean_and_sanitize, extract_text, profile_chunks
from rag.vector_store import SearchHit, drop_index, get_index

log = get_logger("rag.pipeline")

CHUNKS_TABLE = "document_chunks"


@dataclass
class IngestResult:
    chunk_count: int
    char_count: int
    note: str = ""


@dataclass
class RetrievedSource:
    id: str
    label: str
    kind: str
    snippet: str
    score: float
    content: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "kind": self.kind,
            "snippet": self.snippet,
            "score": self.score,
        }


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------

def ingest_document(
    *, product_id: str, document_id: str, filename: str, data: bytes
) -> IngestResult:
    """Extract → clean → chunk → persist. Vectors are built by `reindex_product`."""
    extraction = extract_text(filename, data)
    cleaned = clean_and_sanitize(extraction.text, source=filename)

    chunks = _chunk_document(cleaned, filename)
    db = get_db()
    db.delete_where(CHUNKS_TABLE, {"document_id": document_id})

    now = utc_now()
    rows = [
        {
            "id": new_id(),
            "product_id": product_id,
            "document_id": document_id,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "source_label": chunk.source_label,
            "source_kind": "document",
            "char_count": chunk.char_count,
            "created_at": now,
        }
        for chunk in chunks
    ]
    for row in rows:
        db.insert(CHUNKS_TABLE, row)

    log.info("Ingested %s → %d chunks (%d chars)", filename, len(rows), len(cleaned))
    return IngestResult(len(rows), len(cleaned), extraction.note)


def _chunk_document(text: str, filename: str) -> list[Chunk]:
    from rag.ingestion.chunker import chunk_text

    return chunk_text(text, source_label=filename, source_kind="document")


# ---------------------------------------------------------------------------
# Indexing
# ---------------------------------------------------------------------------

def reindex_product(product_id: str) -> dict:
    """Rebuild the whole vector index for a product: stored document chunks plus
    freshly derived product-profile and demo-section chunks."""
    db = get_db()
    product = db.get("products", product_id)
    if not product:
        return {"indexed": 0, "error": "product_not_found"}

    sections = db.find("demo_sections", {"product_id": product_id}, order_by="order_index")

    # Profile chunks are regenerated every rebuild so edits take effect immediately.
    db.delete_where(CHUNKS_TABLE, {"product_id": product_id, "source_kind": "profile"})
    now = utc_now()
    for chunk in profile_chunks(product, sections):
        db.insert(
            CHUNKS_TABLE,
            {
                "id": new_id(),
                "product_id": product_id,
                "document_id": None,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "source_label": chunk.source_label,
                "source_kind": "profile",
                "char_count": chunk.char_count,
                "created_at": now,
            },
        )

    rows = db.find(CHUNKS_TABLE, {"product_id": product_id})
    if not rows:
        drop_index(product_id)
        return {"indexed": 0, "documents": 0, "profile": 0}

    embedder = get_embedder()
    texts = [r["content"] for r in rows]
    vectors = embedder.embed_documents(texts)

    records = [
        {
            "chunk_id": r["id"],
            "content": r["content"],
            "source_label": r.get("source_label") or "Knowledge base",
            "source_kind": r.get("source_kind") or "document",
            "metadata": {"document_id": r.get("document_id")},
        }
        for r in rows
    ]

    get_index(product_id, embedder.dimension).replace_all(vectors, records)

    profile_count = sum(1 for r in rows if r.get("source_kind") == "profile")
    return {
        "indexed": len(rows),
        "documents": len(rows) - profile_count,
        "profile": profile_count,
        "embedder": embedder.name,
        "dimension": embedder.dimension,
    }


def remove_document(product_id: str, document_id: str) -> None:
    get_db().delete_where(CHUNKS_TABLE, {"document_id": document_id})
    reindex_product(product_id)


def delete_product_knowledge(product_id: str) -> None:
    get_db().delete_where(CHUNKS_TABLE, {"product_id": product_id})
    drop_index(product_id)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(
    product_id: str,
    query: str,
    *,
    top_k: int | None = None,
    min_score: float | None = None,
) -> list[RetrievedSource]:
    query = (query or "").strip()
    if not query:
        return []

    embedder = get_embedder()
    index = get_index(product_id, embedder.dimension)
    if index.size == 0:
        return []

    k = top_k or settings.rag_top_k
    # RAG_MIN_SCORE tunes the semantic model. The lexical fallback scores on a
    # different scale, so it supplies its own floor rather than inheriting one
    # that would silently discard every hit.
    if min_score is not None:
        threshold = min_score
    elif getattr(embedder, "score_floor", None) is not None and embedder.name.startswith("local-"):
        threshold = embedder.score_floor
    else:
        threshold = settings.rag_min_score

    hits = index.search(embedder.embed_query(query), top_k=max(k * 2, k))
    return _post_process(hits, k, threshold)


def _post_process(hits: list[SearchHit], k: int, threshold: float) -> list[RetrievedSource]:
    """Threshold, then de-duplicate near-identical snippets so the context block
    is not three copies of the same paragraph."""
    sources: list[RetrievedSource] = []
    seen: set[str] = set()

    for hit in hits:
        if hit.score < threshold:
            continue
        fingerprint = " ".join(hit.content.lower().split())[:120]
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        sources.append(
            RetrievedSource(
                id=hit.chunk_id,
                label=hit.source_label,
                kind=hit.source_kind,
                snippet=_snippet(hit.content),
                score=hit.score,
                content=hit.content,
            )
        )
        if len(sources) >= k:
            break
    return sources


def _snippet(content: str, limit: int = 220) -> str:
    text = " ".join(content.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_context_block(sources: list[RetrievedSource]) -> str:
    """Render retrieved chunks as a numbered, clearly delimited block.

    The delimiters and the [S1] labels do double duty: they let the model cite a
    source, and they make the boundary between *instructions* and *untrusted
    data* explicit, which is half of the prompt-injection defence.
    """
    if not sources:
        return ""

    blocks = []
    for i, source in enumerate(sources, start=1):
        blocks.append(
            f"[S{i}] source: {source.label} (relevance {source.score:.2f})\n{source.content}"
        )

    return (
        "<<<KNOWLEDGE_BASE_START>>>\n"
        + "\n\n---\n\n".join(blocks)
        + "\n<<<KNOWLEDGE_BASE_END>>>"
    )


def knowledge_stats(product_id: str) -> dict:
    db = get_db()
    rows = db.find(CHUNKS_TABLE, {"product_id": product_id})
    profile = sum(1 for r in rows if r.get("source_kind") == "profile")

    from rag.embeddings.embedder import _embedder  # noqa: PLC0415

    dimension = _embedder.dimension if _embedder else 384
    index = get_index(product_id, dimension) if rows else None

    return {
        "chunks_total": len(rows),
        "profile_chunks": profile,
        "document_chunks": len(rows) - profile,
        "vectors_indexed": index.size if index else 0,
    }
