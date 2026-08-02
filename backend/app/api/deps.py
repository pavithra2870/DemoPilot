"""Shared FastAPI dependencies: authentication and ownership checks."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.database import Row, get_db
from app.services import auth_service


def _extract_bearer(authorization: str | None) -> str:
    if not authorization:
        raise UnauthorizedError("Authentication required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise UnauthorizedError("Expected an `Authorization: Bearer <token>` header.")
    return token.strip()


def get_current_founder(
    authorization: Annotated[str | None, Header()] = None,
) -> Row:
    return auth_service.resolve_token(_extract_bearer(authorization))


def get_optional_founder(
    authorization: Annotated[str | None, Header()] = None,
) -> Row | None:
    if not authorization:
        return None
    try:
        return auth_service.resolve_token(_extract_bearer(authorization))
    except UnauthorizedError:
        return None


CurrentFounder = Annotated[Row, Depends(get_current_founder)]


def owned_product(product_id: str, founder: Row) -> Row:
    """Fetch a product and assert the caller owns it. Every founder route uses this."""
    product = get_db().get("products", product_id)
    if not product:
        raise NotFoundError("Product not found.")
    if product.get("founder_id") != founder["id"]:
        raise ForbiddenError("You do not have access to this product.")
    return product
