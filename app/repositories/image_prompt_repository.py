from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.orm import ImagePrompt


class ImagePromptRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_for_project(self, project_id: str) -> list[ImagePrompt]:
        stmt = select(ImagePrompt).where(ImagePrompt.project_id == project_id).order_by(ImagePrompt.global_order)
        return list(self.db.scalars(stmt))

    def list_for_scene(self, scene_id: str) -> list[ImagePrompt]:
        stmt = (
            select(ImagePrompt)
            .where(ImagePrompt.scene_id == scene_id)
            .order_by(ImagePrompt.order_in_scene)
        )
        return list(self.db.scalars(stmt))

    def get_by_global_order(self, project_id: str, global_order: int) -> ImagePrompt | None:
        stmt = select(ImagePrompt).where(
            ImagePrompt.project_id == project_id, ImagePrompt.global_order == global_order
        )
        return self.db.scalars(stmt).first()

    def max_global_order(self, project_id: str) -> int:
        stmt = select(func.max(ImagePrompt.global_order)).where(ImagePrompt.project_id == project_id)
        return self.db.scalar(stmt) or 0

    def delete_for_scene(self, scene_id: str) -> None:
        self.db.query(ImagePrompt).filter(ImagePrompt.scene_id == scene_id).delete()

    def delete_all_for_project(self, project_id: str) -> None:
        self.db.query(ImagePrompt).filter(ImagePrompt.project_id == project_id).delete()
