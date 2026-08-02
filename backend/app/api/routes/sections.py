from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentFounder, owned_product
from app.schemas.product import (
    DemoSectionCreate,
    DemoSectionOut,
    DemoSectionUpdate,
    SectionReorder,
)
from app.services import product_service

router = APIRouter(prefix="/products/{product_id}/sections", tags=["demo-sections"])


@router.get("", response_model=list[DemoSectionOut])
def list_sections(product_id: str, founder: CurrentFounder) -> list[DemoSectionOut]:
    owned_product(product_id, founder)
    return product_service.list_sections(product_id)


@router.post("", response_model=DemoSectionOut, status_code=201)
def create_section(
    product_id: str, payload: DemoSectionCreate, founder: CurrentFounder
) -> DemoSectionOut:
    owned_product(product_id, founder)
    return product_service.create_section(product_id, payload)


@router.put("/{section_id}", response_model=DemoSectionOut)
def update_section(
    product_id: str, section_id: str, payload: DemoSectionUpdate, founder: CurrentFounder
) -> DemoSectionOut:
    owned_product(product_id, founder)
    return product_service.update_section(product_id, section_id, payload)


@router.delete("/{section_id}", status_code=204)
def delete_section(product_id: str, section_id: str, founder: CurrentFounder) -> None:
    owned_product(product_id, founder)
    product_service.delete_section(product_id, section_id)


@router.post("/reorder", response_model=list[DemoSectionOut])
def reorder(
    product_id: str, payload: SectionReorder, founder: CurrentFounder
) -> list[DemoSectionOut]:
    owned_product(product_id, founder)
    return product_service.reorder_sections(product_id, payload.ordered_ids)


@router.post("/seed", response_model=list[DemoSectionOut], status_code=201)
def seed(product_id: str, founder: CurrentFounder) -> list[DemoSectionOut]:
    """Build a starter walkthrough from the product profile the founder already filled in."""
    owned_product(product_id, founder)
    return product_service.seed_sections(product_id)
