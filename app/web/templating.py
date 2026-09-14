from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.web import presentation

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.globals.update(
    STEP_ORDER=presentation.STEP_ORDER,
    STEP_LABELS=presentation.STEP_LABELS,
    STEP_ICONS=presentation.STEP_ICONS,
    STEP_CSS_CLASS=presentation.STEP_CSS_CLASS,
    CHECK_ICONS=presentation.CHECK_ICONS,
    CHECK_BADGE_CLASS=presentation.CHECK_BADGE_CLASS,
    PROJECT_TABS=presentation.PROJECT_TABS,
)
