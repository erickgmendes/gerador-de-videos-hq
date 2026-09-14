"""Orquestra a síntese de áudio: gera um MP3 por cena (artefato principal,
editável/substituível — mesmo padrão de imagens/vídeos por cena) e, quando
todas as cenas do projeto já têm áudio, concatena tudo num único arquivo
final (`audio/narracao.mp3`) com volume normalizado, sem cortes/saltos de
volume perceptíveis na emenda.

Roda em background — abre sua própria sessão via `session_factory`, igual
ao padrão já usado em app/services/narration/service.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.adapters.tts.base import TextToSpeechAdapter
from app.config import get_settings
from app.domain.errors import AudioAssemblyError, DomainError, TTSError
from app.domain.states import ProjectState
from app.models.orm import Artifact, Job, Project, Scene
from app.repositories.scene_repository import SceneRepository
from app.storage import project_storage


def _relative_path(project_id: str, path) -> str:
    root = project_storage.project_root(project_id)
    return str(path.relative_to(root.parent))


def _upsert_artifact(
    db: Session,
    *,
    project_id: str,
    scene_id: str | None,
    artifact_type: str,
    path,
    duration_seconds: float,
) -> None:
    stmt = select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.scene_id == scene_id,
        Artifact.type == artifact_type,
    )
    artifact = db.scalars(stmt).first()
    if artifact is None:
        artifact = Artifact(project_id=project_id, scene_id=scene_id, type=artifact_type)
        db.add(artifact)

    artifact.file_path = _relative_path(project_id, path)
    artifact.size_bytes = path.stat().st_size
    artifact.duration_seconds = duration_seconds
    artifact.source = "generated"
    artifact.status = "ready"


def _synthesize_scene(
    db: Session, project_id: str, scene: Scene, tts: TextToSpeechAdapter, settings
) -> None:
    out_path = project_storage.audio_scene_path(project_id, scene.order)
    meta = tts.synthesize(
        scene.narration_excerpt,
        voice=settings.tts_voice,
        rate=settings.tts_rate,
        out_path=out_path,
    )
    scene.actual_duration = meta.duration_seconds
    _upsert_artifact(
        db,
        project_id=project_id,
        scene_id=scene.id,
        artifact_type="narration_audio_scene",
        path=out_path,
        duration_seconds=meta.duration_seconds,
    )


def _merge_all_scenes(db: Session, project_id: str, scenes: list[Scene], ffmpeg: FFmpegAdapter) -> None:
    ordered = sorted(scenes, key=lambda s: s.order)
    chunk_paths = [project_storage.audio_scene_path(project_id, s.order) for s in ordered]
    out_path = project_storage.audio_final_path(project_id)
    ffmpeg.concat_audio(chunk_paths, out_path)
    duration = ffmpeg.get_duration(out_path)
    _upsert_artifact(
        db,
        project_id=project_id,
        scene_id=None,
        artifact_type="narration_audio",
        path=out_path,
        duration_seconds=duration,
    )


def run_audio_job(
    project_id: str,
    job_id: str,
    tts: TextToSpeechAdapter,
    ffmpeg: FFmpegAdapter,
    session_factory: sessionmaker,
    scene_ids: list[str] | None = None,
) -> None:
    db: Session = session_factory()
    try:
        project = db.get(Project, project_id)
        job = db.get(Job, job_id)
        if project is None or job is None:
            return

        try:
            settings = get_settings()
            all_scenes = SceneRepository(db).list_for_project(project_id)
            if not all_scenes:
                raise DomainError("Este projeto ainda não tem cenas — gere a narração primeiro.")

            if scene_ids is not None:
                targets = [s for s in all_scenes if s.id in scene_ids]
            else:
                targets = [s for s in all_scenes if s.actual_duration is None]

            for scene in targets:
                _synthesize_scene(db, project_id, scene, tts, settings)
                db.commit()  # cada cena persiste por conta própria — uma falha não perde as anteriores

            refreshed_scenes = SceneRepository(db).list_for_project(project_id)
            if all(s.actual_duration is not None for s in refreshed_scenes):
                _merge_all_scenes(db, project_id, refreshed_scenes, ffmpeg)
                project.state = ProjectState.AUDIO_READY.value
            else:
                project.state = ProjectState.AUDIO_GENERATING.value

            job.status = "success"
            job.progress_percent = 100
        except (TTSError, AudioAssemblyError, DomainError) as exc:
            # Volta para o último estado macro estável — cenas já
            # sintetizadas com sucesso continuam com actual_duration
            # preenchido e não são perdidas, só o estado macro não avança.
            project.state = ProjectState.NARRATION_READY.value
            job.status = "failed"
            job.error_message = str(exc)
        except Exception as exc:  # salvaguarda: nunca deixar o job travado em "running"
            project.state = ProjectState.NARRATION_READY.value
            job.status = "failed"
            job.error_message = f"Erro inesperado ao gerar o áudio. Tente novamente. ({exc.__class__.__name__})"
        finally:
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
