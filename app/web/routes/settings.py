from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.domain.errors import ValidationError
from app.services.settings_service import list_secret_fields, set_secret
from app.web.templating import templates

router = APIRouter()

FUTURE_CATEGORIES = [
    ("Áudio", "Fase 3"),
    ("Vídeo", "Fase 6"),
    ("Meta Automation", "Fase 4"),
    ("Vibes Automation", "Fase 5"),
    ("YouTube", "Fase 8"),
]


@router.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "active_nav": "settings",
            "settings": get_settings(),
            "future_categories": FUTURE_CATEGORIES,
            "secret_fields": list_secret_fields(),
        },
    )


@router.post("/settings/secrets/{key}")
def save_secret(key: str, value: str = Form("")):
    try:
        set_secret(key, value)
    except ValidationError:
        pass  # chave desconhecida (ex.: URL manipulada) — ignora silenciosamente
    return RedirectResponse(url="/settings", status_code=303)
