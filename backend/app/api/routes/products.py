from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentFounder, owned_product
from app.schemas.product import (
    KnowledgeStatus,
    ProductCreate,
    ProductOut,
    ProductSummary,
    ProductUpdate,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductSummary])
def list_products(founder: CurrentFounder) -> list[ProductSummary]:
    return product_service.list_products(founder["id"])


@router.post("", response_model=ProductOut, status_code=201)
def create_product(payload: ProductCreate, founder: CurrentFounder) -> ProductOut:
    return product_service.create_product(founder["id"], payload)


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, founder: CurrentFounder) -> ProductOut:
    owned_product(product_id, founder)
    return product_service.get_product_out(product_id)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: str, payload: ProductUpdate, founder: CurrentFounder
) -> ProductOut:
    owned_product(product_id, founder)
    return product_service.update_product(product_id, payload)


@router.delete("/{product_id}", status_code=204)
def delete_product(product_id: str, founder: CurrentFounder) -> None:
    owned_product(product_id, founder)
    product_service.delete_product(product_id)


@router.post("/{product_id}/publish", response_model=ProductOut)
def publish(product_id: str, founder: CurrentFounder, published: bool = True) -> ProductOut:
    owned_product(product_id, founder)
    return product_service.set_published(product_id, published)


@router.get("/{product_id}/publish-check")
def publish_check(product_id: str, founder: CurrentFounder) -> dict:
    product = owned_product(product_id, founder)
    blockers = product_service.publish_blockers(product_id, product)
    return {
        "ready": not blockers,
        "blockers": blockers,
        "demo_url": product_service.demo_url(product["slug"]),
    }


@router.get("/{product_id}/knowledge-status", response_model=KnowledgeStatus)
def knowledge_status(product_id: str, founder: CurrentFounder) -> KnowledgeStatus:
    owned_product(product_id, founder)
    return product_service.knowledge_status(product_id)
