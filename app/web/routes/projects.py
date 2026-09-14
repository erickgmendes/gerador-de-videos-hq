from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.errors import ValidationError
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService
from app.storage import project_storage
from app.web.templating import templates

router = APIRouter()


@router.get("/projects/new")
def new_project_form(request: Request):
    return templates.TemplateResponse(
        request, "project_new.html", {"active_nav": "dashboard", "error": None, "form": None}
    )


@router.post("/projects/new")
def create_project(
    request: Request,
    name: str = Form(""),
    bible_reference: str = Form(""),
    passage_text: str = Form(""),
    biblia_visual_text: str = Form(""),
    db: Session = Depends(get_db),
):
    form = {
        "name": name,
        "bible_reference": bible_reference,
        "passage_text": passage_text,
        "biblia_visual_text": biblia_visual_text,
    }
    try:
        data = ProjectCreate(
            name=name,
            bible_reference=bible_reference,
            passage_text=passage_text,
            biblia_visual_text=biblia_visual_text or None,
        )
        project = ProjectService(db).create_project(data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "project_new.html",
            {"active_nav": "dashboard", "error": str(exc), "form": form},
            status_code=400,
        )
    return RedirectResponse(url=f"/projects/{project.id}", status_code=303)


@router.get("/projects/{project_id}")
def project_detail(request: Request, project_id: str, db: Session = Depends(get_db)):
    project = ProjectService(db).get_project_summary(project_id)
    return templates.TemplateResponse(
        request, "project_detail.html", {"project": project, "active_nav": "dashboard"}
    )


@router.get("/projects/{project_id}/passagem")
def project_passage_text(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)  # 404 se não existir
    path = project_storage.input_passagem_path(project_id)
    return PlainTextResponse(path.read_text(encoding="utf-8"))


@router.get("/projects/{project_id}/biblia-visual")
def project_biblia_visual_text(project_id: str, db: Session = Depends(get_db)):
    ProjectService(db).get_project(project_id)
    path = project_storage.input_biblia_visual_path(project_id)
    return PlainTextResponse(path.read_text(encoding="utf-8"))
