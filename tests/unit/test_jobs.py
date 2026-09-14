import json

from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.domain.states import ProjectState
from app.models.orm import Job
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.schemas.project import ProjectCreate
from app.services.audio.service import run_audio_job
from app.services.image_prompts.service import run_image_prompts_job
from app.services.jobs import reconcile_stale_jobs
from app.services.narration.service import run_narration_job
from app.services.project_service import ProjectService
from tests.helpers import ENRICHMENT_JSON, NARRATION_TEXT, FakeAIAdapter, FakeTTSAdapter


def _panel_response(count: int, new_characters=None) -> str:
    return json.dumps(
        {
            "new_characters": new_characters or {},
            "panels": [{"shot_type": "medium shot", "description": f"Panel {i + 1}"} for i in range(count)],
        }
    )


def test_reconcile_stale_jobs_marks_running_jobs_as_failed(db_session, test_settings):
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Teste", bible_reference="Jo 1:1", passage_text="texto")
    )
    job = Job(project_id=project.id, job_type="narration", status="running")
    db_session.add(job)
    db_session.commit()

    count = reconcile_stale_jobs(db_session)

    assert count == 1
    db_session.refresh(job)
    db_session.refresh(project)
    assert job.status == "failed"
    assert "reiniciada" in job.error_message
    assert project.state == ProjectState.CREATED.value


def test_reconcile_stale_jobs_recomputes_image_prompts_state_from_real_data(
    db_session, db_session_factory, test_settings
):
    # Regressão: encontrado testando com o projeto real do usuário — um
    # alvo fixo aqui reportava "áudio pronto" mesmo com 8 painéis reais já
    # gerados para uma cena, escondendo progresso de verdade do dashboard.
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Teste", bible_reference="Mc 1:16-20", passage_text="texto")
    )
    narration_job = Job(project_id=project.id, job_type="narration", status="running")
    db_session.add(narration_job)
    db_session.commit()
    db_session.refresh(narration_job)
    run_narration_job(
        project.id, narration_job.id, FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON]), db_session_factory
    )

    audio_job = Job(project_id=project.id, job_type="audio", status="running")
    db_session.add(audio_job)
    db_session.commit()
    db_session.refresh(audio_job)
    run_audio_job(project.id, audio_job.id, FakeTTSAdapter(), FFmpegAdapter(), db_session_factory)

    from app.repositories.scene_repository import SceneRepository

    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    # Gera painéis só para a primeira cena e SIMULA uma interrupção: o job
    # de image_prompts fica com status "running" (não passa pelo
    # try/finally normal do serviço).
    stuck_job = Job(project_id=project.id, job_type="image_prompts", status="running")
    db_session.add(stuck_job)
    db_session.commit()
    db_session.refresh(stuck_job)
    run_image_prompts_job(
        project.id,
        stuck_job.id,
        FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"})]),
        db_session_factory,
        scene_ids=[scenes[0].id],
    )
    # run_image_prompts_job já marcou este job como "success" — para
    # simular uma interrupção de verdade, força de volta para "running"
    # como se o processo tivesse morrido no meio de uma segunda chamada.
    db_session.refresh(stuck_job)
    stuck_job.status = "running"
    db_session.commit()

    count = reconcile_stale_jobs(db_session)

    assert count == 1
    db_session.refresh(project)
    panels = ImagePromptRepository(db_session).list_for_project(project.id)
    assert len(panels) == 1  # o painel real gerado antes da "queda" não foi perdido
    assert project.state == ProjectState.IMAGE_PROMPTS_GENERATING.value  # não "audio_ready"
