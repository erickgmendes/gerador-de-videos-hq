"""Entidades de domínio puras — sem dependência de FastAPI ou SQLAlchemy.

Representam a forma dos dados que os services manipulam. As camadas de
persistência (models/orm.py) e apresentação (schemas/) convertem de/para
essas entidades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.states import ProjectState


@dataclass
class Project:
    id: str
    name: str
    bible_reference: str
    state: ProjectState
    created_at: datetime
    updated_at: datetime
    youtube_status: str | None = None


@dataclass
class Scene:
    id: str
    project_id: str
    order: int
    location: str = ""
    time: str = ""
    characters: list[str] = field(default_factory=list)
    action: str = ""
    emotion: str = ""
    narration_excerpt: str = ""
    visual_importance: str = ""
    estimated_duration: float | None = None
    actual_duration: float | None = None
    status: str = "pending"
