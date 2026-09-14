"""Orquestra a geração da narração: chama a IA para o roteiro, faz o
parsing determinístico das cenas, chama a IA de novo só para enriquecer
os campos semânticos, e persiste tudo (arquivos + banco).

Roda em background (ver app/web/routes/narration.py) — por isso abre sua
própria sessão de banco via `session_factory`, em vez de depender de uma
sessão vinda de uma requisição HTTP já encerrada.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai.base import AIProviderAdapter
from app.domain.errors import AIProviderError, DomainError, NarrationParsingError
from app.domain.states import ProjectState
from app.models.orm import Job, Project, Scene
from app.repositories.scene_repository import SceneRepository
from app.services.narration.prompts import (
    NARRATION_SYSTEM_PROMPT,
    SCENE_EXTRACTION_SYSTEM_PROMPT,
    build_narration_user_message,
    build_scene_extraction_user_message,
)
from app.services.narration.scene_parser import RawScene, parse_scene_blocks
from app.storage import project_storage

# 8192 é o teto de max_tokens do groq/compound (modelo padrão, ver
# app/config.py) — pedir mais do que isso é rejeitado com 400.
NARRATION_MAX_TOKENS = 8192
EXTRACTION_MAX_TOKENS = 4096


def _strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


def _parse_enrichment(raw_json: str) -> dict[int, dict]:
    try:
        data = json.loads(_strip_code_fences(raw_json))
    except json.JSONDecodeError as exc:
        raise NarrationParsingError("A IA não retornou um JSON válido ao enriquecer as cenas.") from exc
    if not isinstance(data, list):
        raise NarrationParsingError("O enriquecimento das cenas não veio no formato de lista esperado.")
    return {int(item["order"]): item for item in data if "order" in item}


def _build_scene_rows(project_id: str, raw_scenes: list[RawScene], enrichment: dict[int, dict]) -> list[Scene]:
    rows: list[Scene] = []
    for raw in raw_scenes:
        extra = enrichment.get(raw.order, {})
        rows.append(
            Scene(
                project_id=project_id,
                order=raw.order,
                location=raw.location,
                time=raw.time,
                characters=list(extra.get("characters", [])),
                action=str(extra.get("action", "")),
                emotion=str(extra.get("emotion", "")),
                narration_excerpt=raw.narration,
                visual_importance=str(extra.get("visual_importance", "")),
                estimated_duration=raw.estimated_duration,
                status="ready",
            )
        )
    return rows


def build_flowing_text(scenes: list[Scene]) -> str:
    """Só o texto narrado, em ordem, sem os rótulos CENA/Local/Momento —
    para o narrador ler/gravar de forma contínua, e para a Fase 3 (TTS)
    sintetizar (não faz sentido narrar em voz alta "CENA 3, Local: ...")."""
    ordered = sorted(scenes, key=lambda s: s.order)
    return "\n\n".join(scene.narration_excerpt.strip() for scene in ordered if scene.narration_excerpt.strip())


def _write_cenas_json(project_id: str, scenes: list[Scene]) -> None:
    payload = {
        "schema_version": 1,
        "project_id": project_id,
        "scenes": [
            {
                "scene_id": f"{scene.order:03d}",
                "order": scene.order,
                "location": scene.location,
                "time": scene.time,
                "characters": scene.characters,
                "action": scene.action,
                "emotion": scene.emotion,
                "narration": scene.narration_excerpt,
                "visual_importance": scene.visual_importance,
                "estimated_duration": scene.estimated_duration,
                "actual_duration": scene.actual_duration,
                "image_prompt_id": None,
                "video_prompt_id": None,
                "status": scene.status,
            }
            for scene in scenes
        ],
    }
    project_storage.scenes_json_path(project_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def run_narration_job(
    project_id: str,
    job_id: str,
    ai: AIProviderAdapter,
    session_factory: sessionmaker,
) -> None:
    db: Session = session_factory()
    try:
        project = db.get(Project, project_id)
        job = db.get(Job, job_id)
        if project is None or job is None:
            return

        try:
            passage_text = project_storage.input_passagem_path(project_id).read_text(encoding="utf-8")
            biblia_visual_text = project_storage.input_biblia_visual_path(project_id).read_text(encoding="utf-8")

            narration_text = ai.complete(
                build_narration_user_message(
                    bible_reference=project.bible_reference,
                    passage_text=passage_text,
                    biblia_visual_text=biblia_visual_text,
                ),
                system=NARRATION_SYSTEM_PROMPT,
                max_tokens=NARRATION_MAX_TOKENS,
            )
            # Salva o roteiro ANTES de tentar interpretá-lo — nada se perde
            # mesmo que o parsing ou o enriquecimento falhem depois.
            project_storage.narracao_md_path(project_id).write_text(narration_text, encoding="utf-8")

            raw_scenes = parse_scene_blocks(narration_text)
            if not raw_scenes:
                raise NarrationParsingError(
                    "A narração foi gerada e salva, mas não foi possível identificar as cenas "
                    "automaticamente (a IA não seguiu o formato esperado). Tente gerar novamente."
                )

            enrichment_raw = ai.complete(
                build_scene_extraction_user_message(
                    raw_scenes=[
                        {"order": s.order, "location": s.location, "time": s.time, "narration": s.narration}
                        for s in raw_scenes
                    ],
                    biblia_visual_text=biblia_visual_text,
                ),
                system=SCENE_EXTRACTION_SYSTEM_PROMPT,
                max_tokens=EXTRACTION_MAX_TOKENS,
            )
            enrichment = _parse_enrichment(enrichment_raw)

            scene_rows = _build_scene_rows(project_id, raw_scenes, enrichment)
            SceneRepository(db).replace_all(project_id, scene_rows)
            _write_cenas_json(project_id, scene_rows)
            project_storage.narracao_texto_corrido_path(project_id).write_text(
                build_flowing_text(scene_rows), encoding="utf-8"
            )

            project.state = ProjectState.NARRATION_READY.value
            job.status = "success"
            job.progress_percent = 100
        except (AIProviderError, NarrationParsingError, DomainError) as exc:
            project.state = ProjectState.CREATED.value
            job.status = "failed"
            job.error_message = str(exc)
        except Exception as exc:  # salvaguarda: nunca deixar o job travado em "running"
            project.state = ProjectState.CREATED.value
            job.status = "failed"
            job.error_message = "Erro inesperado ao gerar a narração. Tente novamente."
            job.error_message += f" ({exc.__class__.__name__})"
        finally:
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
