import json

import app.web.routes.image_prompts as image_prompts_routes
from tests.helpers import create_test_project, generate_test_audio, generate_test_narration


def _panel_response(count: int) -> str:
    return json.dumps(
        {
            "new_characters": {},
            "new_locations": {},
            "panels": [
                {"shot_type": "medium shot", "description": f"Panel {i + 1} description."} for i in range(count)
            ],
        }
    )


def _setup_project_with_images(app_client, monkeypatch) -> str:
    """Projeto com narração, áudio, prompts de imagem gerados E as duas
    imagens (uma por cena, mesmo padrão de test_image_prompts_routes.py)
    já enviadas — pré-requisito para a Fase 5 poder gerar os prompts de
    vídeo."""
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    generate_test_audio(app_client, monkeypatch, project_id)
    from tests.helpers import FakeAIAdapter

    fake_ai = FakeAIAdapter([_panel_response(1), _panel_response(1)])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)
    app_client.post(
        f"/projects/{project_id}/imagens/upload",
        files=[
            ("files", ("001.png", b"fake-png-bytes-1", "image/png")),
            ("files", ("002.png", b"fake-png-bytes-2", "image/png")),
        ],
        follow_redirects=False,
    )
    return project_id


def test_videos_tab_prompts_images_first_when_no_panels(app_client):
    project_id = create_test_project(app_client)

    response = app_client.get(f"/projects/{project_id}/videos")

    assert response.status_code == 200
    assert "Gere e envie as imagens primeiro" in response.text


def test_videos_tab_prompts_images_first_when_images_incomplete(app_client, monkeypatch):
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    generate_test_audio(app_client, monkeypatch, project_id)
    from tests.helpers import FakeAIAdapter

    fake_ai = FakeAIAdapter([_panel_response(1), _panel_response(1)])
    monkeypatch.setattr(image_prompts_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/imagens/gerar", follow_redirects=False)
    # só uma das duas imagens enviada
    app_client.post(
        f"/projects/{project_id}/imagens/1/upload",
        files={"file": ("001.png", b"fake-bytes", "image/png")},
        follow_redirects=False,
    )

    response = app_client.get(f"/projects/{project_id}/videos")

    assert response.status_code == 200
    assert "termine o upload na aba Imagens" in response.text


def test_generate_video_prompts_end_to_end(app_client, monkeypatch):
    project_id = _setup_project_with_images(app_client, monkeypatch)

    response = app_client.post(f"/projects/{project_id}/videos/gerar", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/videos")
    assert detail.status_code == 200
    assert "vídeos recebidas" not in detail.text  # regressão: rótulo certo é "vídeos", não "imagens"
    assert "faltam 2" in detail.text or "vídeos recebidos" in detail.text

    export = app_client.get(f"/projects/{project_id}/videos/prompts.txt")
    assert export.status_code == 200
    assert len(export.text.split("\n\n")) == 2
    assert "wine" in export.text.lower()

    individual = app_client.get(f"/projects/{project_id}/videos/1/prompt.txt")
    assert individual.status_code == 200
    assert "subtle" in individual.text.lower()

    dashboard = app_client.get("/")
    assert "Vídeos" in dashboard.text


def test_upload_videos_in_bulk_matches_by_filename(app_client, monkeypatch):
    project_id = _setup_project_with_images(app_client, monkeypatch)
    app_client.post(f"/projects/{project_id}/videos/gerar", follow_redirects=False)

    response = app_client.post(
        f"/projects/{project_id}/videos/upload",
        files=[
            ("files", ("001.mp4", b"fake-mp4-bytes-1", "video/mp4")),
            ("files", ("002.mp4", b"fake-mp4-bytes-2", "video/mp4")),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/videos")
    assert "Todos os 2 vídeos recebidos" in detail.text

    video_file = app_client.get(f"/projects/{project_id}/videos/1/arquivo")
    assert video_file.status_code == 200


def test_upload_single_video_corrects_one_panel(app_client, monkeypatch):
    project_id = _setup_project_with_images(app_client, monkeypatch)
    app_client.post(f"/projects/{project_id}/videos/gerar", follow_redirects=False)

    response = app_client.post(
        f"/projects/{project_id}/videos/2/upload",
        files={"file": ("qualquer-nome.mov", b"fake-bytes", "video/quicktime")},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/videos")
    assert "1/2 vídeos recebidos" in detail.text


def test_gerar_tudo_videos_clears_existing_uploads(app_client, monkeypatch):
    project_id = _setup_project_with_images(app_client, monkeypatch)
    app_client.post(f"/projects/{project_id}/videos/gerar", follow_redirects=False)
    app_client.post(
        f"/projects/{project_id}/videos/upload",
        files=[
            ("files", ("001.mp4", b"fake-mp4-bytes-1", "video/mp4")),
            ("files", ("002.mp4", b"fake-mp4-bytes-2", "video/mp4")),
        ],
        follow_redirects=False,
    )

    response = app_client.post(f"/projects/{project_id}/videos/gerar-tudo", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/videos")
    assert "faltam 2" in detail.text  # os vídeos enviados foram limpos, prompts novos gerados


def test_videos_page_404_for_unknown_project(app_client):
    response = app_client.get("/projects/nao-existe/videos")
    assert response.status_code == 404
