import json
import re

import pytest

from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.domain.states import ProjectState
from app.models.orm import Character, Job, Location, Project, Scene
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.repositories.scene_repository import SceneRepository
from app.schemas.project import ProjectCreate
from app.services.audio.service import run_audio_job
from app.services.image_prompts.service import compute_panel_count, run_image_prompts_job
from app.services.narration.service import run_narration_job
from app.services.project_service import ProjectService
from app.storage import project_storage
from tests.helpers import ENRICHMENT_JSON, NARRATION_TEXT, FakeAIAdapter, FakeTTSAdapter


@pytest.mark.parametrize(
    "duration,segment,expected",
    [
        (26.0, 5.0, 6),  # 26/5 = 5.2 -> arredonda pra cima
        (25.0, 5.0, 5),  # exato
        (4.0, 5.0, 1),  # cena curta ainda vira 1 painel
        (0.5, 5.0, 1),
        (60.0, 5.0, 12),
    ],
)
def test_compute_panel_count_rounds_up(duration, segment, expected):
    assert compute_panel_count(duration, segment) == expected


def test_compute_panel_count_never_zero_even_with_invalid_segment():
    assert compute_panel_count(10.0, 0) == 1
    assert compute_panel_count(10.0, -1) == 1


# --- pipeline completo, via fakes (sem chamar nenhuma API de verdade) ---


def _create_project_with_audio(db_session, db_session_factory) -> Project:
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Evangelho de Teste", bible_reference="Mc 1:16-20", passage_text="Texto de teste.")
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

    db_session.refresh(project)
    return project


def _create_image_prompts_job(db_session, project_id: str) -> Job:
    job = Job(project_id=project_id, job_type="image_prompts", status="running")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    return job


def _panel_response(count: int, new_characters: dict[str, str], new_locations: dict[str, str] | None = None) -> str:
    return json.dumps(
        {
            "new_characters": new_characters,
            "new_locations": new_locations or {},
            "panels": [
                {"shot_type": "medium shot", "description": f"Panel {i + 1} description."} for i in range(count)
            ],
        }
    )


class _PanelCountEchoAIAdapter:
    """Lê "QUANTIDADE DE PAINÉIS A GERAR: N" da mensagem e devolve
    exatamente N painéis — para testar o teto do projeto (Fase 4) sem
    precisar de uma lista de respostas canônicas por cena."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        self.calls.append(prompt)
        match = re.search(r"QUANTIDADE DE PAINÉIS A GERAR:\s*(\d+)", prompt)
        count = int(match.group(1)) if match else 1
        return _panel_response(count, {})


def test_run_image_prompts_job_caps_total_panels_for_the_whole_project(
    db_session, db_session_factory, test_settings
):
    # Reproduz o caso real do usuário: muitas cenas longas que, sem teto,
    # gerariam bem mais de 50 painéis (ele quer editar manualmente no
    # Kdenlive, sem depender de uma imagem a cada poucos segundos).
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Projeto Longo", bible_reference="Lc 1:1-25", passage_text="Texto de teste.")
    )
    scenes = [
        Scene(project_id=project.id, order=i, narration_excerpt=f"Cena {i}.", actual_duration=26.0)
        for i in range(1, 19)  # 18 cenas — mesma contagem do projeto real do usuário
    ]
    SceneRepository(db_session).replace_all(project.id, scenes)

    job = _create_image_prompts_job(db_session, project.id)
    ai = _PanelCountEchoAIAdapter()

    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    verify = db_session_factory()
    try:
        panels = ImagePromptRepository(verify).list_for_project(project.id)
        assert sum(1 for _ in panels) == 50
        assert len(panels) == 50
        # Numeração global sequencial e sem furos, mesmo cortada pelo teto.
        assert [p.global_order for p in panels] == list(range(1, 51))
    finally:
        verify.close()


def test_run_image_prompts_job_paces_calls_between_scenes(db_session, db_session_factory, test_settings, monkeypatch):
    # Regressão: relatado pelo usuário com dados reais — sem pausa entre
    # chamadas de cena, um lote de várias cenas disparava rápido demais e
    # estourava o teto de requisições/minuto do tier gratuito do Gemini
    # (bem menor que o de tokens), mesmo com o conteúdo cabendo no limite
    # de tokens. A pausa entre CENAS (não por tentativa de IA) resolve.
    from app.config import get_settings

    monkeypatch.setenv("IMAGE_PROMPT_SCENE_PAUSE_SECONDS", "9")
    get_settings.cache_clear()

    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.image_prompts.service.time.sleep", lambda seconds: sleep_calls.append(seconds))

    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Projeto Pausado", bible_reference="Lc 1:1-25", passage_text="Texto de teste.")
    )
    scenes = [
        Scene(project_id=project.id, order=i, narration_excerpt=f"Cena {i}.", actual_duration=4.0) for i in range(1, 4)
    ]
    SceneRepository(db_session).replace_all(project.id, scenes)

    job = _create_image_prompts_job(db_session, project.id)
    ai = _PanelCountEchoAIAdapter()

    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    # 3 cenas -> pausa só ENTRE elas, nunca antes da primeira nem depois
    # da última.
    assert sleep_calls == [9.0, 9.0]


def test_run_image_prompts_job_computes_panels_and_caches_characters(db_session, db_session_factory, test_settings):
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    assert len(scenes) == 2

    # Força uma cena curta (1 painel) e uma longa (3 painéis) para testar
    # o cálculo por duração de ponta a ponta.
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 13.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter(
        [
            _panel_response(1, {"Jesus": "a calm 30-year-old man wearing a beige tunic"}),
            _panel_response(3, {"Simão": "a rugged fisherman", "André": "a younger fisherman"}),
        ]
    )

    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job.id)
        refreshed_project = verify.get(Project, project.id)
        panels = ImagePromptRepository(verify).list_for_project(project.id)
        characters = {
            c.name: c.visual_description
            for c in verify.query(Character).filter(Character.project_id == project.id)
        }

        assert refreshed_job.status == "success"
        assert refreshed_project.state == ProjectState.IMAGE_PROMPTS_READY.value
        assert len(panels) == 4  # 1 + 3
        assert [p.global_order for p in panels] == [1, 2, 3, 4]
        assert panels[0].order_in_scene == 1
        assert panels[1].order_in_scene == 1 and panels[2].order_in_scene == 2  # cena 2, painéis 1..3
        assert "Jesus" in characters
        assert "Simão" in characters and "André" in characters
        assert "SINGLE COMIC PANEL" in panels[0].prompt_text
        assert "16:9" in panels[0].prompt_text
        assert "No text anywhere" in panels[0].prompt_text
    finally:
        verify.close()

    assert len(ai.calls) == 2

    # Regressão: exportação sem rótulo "PROMPT NNN" (pedido do usuário) —
    # só os textos, um por bloco, e linha em branco só ENTRE blocos, nunca
    # dentro de um (a ferramenta externa usa linha em branco como
    # separador de prompts; ver tests/unit/test_image_prompts_prompts.py
    # para o caso mais direto).
    export_text = project_storage.image_prompts_export_path(project.id).read_text(encoding="utf-8")
    assert "PROMPT " not in export_text
    prompt_blocks = export_text.split("\n\n")
    assert len(prompt_blocks) == 4  # um bloco de texto por painel, nada a mais
    for block in prompt_blocks:
        assert "\n" not in block
        assert block in {p.prompt_text for p in panels}


def test_run_image_prompts_job_ignores_redundant_new_character_from_ai(
    db_session, db_session_factory, test_settings
):
    # Regressão: relatado pelo usuário com dados reais — a IA às vezes
    # reenvia um personagem que JÁ está no cache dentro de "new_characters"
    # (apesar de instruída a não fazer isso). Sem a proteção, isso criava
    # uma segunda linha em `characters` com uma descrição DIFERENTE da
    # primeira, e cenas diferentes acabavam usando versões inconsistentes
    # do mesmo personagem (idade/roupa mudando de cena pra cena).
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter(
        [
            _panel_response(1, {"Jesus": "a calm man in a beige tunic"}),
            # A IA reenvia "Jesus" de novo (não deveria, mas acontece) com
            # uma descrição DIFERENTE — deve ser ignorada, não sobrescrever.
            _panel_response(1, {"Jesus": "a completely different appearance"}),
        ]
    )

    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    verify = db_session_factory()
    try:
        jesus_rows = verify.query(Character).filter(
            Character.project_id == project.id, Character.name == "Jesus"
        ).all()
        assert len(jesus_rows) == 1  # nunca duplica
        assert jesus_rows[0].visual_description == "a calm man in a beige tunic"  # mantém a primeira
    finally:
        verify.close()


def test_run_image_prompts_job_reuses_cached_character_description(db_session, db_session_factory, test_settings):
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter(
        [
            _panel_response(1, {"Jesus": "a calm man in a beige tunic"}),
            _panel_response(1, {"Simão": "a fisherman", "André": "another fisherman"}),
        ]
    )
    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    # A cena 2 cita "Jesus" (ver ENRICHMENT_JSON em tests/helpers.py) — a
    # descrição cacheada deve ter sido reaproveitada, não pedida de novo.
    second_call_message = ai.calls[1]["prompt"]
    assert "a calm man in a beige tunic" in second_call_message
    assert "PERSONAGENS JÁ DEFINIDOS" in second_call_message
    assert "PERSONAGENS MENCIONADOS NESTA CENA" in second_call_message
    assert "Simão" in second_call_message or "André" in second_call_message


def test_run_image_prompts_job_caches_and_reuses_location_description(
    db_session, db_session_factory, test_settings
):
    # Mesma lógica de continuidade já validada para personagens, agora
    # para cenários — a cena 2 deve reaproveitar a descrição do templo
    # gerada na cena 1, palavra por palavra, sem pedir de novo à IA.
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter(
        [
            _panel_response(1, {}, {"Temple of Jerusalem Courtyard": "an ancient stone courtyard with tall columns"}),
            _panel_response(1, {}, {}),
        ]
    )
    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    verify = db_session_factory()
    try:
        locations = {
            l.name: l.visual_description
            for l in verify.query(Location).filter(Location.project_id == project.id)
        }
        assert locations == {"Temple of Jerusalem Courtyard": "an ancient stone courtyard with tall columns"}
    finally:
        verify.close()

    second_call_message = ai.calls[1]["prompt"]
    assert "an ancient stone courtyard with tall columns" in second_call_message
    assert "CENÁRIOS JÁ DEFINIDOS" in second_call_message


def test_run_image_prompts_job_ignores_redundant_new_location_from_ai(
    db_session, db_session_factory, test_settings
):
    # Mesma guarda contra reenvio já validada para personagens, agora
    # para cenários — não pode duplicar nem sobrescrever com uma segunda
    # descrição diferente da primeira.
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter(
        [
            _panel_response(1, {}, {"Temple Courtyard": "an ancient stone courtyard"}),
            _panel_response(1, {}, {"Temple Courtyard": "a completely different place"}),
        ]
    )
    run_image_prompts_job(project.id, job.id, ai, db_session_factory)

    verify = db_session_factory()
    try:
        rows = verify.query(Location).filter(
            Location.project_id == project.id, Location.name == "Temple Courtyard"
        ).all()
        assert len(rows) == 1
        assert rows[0].visual_description == "an ancient stone courtyard"
    finally:
        verify.close()


def test_partial_generation_does_not_report_ready(db_session, db_session_factory, test_settings):
    # Reproduz um bug real encontrado testando com um projeto de verdade:
    # gerar painéis para só ALGUMAS cenas (ex.: job interrompido, ou uma
    # geração resumível que ainda não processou tudo) não pode reportar
    # IMAGE_PROMPTS_READY — precisa continuar em IMAGE_PROMPTS_GENERATING
    # até toda cena ter pelo menos um painel (mesmo padrão de
    # AUDIO_GENERATING como "repouso parcial" já usado no áudio).
    project = _create_project_with_audio(db_session, db_session_factory)
    scenes = SceneRepository(db_session).list_for_project(project.id)
    scenes[0].actual_duration = 4.0
    scenes[1].actual_duration = 4.0
    db_session.commit()

    job = _create_image_prompts_job(db_session, project.id)
    ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"})])

    # scene_ids só com a primeira cena — a segunda fica sem nenhum painel.
    run_image_prompts_job(project.id, job.id, ai, db_session_factory, scene_ids=[scenes[0].id])

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job.id)
        refreshed_project = verify.get(Project, project.id)
        assert refreshed_job.status == "success"
        assert refreshed_project.state == ProjectState.IMAGE_PROMPTS_GENERATING.value
    finally:
        verify.close()


def test_run_image_prompts_job_fails_gracefully_without_audio(db_session, db_session_factory, test_settings):
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Sem Áudio", bible_reference="Jo 1:1", passage_text="texto")
    )
    narration_job = Job(project_id=project.id, job_type="narration", status="running")
    db_session.add(narration_job)
    db_session.commit()
    db_session.refresh(narration_job)
    run_narration_job(
        project.id, narration_job.id, FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON]), db_session_factory
    )

    job = _create_image_prompts_job(db_session, project.id)
    run_image_prompts_job(project.id, job.id, FakeAIAdapter([]), db_session_factory)

    verify = db_session_factory()
    try:
        refreshed_job = verify.get(Job, job.id)
        assert refreshed_job.status == "failed"
        assert "áudio" in refreshed_job.error_message.lower()
    finally:
        verify.close()
