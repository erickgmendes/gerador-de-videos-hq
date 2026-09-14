import json

import app.web.routes.image_prompts as image_prompts_routes
from app.repositories.scene_repository import SceneRepository
from tests.helpers import (
    FakeAIAdapter,
    create_test_project,
    generate_test_audio,
    generate_test_narration,
    get_test_db_session,
)


def _panel_response(count: int, new_characters: dict[str, str] | None = None) -> str:
    return json.dumps(
        {
            "new_characters": new_characters or {},
            "panels": [
                {"shot_type": "medium shot", "description": f"Panel {i + 1} description."} for i in range(count)
            ],
        }
    )


def _setup_project_with_audio(app_client, monkeypatch) -> str:
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    generate_test_audio(app_client, monkeypatch, project_id)
    return project_id


def test_imagens_tab_prompts_narration_first(app_client):
    project_id = create_test_project(app_client)
    response = app_client.get(f"/projects/{project_id}/imagens")
    assert response.status_code == 200
    assert "Gere a narração primeiro" in response.text


def test_imagens_tab_prompts_audio_first(app_client, monkeypatch):
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)

    response = app_client.get(f"/projects/{project_id}/imagens")

    assert response.status_code == 200
    assert "Gere o áudio primeiro" in response.text


def test_imagens_tab_shows_panel_estimate_once_audio_ready(app_client, monkeypatch):
    project_id = _setup_project_with_audio(app_client, monkeypatch)

    response = app_client.get(f"/projects/{project_id}/imagens")

    assert response.status_code == 200
    assert "imagens" in response.text.lower()
    assert "Gerar prompts de imagem</button>" in response.text


def test_generate_image_prompts_end_to_end(app_client, monkeypatch):
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)

    response = app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/imagens")
    assert detail.status_code == 200
    assert "imagens recebidas" in detail.text or "faltam" in detail.text

    export = app_client.get(f"/projects/{project_id}/imagens/prompts.txt")
    assert export.status_code == 200
    assert "PROMPT 001" not in export.text  # sem rótulo — só os textos, separados por linha em branco
    assert "Panel 1 description" in export.text
    assert len(export.text.split("\n\n")) == 2  # 2 painéis, 1 por cena
    assert "SINGLE COMIC PANEL" in export.text

    individual = app_client.get(f"/projects/{project_id}/imagens/1/prompt.txt")
    assert individual.status_code == 200
    assert "Panel 1 description" in individual.text

    dashboard = app_client.get("/")
    assert "Prompts de imagem" in dashboard.text


def test_upload_images_in_bulk_matches_by_filename(app_client, monkeypatch):
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)

    response = app_client.post(
        f"/projects/{project_id}/imagens/upload",
        files=[
            ("files", ("001.png", b"fake-png-bytes-1", "image/png")),
            ("files", ("002.png", b"fake-png-bytes-2", "image/png")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/imagens")
    assert "Todas as 2 imagens recebidas" in detail.text

    image_file = app_client.get(f"/projects/{project_id}/imagens/1/arquivo")
    assert image_file.status_code == 200


def test_upload_single_image_corrects_one_panel(app_client, monkeypatch):
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)

    response = app_client.post(
        f"/projects/{project_id}/imagens/2/upload",
        files={"file": ("qualquer-nome.jpg", b"fake-bytes", "image/jpeg")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/imagens")
    assert "1/2 imagens recebidas" in detail.text


def test_regenerate_scene_prompts_clears_uploaded_image(app_client, monkeypatch):
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)
    app_client.post(
        f"/projects/{project_id}/imagens/1/upload",
        files={"file": ("001.png", b"fake-bytes", "image/png")},
        follow_redirects=False,
    )

    db = get_test_db_session(app_client)
    scene_one_id = SceneRepository(db).list_for_project(project_id)[0].id
    db.close()

    fake_ai_2 = FakeAIAdapter([_panel_response(1, {})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai_2)
    response = app_client.post(
        f"/projects/{project_id}/scenes/{scene_one_id}/imagens/gerar", follow_redirects=False
    )
    assert response.status_code == 303

    image_file = app_client.get(f"/projects/{project_id}/imagens/1/arquivo")
    assert image_file.status_code == 404  # a imagem antiga foi limpa junto com o prompt regenerado


def test_gerar_tudo_recalculates_panels_from_updated_audio_duration(app_client, monkeypatch):
    # Reproduz o caso relatado: usuário regenera o áudio (mudando as
    # durações reais das cenas) depois de já ter gerado os prompts de
    # imagem — os prompts antigos ficam com a contagem de painéis
    # desatualizada, e só "gerar" (que só preenche cenas sem painel) não
    # resolve, porque todas as cenas já têm painéis.
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)

    original_export = app_client.get(f"/projects/{project_id}/imagens/prompts.txt").text
    assert len(original_export.split("\n\n")) == 2

    # Simula "regenerar áudio": a cena passa a durar bem mais, então
    # agora precisaria de mais painéis do que os já gerados.
    db = get_test_db_session(app_client)
    scenes = SceneRepository(db).list_for_project(project_id)
    scenes[0].actual_duration = 40.0  # 40/5 = 8 painéis, antes só tinha 1
    db.commit()
    db.close()

    fake_ai_2 = FakeAIAdapter([_panel_response(8, {}), _panel_response(1, {})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai_2)
    response = app_client.post(f"/projects/{project_id}/imagens/gerar-tudo", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/imagens")
    assert "9/9 imagens" in detail.text or "9 imagens" in detail.text

    new_export = app_client.get(f"/projects/{project_id}/imagens/prompts.txt").text
    assert len(new_export.split("\n\n")) == 9  # 8 + 1, refletindo a nova duração


def test_gerar_tudo_also_clears_character_cache(app_client, monkeypatch):
    # Um reset completo precisa recomeçar a continuidade visual do zero —
    # senão descrições de personagens de uma geração anterior continuam
    # contaminando a nova (a mesma causa raiz do bug de continuidade).
    project_id = _setup_project_with_audio(app_client, monkeypatch)
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"}), _panel_response(1, {"Simão": "a fisherman"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)

    from app.models.orm import Character

    db = get_test_db_session(app_client)
    assert {c.name for c in db.query(Character).filter(Character.project_id == project_id)} == {"Jesus", "Simão"}
    db.close()

    fake_ai_2 = FakeAIAdapter([_panel_response(1, {"Jesus": "a different look entirely"}), _panel_response(1, {"Simão": "also different"})])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai_2)
    app_client.post(f"/projects/{project_id}/imagens/gerar-tudo", follow_redirects=False)

    db = get_test_db_session(app_client)
    jesus_rows = db.query(Character).filter(Character.project_id == project_id, Character.name == "Jesus").all()
    assert len(jesus_rows) == 1  # não duplicou
    assert jesus_rows[0].visual_description == "a different look entirely"  # pegou a versão nova, não a antiga
    db.close()


def test_imagens_status_fragment_available(app_client):
    project_id = create_test_project(app_client)
    response = app_client.get(f"/projects/{project_id}/imagens/status")
    assert response.status_code == 200
    assert "imagens-status" in response.text


def test_imagens_page_404_for_unknown_project(app_client):
    response = app_client.get("/projects/nao-existe/imagens")
    assert response.status_code == 404


def test_partial_generation_shows_continue_button_not_endless_spinner(app_client, monkeypatch):
    # Regressão: IMAGE_PROMPTS_GENERATING também é usado como "repouso
    # parcial" (nem toda cena tem painel ainda), não só "job rodando
    # agora". A página não pode mostrar o spinner com polling infinito
    # quando o job já terminou (sucesso ou falha) e só falta continuar.
    project_id = _setup_project_with_audio(app_client, monkeypatch)

    from app.models.orm import Job
    from app.services.image_prompts.service import run_image_prompts_job

    db = get_test_db_session(app_client)
    scenes = SceneRepository(db).list_for_project(project_id)
    first_scene_id = scenes[0].id
    job = Job(project_id=project_id, job_type="image_prompts", status="running")
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    from app.db import get_session_factory

    session_factory = app_client.app.dependency_overrides[get_session_factory]()
    fake_ai = FakeAIAdapter([_panel_response(1, {"Jesus": "a calm man"})])
    run_image_prompts_job(project_id, job_id, fake_ai, session_factory, scene_ids=[first_scene_id])

    response = app_client.get(f"/projects/{project_id}/imagens")

    assert response.status_code == 200
    assert "esta página se atualiza sozinha" not in response.text
    assert "Continuar geração" in response.text
    assert 'hx-trigger="load delay:3s"' not in response.text
