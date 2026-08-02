"""DemoPilot API entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.logging_config import get_logger, setup_logging

setup_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(_: FastAPI):
    from app.database import get_db

    settings.ensure_dirs()
    db = get_db()
    log.info("DemoPilot API starting — storage=%s, model=%s", db.backend, settings.groq_model)
    for warning in settings.validate_runtime():
        log.warning(warning)

    yield

    from app.ai_services.llm import close_llm_providers

    await close_llm_providers()
    log.info("DemoPilot API stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="DemoPilot API",
        description=(
            "An AI Sales Engineer that runs asynchronous, interactive B2B product demos: "
            "grounded answers, demo control, natural qualification and lead intelligence."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    from app.api.routes import (
        analytics,
        auth,
        demo,
        demo_ws,
        documents,
        health,
        leads,
        products,
        sections,
    )

    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(products.router, prefix="/api")
    app.include_router(sections.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(demo.router, prefix="/api")
    app.include_router(leads.router, prefix="/api")
    app.include_router(analytics.router, prefix="/api")
    app.include_router(demo_ws.router)          # WebSocket, no /api prefix

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": "DemoPilot API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/api/health",
        }

    return app


app = create_app()
