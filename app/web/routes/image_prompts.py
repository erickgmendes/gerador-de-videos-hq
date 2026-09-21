from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai import get_ai_adapter
from app.config import get_settings
from app.db import get_db, get_session_factory
from app.domain.errors import AIProviderError
from app.domain.states import ProjectState
from app.models.orm import Character, Job, Location
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.repositories.scene_repository import SceneRepository
from app.services.image_prompts.service import compute_panel_count, recompute_project_state, run_image_prompts_job
from app.services.image_prompts.upload import associate_single_upload, associate_uploaded_images
from app.services.jobs import get_latest_job
from app.services.project_service import ProjectService
from app.storage import project_storage
from app.web.templating import templates

router = APIRouter()


def _build_context(project_id: str, db: Session) -> dict:
    project = ProjectService(db).get_project_summary(project_id)
    scenes = SceneRepository(db).list_for_project(project_id)
    image_prompts = ImagePromptRepository(db).list_for_project(project_id)

    all_scenes_have_audio = bool(scenes) and all(s.actual_duration is not None for s in scenes)
    estimated_panel_count = (
        sum(compute_panel_count(s.actual_duration, get_settings().video_segment_seconds) for s in scenes)
        if all_scenes_have_audio
        else 0
    )
    panels_by_scene: dict[str, list] = {}
    for panel in image_prompts:
        panels_by_scene.setdefault(panel.scene_id, []).append(panel)

    return {
        "project": project,
        "scenes": scenes,
        "image_prompts": image_prompts,
        "panels_by_scene": panels_by_scene,
        "all_scenes_have_audio": all_scenes_have_audio,
        "estimated_panel_count": estimated_panel_count,
        "video_segment_seconds": get_settings().video_segment_seconds,
        "missing_count": sum(1 for p in image_prompts if not p.image_path),
        "latest_job": get_latest_job(db, project_id, "image_prompts"),
        "active_nav": "dashboard",
        "active_tab": "imagens",
    }


@router.get("/projects/{project_id}/imagens")
def imagens_page(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "project_imagens.html", context)


@router.get("/projects/{project_id}/imagens/status")
def imagens_status(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "partials/imagens_status.html", context)


@router.get("/projects/{project_id}/imagens/prompts.txt")
def imagens_prompts_export(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    path = project_storage.image_prompts_export_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Os prompts ainda não foram gerados.")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/projects/{project_id}/imagens/{global_order}/prompt.txt")
def imagem_prompt_individual(project_id: str, global_order: int, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    panel = ImagePromptRepository(db).get_by_global_order(project_id, global_order)
    if panel is None:
        raise HTTPException(status_code=404, detail="Painel não encontrado.")
    return PlainTextResponse(panel.prompt_text)


@router.get("/projects/{project_id}/imagens/{global_order}/arquivo")
def imagem_arquivo(project_id: str, global_order: int, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    panel = ImagePromptRepository(db).get_by_global_order(project_id, global_order)
    if panel is None or not panel.image_path:
        raise HTTPException(status_code=404, detail="Imagem ainda não enviada.")
    full_path = project_storage.project_root(project_id).parent / panel.image_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Imagem ainda não enviada.")
    return FileResponse(full_path)


def _start_image_prompts_job(
    project_id: str,
    scene_ids: list[str] | None,
    background_tasks: BackgroundTasks,
    db: Session,
    session_factory: sessionmaker,
) -> None:
    project = ProjectService(db).get_project(project_id)  # 404 se não existir
    ai = get_ai_adapter()  # levanta AIProviderError antes de qualquer escrita, se a chave faltar

    job = Job(
        project_id=project_id,
        job_type="image_prompts",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(job)
    project.state = ProjectState.IMAGE_PROMPTS_GENERATING.value
    db.commit()
    db.refresh(job)

    background_tasks.add_task(run_image_prompts_job, project_id, job.id, ai, session_factory, scene_ids)


@router.post("/projects/{project_id}/imagens/gerar")
def gerar_imagens(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    try:
        _start_image_prompts_job(project_id, None, background_tasks, db, session_factory)
    except AIProviderError:
        pass
    return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)


@router.post("/projects/{project_id}/imagens/gerar-tudo")
def gerar_tudo_imagens(
    project_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    """Apaga todos os prompts atuais e gera de novo do zero — diferente de
    POST .../imagens/gerar, que só preenche cenas sem painel ainda. Necessário
    porque a contagem de painéis por cena vem da duração do áudio
    (Scene.actual_duration); se o áudio foi regenerado depois dos prompts
    (ex.: mudou de voz/velocidade), os prompts antigos ficam com a
    contagem desatualizada e não há como "só atualizar" sem recalcular
    tudo — a numeração global e o teto de MAX_IMAGE_PROMPTS dependem do
    projeto inteiro, não de uma cena isolada."""
    try:
        get_ai_adapter()  # falha cedo — nunca apagar os prompts atuais sem chave configurada
    except AIProviderError:
        return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)

    ImagePromptRepository(db).delete_all_for_project(project_id)
    # Limpa também o cache de personagens e de cenários — senão descrições
    # de uma geração anterior (possivelmente já reaproveitadas/duplicadas)
    # continuariam contaminando a geração nova. Um reset completo deve
    # recomeçar a continuidade visual do zero.
    db.query(Character).filter(Character.project_id == project_id).delete()
    db.query(Location).filter(Location.project_id == project_id).delete()
    db.commit()
    _start_image_prompts_job(project_id, None, background_tasks, db, session_factory)
    return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)


@router.post("/projects/{project_id}/scenes/{scene_id}/imagens/gerar")
def gerar_imagens_cena(
    project_id: str,
    scene_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    session_factory: sessionmaker = Depends(get_session_factory),
):
    try:
        _start_image_prompts_job(project_id, [scene_id], background_tasks, db, session_factory)
    except AIProviderError:
        pass
    return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)


def _recompute_and_save(db: Session, project_id: str) -> None:
    project = ProjectService(db).get_project(project_id)
    project.state = recompute_project_state(
        SceneRepository(db).list_for_project(project_id), ImagePromptRepository(db).list_for_project(project_id)
    )
    db.commit()


@router.post("/projects/{project_id}/imagens/upload")
async def upload_imagens(project_id: str, db: Session = Depends(get_db), files: list[UploadFile] = File(default=[])):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    payload = [(f.filename or "", await f.read()) for f in files]
    associate_uploaded_images(db, project_id, payload)
    _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)


@router.post("/projects/{project_id}/imagens/{global_order}/upload")
async def upload_imagem_individual(
    project_id: str, global_order: int, db: Session = Depends(get_db), file: UploadFile = File(...)
):
    ProjectService(db).get_project(project_id)
    content = await file.read()
    associate_single_upload(db, project_id, global_order, file.filename or "", content)
    _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/imagens", status_code=303)
