from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.adapters.tts import get_tts_adapter
from app.db import get_db, get_session_factory
from app.domain.states import ProjectState
from app.models.orm import Job
from app.repositories.scene_repository import SceneRepository
from app.services.audio.service import run_audio_job
from app.services.jobs import get_latest_job
from app.services.project_service import ProjectService
from app.storage import project_storage
from app.web.templating import templates

router = APIRouter()


def _build_context(project_id: str, db: Session) -> dict:
    project = ProjectService(db).get_project_summary(project_id)
    scenes = SceneRepository(db).list_for_project(project_id)
    final_path = project_storage.audio_final_path(project_id)
    return {
        "project": project,
        "scenes": scenes,
        "all_scenes_ready": bool(scenes) and all(s.actual_duration is not None for s in scenes),
        "final_audio_ready": final_path.exists(),
        "latest_job": get_latest_job(db, project_id, "audio"),
        "active_nav": "dashboard",
        "active_tab": "audio",
    }


@router.get("/projects/{project_id}/audio")
def audio_page(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "project_audio.html", context)


@router.get("/projects/{project_id}/audio/status")
def audio_status(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "partials/audio_status.html", context)


@router.get("/projects/{project_id}/audio/cena/{order}.mp3")
def audio_scene_file(project_id: str, order: int, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se o projeto não existir
    path = project_storage.audio_scene_path(project_id, order)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Áudio desta cena ainda não foi gerado.")
    return FileResponse(path, media_type="audio/mpeg")


@router.get("/projects/{project_id}/audio/narracao.mp3")
def audio_final_file(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    path = project_storage.audio_final_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="O áudio final ainda não foi gerado.")
    return FileResponse(path, media_type="audio/mpeg")


def _start_audio_job(
    project_id: str,
    scene_ids: list[str] | None,
    background_tasks: BackgroundTasks,
    db: Session,
    session_factory: sessionmaker,
) -> None:
    project = ProjectService(db).get_project(project_id)  # 404 se não existir

    job = Job(
        project_id=project_id,
        job_type="audio",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    project.state = ProjectState.AUDIO_GENERATING.value
    db.commit()
    db.refresh(job)

    background_tasks.add_task(
        run_audio_job, project_id, job.id, get_tts_adapter(), FFmpegAdapter(), session_factory, scene_ids
    )


@router.post("/projects/{project_id}/audio/gerar")
def gerar_audio(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    _start_audio_job(project_id, None, background_tasks, db, session_factory)
    return RedirectResponse(url=f"/projects/{project_id}/audio", status_code=303)


@router.post("/projects/{project_id}/audio/regenerar-tudo")
def regenerar_todo_audio(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    # scene_ids explícito (todas) — diferente de POST .../audio/gerar, que
    # só preenche as cenas sem áudio ainda (retomada). Aqui força a
    # ressíntese de tudo, mesmo cenas que já tinham áudio pronto.
    scenes = SceneRepository(db).list_for_project(project_id)
    all_scene_ids = [s.id for s in scenes]
    _start_audio_job(project_id, all_scene_ids, background_tasks, db, session_factory)
    return RedirectResponse(url=f"/projects/{project_id}/audio", status_code=303)


@router.post("/projects/{project_id}/scenes/{scene_id}/audio/gerar")
def gerar_audio_cena(
    project_id: str,
    scene_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    _start_audio_job(project_id, [scene_id], background_tasks, db, session_factory)
    return RedirectResponse(url=f"/projects/{project_id}/audio", status_code=303)
