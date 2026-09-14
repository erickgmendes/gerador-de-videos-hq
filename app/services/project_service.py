"""Orquestra criação, listagem e carregamento de projetos.

Este service não conhece FastAPI nem SQLAlchemy diretamente além do que o
repositório expõe — a rota HTTP fica fina, toda a regra mora aqui.
"""

from __future__ import annotations

import json
import secrets
from datetime import date, datetime, timezone

from slugify import slugify
from sqlalchemy.orm import Session

from app.domain.errors import ProjectNotFoundError, ValidationError
from app.domain.states import ProjectState, progress_percent, step_statuses
from app.models.orm import Project
from app.repositories.project_repository import ProjectRepository
from app.schemas.project import ProjectCreate, ProjectSummary
from app.storage import project_storage


def _generate_project_id(name: str) -> str:
    base = slugify(name) or "projeto"
    today = date.today().isoformat()
    suffix = secrets.token_hex(2)
    return f"{base}-{today}-{suffix}"


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ProjectRepository(db)

    def create_project(self, data: ProjectCreate) -> Project:
        if not data.name.strip():
            raise ValidationError("Informe um nome para o projeto.")
        if not data.bible_reference.strip():
            raise ValidationError("Informe a referência bíblica.")
        if not data.passage_text.strip():
            raise ValidationError("Informe o texto completo da passagem.")

        project_id = _generate_project_id(data.name)
        while project_storage.project_exists(project_id):
            project_id = _generate_project_id(data.name)

        root = project_storage.create_project_tree(project_id)

        project_storage.input_passagem_path(project_id).write_text(data.passage_text, encoding="utf-8")
        biblia_visual = data.biblia_visual_text or (
            "<!-- Bíblia Visual dos Personagens deste projeto. "
            "Preencha com as definições visuais canônicas (seção 11 da especificação). -->\n"
        )
        project_storage.input_biblia_visual_path(project_id).write_text(biblia_visual, encoding="utf-8")

        now = datetime.now(timezone.utc)
        metadata = {
            "id": project_id,
            "name": data.name,
            "bible_reference": data.bible_reference,
            "created_at": now.isoformat(),
        }
        project_storage.project_json_path(project_id).write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        project = Project(
            id=project_id,
            name=data.name,
            bible_reference=data.bible_reference,
            state=ProjectState.CREATED.value,
        )
        self.repo.add(project)
        return project

    def list_projects(self) -> list[ProjectSummary]:
        return [self._to_summary(project) for project in self.repo.list_all()]

    def get_project(self, project_id: str) -> Project:
        project = self.repo.get(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    def get_project_summary(self, project_id: str) -> ProjectSummary:
        return self._to_summary(self.get_project(project_id))

    @staticmethod
    def _to_summary(project: Project) -> ProjectSummary:
        state = ProjectState(project.state)
        return ProjectSummary(
            id=project.id,
            name=project.name,
            bible_reference=project.bible_reference,
            state=state,
            progress=progress_percent(state),
            steps=step_statuses(state),
            created_at=project.created_at,
            updated_at=project.updated_at,
            youtube_status=project.youtube_status,
        )
