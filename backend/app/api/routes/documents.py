from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile

from app.api.deps import CurrentFounder, owned_product
from app.core.rate_limit import upload_rate_limit
from app.schemas.product import DocumentOut
from app.services import document_service

router = APIRouter(prefix="/products/{product_id}/documents", tags=["knowledge"])


@router.get("", response_model=list[DocumentOut])
def list_documents(product_id: str, founder: CurrentFounder) -> list[DocumentOut]:
    owned_product(product_id, founder)
    return document_service.list_documents(product_id)


@router.post(
    "",
    response_model=DocumentOut,
    status_code=202,
    dependencies=[Depends(upload_rate_limit)],
)
async def upload_document(
    product_id: str,
    founder: CurrentFounder,
    background: BackgroundTasks,
    file: UploadFile = File(...),
) -> DocumentOut:
    """Validate, store, then extract → chunk → embed → index in the background."""
    owned_product(product_id, founder)

    data = await file.read()
    filename = document_service.validate_upload(
        file.filename or "upload", data, file.content_type or ""
    )

    row = document_service.create_document_record(
        product_id, filename, data, file.content_type or ""
    )
    background.add_task(
        document_service.process_document, product_id, row["id"], filename, data
    )
    return document_service.to_out(row)


@router.delete("/{document_id}", status_code=204)
def delete_document(product_id: str, document_id: str, founder: CurrentFounder) -> None:
    owned_product(product_id, founder)
    document_service.delete_document(product_id, document_id)


@router.post("/reindex")
def reindex(product_id: str, founder: CurrentFounder) -> dict:
    """Rebuild the vector index from stored chunks plus the current product profile."""
    owned_product(product_id, founder)
    return document_service.reindex(product_id)
