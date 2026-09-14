from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.domain.states import ProjectState
from app.services.project_service import ProjectService
from app.web.templating import templates

router = APIRouter()


@router.get("/")
def dashboard(request: Request, db: Session = Depends(get_db)):
    summaries = ProjectService(db).list_projects()
    in_progress = [p for p in summaries if p.state != ProjectState.PUBLISHED]
    completed = [p for p in summaries if p.state == ProjectState.PUBLISHED]
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"in_progress": in_progress, "completed": completed, "active_nav": "dashboard"},
    )
