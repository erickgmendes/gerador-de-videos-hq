from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import health
from app.config import get_settings
from app.db import get_session_factory
from app.domain.errors import AIProviderError, DomainError, ProjectNotFoundError
from app.services.jobs import reconcile_stale_jobs
from app.web.routes import audio, dashboard, diagnostics, image_prompts, narration, projects, settings, video_prompts

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Lê dependency_overrides manualmente — este código roda fora do ciclo
    # de requisição, então Depends() não se aplica; sem isso, os testes que
    # sobem a app via TestClient acabariam tocando o banco de dev de verdade.
    session_factory_provider = app.dependency_overrides.get(get_session_factory, get_session_factory)
    db = session_factory_provider()()
    try:
        reconcile_stale_jobs(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    get_settings().ensure_directories()

    app = FastAPI(title="Produção Audiovisual Bíblica", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    app.include_router(dashboard.router)
    app.include_router(projects.router)
    app.include_router(narration.router)
    app.include_router(audio.router)
    app.include_router(image_prompts.router)
    app.include_router(video_prompts.router)
    app.include_router(settings.router)
    app.include_router(diagnostics.router)
    app.include_router(health.router)

    @app.exception_handler(ProjectNotFoundError)
    def project_not_found_handler(request: Request, exc: ProjectNotFoundError) -> PlainTextResponse:
        return PlainTextResponse(str(exc), status_code=404)

    @app.exception_handler(AIProviderError)
    def ai_provider_error_handler(request: Request, exc: AIProviderError) -> PlainTextResponse:
        return PlainTextResponse(str(exc), status_code=503)

    @app.exception_handler(DomainError)
    def domain_error_handler(request: Request, exc: DomainError) -> PlainTextResponse:
        return PlainTextResponse(str(exc), status_code=400)

    return app


app = create_app()
