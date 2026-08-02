from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.database import get_db

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    """Operator-facing readiness probe. Also drives the frontend's setup banner."""
    db_health = get_db().health()

    llm_info: dict = {"provider": "groq", "model": settings.groq_model}
    try:
        from app.ai_services.llm import get_llm_provider

        provider = get_llm_provider()
        llm_info = {"provider": provider.name, "model": provider.model}
    except Exception as exc:  # noqa: BLE001 - health must never 500
        llm_info["error"] = str(exc)
    llm_info["configured"] = settings.llm_configured

    try:
        from rag.vector_store import vector_store_info

        rag_info = vector_store_info()
    except Exception as exc:  # noqa: BLE001
        rag_info = {"available": False, "error": str(exc)}

    return {
        "status": "ok" if db_health.get("ok") else "degraded",
        "environment": settings.app_env,
        "database": db_health,
        "llm": llm_info,
        "rag": rag_info,
        "warnings": settings.validate_runtime(),
    }
