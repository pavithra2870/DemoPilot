"""Document upload and ingestion orchestration.

Uploads are validated hard before anything touches disk, then ingested in a
background task so the founder's UI never blocks on embedding a 200-page PDF.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.core.errors import NotFoundError, ValidationError
from app.core.logging_config import get_logger
from app.core.security import safe_filename
from app.database import get_db, new_id, utc_now
from app.schemas.product import DocumentOut

log = get_logger("service.document")

DOCUMENTS = "product_documents"

# Magic-byte signatures for the formats where sniffing is meaningful.
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    ".pdf": (b"%PDF",),
    ".docx": (b"PK\x03\x04",),
}


def _to_out(row: dict) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        product_id=row["product_id"],
        filename=row["filename"],
        content_type=row.get("content_type") or "",
        size_bytes=int(row.get("size_bytes") or 0),
        status=row.get("status") or "pending",
        chunk_count=int(row.get("chunk_count") or 0),
        char_count=int(row.get("char_count") or 0),
        error=row.get("error"),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


to_out = _to_out


def validate_upload(filename: str, data: bytes, content_type: str = "") -> str:
    """Returns the normalised safe filename, or raises with a specific reason."""
    if not data:
        raise ValidationError("The uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(
            f"File is too large ({len(data) / 1_048_576:.1f} MB). "
            f"The limit is {settings.max_upload_mb} MB."
        )

    clean_name = safe_filename(filename)
    suffix = Path(clean_name).suffix.lower()
    if suffix not in settings.allowed_extensions:
        raise ValidationError(
            f"'{suffix or 'unknown'}' files are not accepted. "
            f"Allowed: {', '.join(sorted(settings.allowed_extensions))}"
        )

    signatures = _SIGNATURES.get(suffix)
    if signatures and not any(data.startswith(sig) for sig in signatures):
        raise ValidationError(
            f"That file does not look like a real {suffix} file. "
            "It may have been renamed from another format."
        )

    if suffix in {".txt", ".md", ".csv"}:
        sample = data[:4096]
        if b"\x00" in sample:
            raise ValidationError("That file appears to be binary, not text.")

    return clean_name


def list_documents(product_id: str) -> list[DocumentOut]:
    rows = get_db().find(DOCUMENTS, {"product_id": product_id},
                         order_by="created_at", descending=True)
    return [_to_out(r) for r in rows]


def create_document_record(product_id: str, filename: str, data: bytes,
                           content_type: str) -> dict:
    now = utc_now()
    document_id = new_id()

    stored_dir = settings.upload_path / product_id
    stored_dir.mkdir(parents=True, exist_ok=True)
    stored_path = stored_dir / f"{document_id}{Path(filename).suffix.lower()}"
    stored_path.write_bytes(data)

    # Store relative to the backend root when possible so the data directory stays
    # portable; fall back to absolute for upload dirs configured outside the project.
    try:
        recorded_path = str(stored_path.relative_to(settings.abs_path(".")))
    except ValueError:
        recorded_path = str(stored_path)

    return get_db().insert(
        DOCUMENTS,
        {
            "id": document_id,
            "product_id": product_id,
            "filename": filename,
            "stored_path": recorded_path,
            "content_type": content_type or "",
            "size_bytes": len(data),
            "status": "pending",
            "chunk_count": 0,
            "char_count": 0,
            "error": None,
            "created_at": now,
            "updated_at": now,
        },
    )


def process_document(product_id: str, document_id: str, filename: str, data: bytes) -> None:
    """Background ingestion. Every failure is recorded on the row so the founder
    sees exactly which file failed and why, instead of a silent no-op."""
    from rag.pipeline import ingest_document, reindex_product

    db = get_db()
    db.update(DOCUMENTS, document_id, {"status": "processing", "updated_at": utc_now()})

    try:
        result = ingest_document(
            product_id=product_id, document_id=document_id, filename=filename, data=data
        )
        reindex_product(product_id)
        db.update(
            DOCUMENTS,
            document_id,
            {
                "status": "indexed",
                "chunk_count": result.chunk_count,
                "char_count": result.char_count,
                "error": result.note or None,
                "updated_at": utc_now(),
            },
        )
        log.info("Indexed document %s (%d chunks)", filename, result.chunk_count)
    except Exception as exc:  # noqa: BLE001 - surfaced to the founder, not swallowed
        log.exception("Ingestion failed for %s", filename)
        db.update(
            DOCUMENTS,
            document_id,
            {"status": "failed", "error": str(exc)[:500], "updated_at": utc_now()},
        )


def delete_document(product_id: str, document_id: str) -> None:
    from rag.pipeline import remove_document

    db = get_db()
    row = db.get(DOCUMENTS, document_id)
    if not row or row.get("product_id") != product_id:
        raise NotFoundError("Document not found.")

    stored = row.get("stored_path")
    if stored:
        try:
            settings.abs_path(stored).unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Could not remove file %s: %s", stored, exc)

    db.delete(DOCUMENTS, document_id)
    remove_document(product_id, document_id)


def reindex(product_id: str) -> dict:
    from rag.pipeline import reindex_product

    return reindex_product(product_id)
