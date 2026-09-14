"""Associação de imagens enviadas em lote aos painéis pelo nome do
arquivo (seção 23 da especificação): primeira sequência de dígitos
encontrada no nome vira o `global_order`. Upload individual (por painel)
não passa por aqui — é uma correção direta, sem precisar adivinhar nada.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.repositories.image_prompt_repository import ImagePromptRepository
from app.storage import project_storage

_NUMBER_RE = re.compile(r"(\d+)")


def parse_global_order_from_filename(filename: str) -> int | None:
    match = _NUMBER_RE.search(Path(filename).stem)
    if not match:
        return None
    return int(match.group(1))


def _relative_path(project_id: str, path: Path) -> str:
    return str(path.relative_to(project_storage.project_root(project_id).parent))


def _save_image(project_id: str, global_order: int, filename: str, content: bytes) -> str:
    extension = Path(filename).suffix or ".png"
    out_path = project_storage.image_file_path(project_id, global_order, extension)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(content)
    return _relative_path(project_id, out_path)


@dataclass
class UploadResult:
    expected_total: int = 0
    matched: list[int] = field(default_factory=list)
    unmatched_filenames: list[str] = field(default_factory=list)
    missing: list[int] = field(default_factory=list)


def associate_uploaded_images(db: Session, project_id: str, files: list[tuple[str, bytes]]) -> UploadResult:
    repo = ImagePromptRepository(db)
    all_prompts = repo.list_for_project(project_id)
    by_order = {p.global_order: p for p in all_prompts}

    result = UploadResult(expected_total=len(all_prompts))

    for filename, content in files:
        global_order = parse_global_order_from_filename(filename)
        panel = by_order.get(global_order) if global_order is not None else None
        if panel is None:
            result.unmatched_filenames.append(filename)
            continue

        panel.image_path = _save_image(project_id, global_order, filename, content)
        panel.image_uploaded_at = datetime.now(timezone.utc)
        panel.status = "image_ready"
        result.matched.append(global_order)

    db.commit()

    uploaded_orders = {p.global_order for p in all_prompts if p.image_path}
    result.missing = sorted(set(by_order.keys()) - uploaded_orders)
    return result


def associate_single_upload(db: Session, project_id: str, global_order: int, filename: str, content: bytes) -> bool:
    repo = ImagePromptRepository(db)
    panel = repo.get_by_global_order(project_id, global_order)
    if panel is None:
        return False

    panel.image_path = _save_image(project_id, global_order, filename, content)
    panel.image_uploaded_at = datetime.now(timezone.utc)
    panel.status = "image_ready"
    db.commit()
    return True
