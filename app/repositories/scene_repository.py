from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.orm import Scene


class SceneRepository:
    """Usado a partir da Fase 2, quando o roteiro passa a gerar cenas.json."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_project(self, project_id: str) -> list[Scene]:
        stmt = select(Scene).where(Scene.project_id == project_id).order_by(Scene.order)
        return list(self.db.scalars(stmt))

    def replace_all(self, project_id: str, scenes: list[Scene]) -> None:
        self.db.query(Scene).filter(Scene.project_id == project_id).delete()
        for scene in scenes:
            self.db.add(scene)
        self.db.commit()
