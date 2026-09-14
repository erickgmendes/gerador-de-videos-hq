from __future__ import annotations

from fastapi import APIRouter, Request

from app.diagnostics.checks import run_all_checks
from app.web.templating import templates

router = APIRouter()


@router.get("/diagnostics")
def diagnostics_page(request: Request):
    return templates.TemplateResponse(
        request,
        "diagnostics.html",
        {"active_nav": "diagnostics", "checks": run_all_checks()},
    )
