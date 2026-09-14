from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.domain.states import ProjectState, StepKey, StepStatus


class ProjectCreate(BaseModel):
    """Estrutura de entrada para criação de projeto. As regras de negócio
    (campos obrigatórios não vazios) ficam em ProjectService.create_project,
    não aqui — para que a mensagem de erro seja amigável e centralizada."""

    name: str = ""
    bible_reference: str = ""
    passage_text: str = ""
    biblia_visual_text: str | None = None


class ProjectSummary(BaseModel):
    id: str
    name: str
    bible_reference: str
    state: ProjectState
    progress: int
    steps: dict[StepKey, StepStatus]
    created_at: datetime
    updated_at: datetime
    youtube_status: str | None = None
