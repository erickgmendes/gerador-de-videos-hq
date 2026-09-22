import json

from app.domain.states import ProjectState
from app.models.orm import Job, Project, Scene
from app.repositories.scene_repository import SceneRepository
from app.schemas.project import ProjectCreate
from app.services.narration.scene_parser import RawScene
from app.services.narration.service import (
    VIDEO_CLOSING,
    VIDEO_GREETING,
    _splice_greeting_and_closing,
    build_flowing_text,
    run_narration_job,
)
from app.services.project_service import ProjectService
from app.storage import project_storage
from tests.helpers import ENRICHMENT_JSON, NARRATION_TEXT, FailingAIAdapter, FakeAIAdapter


def _create_project(db_session) -> Project:
    return ProjectService(db_session).create_project(
        ProjectCreate(
            name="Evangelho de Teste",
            bible_reference="Mc 1:16-20",
            passage_text="Texto bíblico de teste.",
            biblia_visual_text="Jesus: túnica branca. Simão: manto marrom.",
        )
    )


def _create_job(db_session, project_id: str) -> Job:
    job = Job(project_id=project_id, job_type="narration", status="running")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def test_run_narration_job_success_writes_files_and_scenes(db_session, db_session_factory, test_settings):
    project = _create_project(db_session)
    job = _create_job(db_session, project.id)
    ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])

    run_narration_job(project.id, job.id, ai, db_session_factory)

    verify_session = db_session_factory()
    try:
        refreshed_project = verify_session.get(Project, project.id)
        refreshed_job = verify_session.get(Job, job.id)
        scenes = SceneRepository(verify_session).list_for_project(project.id)

        assert refreshed_project.state == ProjectState.NARRATION_READY.value
        assert refreshed_job.status == "success"
        assert len(scenes) == 2
        assert scenes[0].characters == ["Jesus"]
        assert scenes[1].characters == ["Simão", "André", "Jesus"]
        assert scenes[0].estimated_duration > 0

        narracao_path = project_storage.narracao_md_path(project.id)
        assert narracao_path.exists()
        assert "O chamado à beira-mar" in narracao_path.read_text(encoding="utf-8")

        cenas_json = json.loads(project_storage.scenes_json_path(project.id).read_text(encoding="utf-8"))
        assert len(cenas_json["scenes"]) == 2
        assert cenas_json["scenes"][0]["scene_id"] == "001"

        flowing_path = project_storage.narracao_texto_corrido_path(project.id)
        assert flowing_path.exists()
        flowing_text = flowing_path.read_text(encoding="utf-8")
        assert "CENA" not in flowing_text
        assert "Local:" not in flowing_text
        assert "Jesus caminhava pela praia" in flowing_text
        assert "Simão e André largaram as redes" in flowing_text
    finally:
        verify_session.close()

    assert len(ai.calls) == 2


def test_build_flowing_text_joins_scenes_in_order_without_labels():
    scenes = [
        Scene(project_id="p1", order=2, narration_excerpt="Segunda cena."),
        Scene(project_id="p1", order=1, narration_excerpt="Primeira cena."),
    ]

    result = build_flowing_text(scenes)

    assert result == "Primeira cena.\n\nSegunda cena."


def test_build_flowing_text_skips_empty_scenes():
    scenes = [
        Scene(project_id="p1", order=1, narration_excerpt="Só esta."),
        Scene(project_id="p1", order=2, narration_excerpt="   "),
    ]

    result = build_flowing_text(scenes)

    assert result == "Só esta."


def test_splice_greeting_and_closing_on_multiple_scenes():
    # Pedido do usuário: texto fixo, exato, sempre igual — não parafraseado
    # pela IA. Colado só na primeira/última cena, nunca no meio.
    scenes = [
        RawScene(order=1, title="A", location="", time="", narration="Primeira cena.", estimated_duration=1.0),
        RawScene(order=2, title="B", location="", time="", narration="Cena do meio.", estimated_duration=1.0),
        RawScene(order=3, title="C", location="", time="", narration="Última cena.", estimated_duration=1.0),
    ]

    _splice_greeting_and_closing(scenes)

    assert scenes[0].narration == f"{VIDEO_GREETING} Primeira cena."
    assert scenes[1].narration == "Cena do meio."
    assert scenes[2].narration == f"Última cena. {VIDEO_CLOSING}"
    # duração recalculada para refletir as palavras adicionadas
    assert scenes[0].estimated_duration > 1.0
    assert scenes[2].estimated_duration > 1.0


def test_splice_greeting_and_closing_on_single_scene_gets_both():
    scenes = [RawScene(order=1, title="A", location="", time="", narration="Única cena.", estimated_duration=1.0)]

    _splice_greeting_and_closing(scenes)

    assert scenes[0].narration == f"{VIDEO_GREETING} Única cena. {VIDEO_CLOSING}"


def test_run_narration_job_adds_fixed_greeting_and_closing(db_session, db_session_factory, test_settings):
    project = _create_project(db_session)
    job = _create_job(db_session, project.id)
    ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])

    run_narration_job(project.id, job.id, ai, db_session_factory)

    verify_session = db_session_factory()
    try:
        scenes = SceneRepository(verify_session).list_for_project(project.id)
        assert scenes[0].narration_excerpt.startswith(VIDEO_GREETING)
        assert scenes[-1].narration_excerpt.endswith(VIDEO_CLOSING)
        # nenhuma cena do meio deve ganhar as frases fixas
        assert VIDEO_GREETING not in scenes[-1].narration_excerpt
        assert VIDEO_CLOSING not in scenes[0].narration_excerpt

        flowing_text = project_storage.narracao_texto_corrido_path(project.id).read_text(encoding="utf-8")
        assert flowing_text.startswith(VIDEO_GREETING)
        assert flowing_text.endswith(VIDEO_CLOSING)
    finally:
        verify_session.close()


def test_run_narration_job_ai_failure_reverts_project_state(db_session, db_session_factory, test_settings):
    project = _create_project(db_session)
    job = _create_job(db_session, project.id)

    run_narration_job(project.id, job.id, FailingAIAdapter(), db_session_factory)

    verify_session = db_session_factory()
    try:
        refreshed_project = verify_session.get(Project, project.id)
        refreshed_job = verify_session.get(Job, job.id)
        assert refreshed_project.state == ProjectState.CREATED.value
        assert refreshed_job.status == "failed"
        assert "Chave inválida" in refreshed_job.error_message
    finally:
        verify_session.close()


def test_run_narration_job_keeps_narration_file_when_parsing_fails(db_session, db_session_factory, test_settings):
    project = _create_project(db_session)
    job = _create_job(db_session, project.id)
    ai = FakeAIAdapter(["Texto sem nenhuma estrutura de cena reconhecível."])

    run_narration_job(project.id, job.id, ai, db_session_factory)

    verify_session = db_session_factory()
    try:
        refreshed_project = verify_session.get(Project, project.id)
        refreshed_job = verify_session.get(Job, job.id)
        assert refreshed_project.state == ProjectState.CREATED.value
        assert refreshed_job.status == "failed"
        assert "cenas" in refreshed_job.error_message.lower()
    finally:
        verify_session.close()

    # A narração foi salva mesmo com a extração de cenas falhando.
    assert project_storage.narracao_md_path(project.id).exists()
    assert len(ai.calls) == 1


def test_run_narration_job_invalid_enrichment_json_fails_gracefully(db_session, db_session_factory, test_settings):
    project = _create_project(db_session)
    job = _create_job(db_session, project.id)
    ai = FakeAIAdapter([NARRATION_TEXT, "isto não é json"])

    run_narration_job(project.id, job.id, ai, db_session_factory)

    verify_session = db_session_factory()
    try:
        refreshed_project = verify_session.get(Project, project.id)
        refreshed_job = verify_session.get(Job, job.id)
        assert refreshed_project.state == ProjectState.CREATED.value
        assert refreshed_job.status == "failed"
    finally:
        verify_session.close()
