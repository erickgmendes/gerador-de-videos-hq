from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.domain.states import ProjectState
from app.models.orm import Artifact, Job, Project, Scene
from app.services.audio.service import run_audio_job
from app.services.narration.service import run_narration_job
from app.storage import project_storage
from tests.helpers import (
    ENRICHMENT_JSON,
    NARRATION_TEXT,
    FailingTTSAdapter,
    FakeAIAdapter,
    FakeTTSAdapter,
)


def _create_project_with_scenes(db_session, db_session_factory) -> Project:
    """Reaproveita o pipeline real da Fase 2 (via FakeAIAdapter) para
    chegar num projeto com cenas de verdade, em vez de montar Scene rows
    manualmente — evita duplicar suposições sobre o formato entre as fases."""
    from app.schemas.project import ProjectCreate
    from app.services.project_service import ProjectService

    project = ProjectService(db_session).create_project(
        ProjectCreate(
            name="Evangelho de Teste",
            bible_reference="Mc 1:16-20",
            passage_text="Texto bíblico de teste.",
        )
    )
    job = Job(project_id=project.id, job_type="narration", status="running")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])
    run_narration_job(project.id, job.id, ai, db_session_factory)
    db_session.refresh(project)
    return project


def _create_audio_job(db_session, project_id: str) -> Job:
    job = Job(project_id=project_id, job_type="audio", status="running")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_run_audio_job_synthesizes_all_scenes_and_merges(db_session, db_session_factory, test_settings):
    project = _create_project_with_scenes(db_session, db_session_factory)
    job = _create_audio_job(db_session, project.id)
    tts = FakeTTSAdapter()
    ffmpeg = FFmpegAdapter()

    run_audio_job(project.id, job.id, tts, ffmpeg, db_session_factory)

    verify = db_session_factory()
    try:
        refreshed_project = verify.get(Project, project.id)
        refreshed_job = verify.get(Job, job.id)
        scenes = verify.query(Scene).filter(Scene.project_id == project.id).order_by(Scene.order).all()

        assert refreshed_job.status == "success"
        assert refreshed_project.state == ProjectState.AUDIO_READY.value
        assert len(scenes) == 2
        assert all(s.actual_duration is not None for s in scenes)

        scene_artifacts = (
            verify.query(Artifact)
            .filter(Artifact.project_id == project.id, Artifact.type == "narration_audio_scene")
            .all()
        )
        assert len(scene_artifacts) == 2

        final_artifact = (
            verify.query(Artifact)
            .filter(Artifact.project_id == project.id, Artifact.type == "narration_audio")
            .one_or_none()
        )
        assert final_artifact is not None
        assert final_artifact.duration_seconds > 0

        assert project_storage.audio_scene_path(project.id, 1).exists()
        assert project_storage.audio_scene_path(project.id, 2).exists()
        assert project_storage.audio_final_path(project.id).exists()
    finally:
        verify.close()

    assert len(tts.calls) == 2


def test_run_audio_job_regenerates_single_scene_and_remerges(db_session, db_session_factory, test_settings):
    project = _create_project_with_scenes(db_session, db_session_factory)
    job1 = _create_audio_job(db_session, project.id)
    tts = FakeTTSAdapter()
    ffmpeg = FFmpegAdapter()
    run_audio_job(project.id, job1.id, tts, ffmpeg, db_session_factory)

    verify = db_session_factory()
    scene_one = verify.query(Scene).filter(Scene.project_id == project.id, Scene.order == 1).one()
    scene_one_id = scene_one.id
    verify.close()

    job2 = _create_audio_job(db_session, project.id)
    run_audio_job(project.id, job2.id, tts, ffmpeg, db_session_factory, scene_ids=[scene_one_id])

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job2.id)
        refreshed_project = verify.get(Project, project.id)
        assert refreshed_job.status == "success"
        assert refreshed_project.state == ProjectState.AUDIO_READY.value
    finally:
        verify.close()

    # Duas cenas na primeira rodada + uma cena regenerada na segunda.
    assert len(tts.calls) == 3


def test_run_audio_job_partial_progress_when_some_scenes_fail(db_session, db_session_factory, test_settings):
    project = _create_project_with_scenes(db_session, db_session_factory)
    job = _create_audio_job(db_session, project.id)

    run_audio_job(project.id, job.id, FailingTTSAdapter(), FFmpegAdapter(), db_session_factory)

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job.id)
        refreshed_project = verify.get(Project, project.id)
        scenes = verify.query(Scene).filter(Scene.project_id == project.id).all()

        assert refreshed_job.status == "failed"
        assert refreshed_project.state == ProjectState.NARRATION_READY.value
        assert all(s.actual_duration is None for s in scenes)
    finally:
        verify.close()


def test_run_audio_job_without_scenes_fails_gracefully(db_session, db_session_factory, test_settings):
    from app.schemas.project import ProjectCreate
    from app.services.project_service import ProjectService

    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Sem Cenas", bible_reference="Jo 1:1", passage_text="texto")
    )
    job = _create_audio_job(db_session, project.id)

    run_audio_job(project.id, job.id, FakeTTSAdapter(), FFmpegAdapter(), db_session_factory)

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job.id)
        assert refreshed_job.status == "failed"
        assert "cenas" in refreshed_job.error_message.lower()
    finally:
        verify.close()
