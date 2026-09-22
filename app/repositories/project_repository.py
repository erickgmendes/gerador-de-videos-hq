from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def exists(self, project_id: str) -> bool:
        return self.get(project_id) is not None

    def list_all(self) -> list[Project]:
        stmt = select(Project).order_by(Project.created_at.desc())
        return list(self.db.scalars(stmt))

    def save(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete(self, project: Project) -> None:
        # cascade="all, delete-orphan" nas relationships de Project (ver
        # app/models/orm.py) apaga cenas, jobs, personagens, cenários,
        # prompts de imagem e artifacts junto, numa unidade só.
        self.db.delete(project)
        self.db.commit()
