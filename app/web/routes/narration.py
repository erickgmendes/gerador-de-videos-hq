from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai import get_ai_adapter
from app.config import get_settings
from app.db import get_db, get_session_factory
from app.domain.errors import AIProviderError
from app.domain.states import ProjectState
from app.models.orm import Job
from app.repositories.scene_repository import SceneRepository
from app.services.jobs import get_latest_job
from app.services.narration.service import build_flowing_text, run_narration_job
from app.services.project_service import ProjectService
from app.storage import project_storage
from app.web.templating import templates

router = APIRouter()


def _build_context(project_id: str, db: Session) -> dict:
    project = ProjectService(db).get_project_summary(project_id)
    scenes = SceneRepository(db).list_for_project(project_id)
    narracao_path = project_storage.narracao_md_path(project_id)
    narration_text = narracao_path.read_text(encoding="utf-8") if narracao_path.exists() else None
    # Calculado a partir de `scenes` (não lido do arquivo) para continuar
    # funcionando em projetos gerados antes de texto_narracao.txt existir.
    flowing_text = build_flowing_text(scenes) if scenes else None
    total_minutes = round(sum(s.estimated_duration or 0 for s in scenes) / 60, 1) if scenes else 0
    return {
        "project": project,
        "scenes": scenes,
        "narration_text": narration_text,
        "flowing_text": flowing_text,
        "total_minutes": total_minutes,
        # Ao menos uma das duas — Gemini funciona sozinho como principal
        # também, não só como backup da Groq (ver app/adapters/ai/__init__.py).
        "ai_configured": bool(get_settings().groq_api_key or get_settings().gemini_api_key),
        "latest_job": get_latest_job(db, project_id, "narration"),
        "active_nav": "dashboard",
        "active_tab": "narracao",
    }


@router.get("/projects/{project_id}/narracao")
def narracao_page(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "project_narracao.html", context)


@router.get("/projects/{project_id}/narracao/status")
def narracao_status(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "partials/narracao_status.html", context)


@router.get("/projects/{project_id}/narracao/texto-corrido")
def narracao_texto_corrido(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    scenes = SceneRepository(db).list_for_project(project_id)
    return PlainTextResponse(build_flowing_text(scenes))


@router.post("/projects/{project_id}/narracao/gerar")
def gerar_narracao(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    service = ProjectService(db)
    project = service.get_project(project_id)  # levanta 404 se não existir

    try:
        ai = get_ai_adapter()
    except AIProviderError:
        return RedirectResponse(url=f"/projects/{project_id}/narracao", status_code=303)

    job = Job(
        project_id=project_id,
        job_type="narration",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    project.state = ProjectState.NARRATION_GENERATING.value
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_narration_job, project_id, job.id, ai, session_factory)

    return RedirectResponse(url=f"/projects/{project_id}/narracao", status_code=303)
