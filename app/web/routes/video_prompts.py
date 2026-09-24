from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.errors import VideoPromptError
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.repositories.scene_repository import SceneRepository
from app.services.project_service import ProjectService
from app.services.video_prompts.service import (
    generate_video_prompts,
    recompute_project_state,
    regenerate_all_video_prompts,
)
from app.services.video_prompts.upload import associate_single_video_upload, associate_uploaded_videos
from app.storage import project_storage
from app.web.templating import templates

router = APIRouter()


def _build_context(project_id: str, db: Session) -> dict:
    project = ProjectService(db).get_project_summary(project_id)
    scenes = SceneRepository(db).list_for_project(project_id)
    image_prompts = ImagePromptRepository(db).list_for_project(project_id)

    all_images_ready = bool(image_prompts) and all(p.image_path for p in image_prompts)
    prompts_generated = bool(image_prompts) and all(p.video_prompt_text for p in image_prompts)

    panels_by_scene: dict[str, list] = {}
    for panel in image_prompts:
        panels_by_scene.setdefault(panel.scene_id, []).append(panel)

    return {
        "project": project,
        "scenes": scenes,
        "image_prompts": image_prompts,
        "panels_by_scene": panels_by_scene,
        "all_images_ready": all_images_ready,
        "prompts_generated": prompts_generated,
        "missing_count": sum(1 for p in image_prompts if p.image_path and not p.video_path),
        "active_nav": "dashboard",
        "active_tab": "videos",
    }


@router.get("/projects/{project_id}/videos")
def videos_page(request: Request, project_id: str, db: Session = Depends(get_db)):
    context = _build_context(project_id, db)
    return templates.TemplateResponse(request, "project_videos.html", context)


@router.get("/projects/{project_id}/videos/prompts.txt")
def videos_prompts_export(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    path = project_storage.video_prompts_export_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Os prompts de vídeo ainda não foram gerados.")
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/projects/{project_id}/videos/{global_order}/prompt.txt")
def video_prompt_individual(project_id: str, global_order: int, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    panel = ImagePromptRepository(db).get_by_global_order(project_id, global_order)
    if panel is None or not panel.video_prompt_text:
        raise HTTPException(status_code=404, detail="Prompt de vídeo não encontrado.")
    return PlainTextResponse(panel.video_prompt_text)


@router.get("/projects/{project_id}/videos/{global_order}/arquivo")
def video_arquivo(project_id: str, global_order: int, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    panel = ImagePromptRepository(db).get_by_global_order(project_id, global_order)
    if panel is None or not panel.video_path:
        raise HTTPException(status_code=404, detail="Vídeo ainda não enviado.")
    full_path = project_storage.project_root(project_id).parent / panel.video_path
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Vídeo ainda não enviado.")
    return FileResponse(full_path)


def _recompute_and_save(db: Session, project_id: str) -> None:
    project = ProjectService(db).get_project(project_id)
    project.state = recompute_project_state(ImagePromptRepository(db).list_for_project(project_id))
    db.commit()


@router.post("/projects/{project_id}/videos/gerar")
def gerar_videos_prompts(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    try:
        generate_video_prompts(db, project_id)
    except VideoPromptError:
        pass  # mensagem já visível na própria aba (all_images_ready/prompts_generated)
    else:
        _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/videos", status_code=303)


@router.post("/projects/{project_id}/videos/gerar-tudo")
def gerar_tudo_videos_prompts(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    try:
        regenerate_all_video_prompts(db, project_id)
    except VideoPromptError:
        pass
    else:
        _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/videos", status_code=303)


@router.post("/projects/{project_id}/videos/upload")
async def upload_videos(project_id: str, db: Session = Depends(get_db), files: list[UploadFile] = File(default=[])):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    payload = [(f.filename or "", await f.read()) for f in files]
    associate_uploaded_videos(db, project_id, payload)
    _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/videos", status_code=303)


@router.post("/projects/{project_id}/videos/{global_order}/upload")
async def upload_video_individual(
    project_id: str, global_order: int, db: Session = Depends(get_db), file: UploadFile = File(...)
):
    ProjectService(db).get_project(project_id)
    content = await file.read()
    associate_single_video_upload(db, project_id, global_order, file.filename or "", content)
    _recompute_and_save(db, project_id)
    return RedirectResponse(url=f"/projects/{project_id}/videos", status_code=303)
