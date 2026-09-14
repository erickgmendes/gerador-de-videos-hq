import app.web.routes.audio as audio_routes
from tests.helpers import FakeTTSAdapter, create_test_project, generate_test_narration


def test_audio_tab_prompts_narration_first_when_no_scenes(app_client):
    project_id = create_test_project(app_client)

    response = app_client.get(f"/projects/{project_id}/audio")

    assert response.status_code == 200
    assert "Gere a narração primeiro" in response.text


def test_generate_audio_end_to_end_with_fake_tts(app_client, monkeypatch):
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    monkeypatch.setattr(audio_routes, "get_tts_adapter", lambda: FakeTTSAdapter())

    response = app_client.post(f"/projects/{project_id}/audio/gerar", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/audio")
    assert detail.status_code == 200
    assert "Áudio completo" in detail.text

    final_audio = app_client.get(f"/projects/{project_id}/audio/narracao.mp3")
    assert final_audio.status_code == 200
    assert final_audio.headers["content-type"] == "audio/mpeg"

    scene_audio = app_client.get(f"/projects/{project_id}/audio/cena/1.mp3")
    assert scene_audio.status_code == 200

    dashboard = app_client.get("/")
    assert "Áudio" in dashboard.text


def test_regenerate_single_scene_audio(app_client, monkeypatch):
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    monkeypatch.setattr(audio_routes, "get_tts_adapter", lambda: FakeTTSAdapter())
    app_client.post(f"/projects/{project_id}/audio/gerar", follow_redirects=False)

    # Descobre o id da cena 1 pela página renderizada (formulário por linha).
    detail = app_client.get(f"/projects/{project_id}/audio")
    assert "Regenerar" in detail.text

    from app.db import get_db

    db_gen = app_client.app.dependency_overrides[get_db]()
    db = next(db_gen)
    from app.repositories.scene_repository import SceneRepository

    scenes = SceneRepository(db).list_for_project(project_id)
    scene_one_id = scenes[0].id
    db.close()

    response = app_client.post(
        f"/projects/{project_id}/scenes/{scene_one_id}/audio/gerar", follow_redirects=False
    )
    assert response.status_code == 303

    detail_after = app_client.get(f"/projects/{project_id}/audio")
    assert "Áudio completo" in detail_after.text


def test_regenerate_all_audio_resynthesizes_every_scene(app_client, monkeypatch):
    project_id = create_test_project(app_client)
    generate_test_narration(app_client, monkeypatch, project_id)
    fake_tts = FakeTTSAdapter()
    monkeypatch.setattr(audio_routes, "get_tts_adapter", lambda: fake_tts)

    app_client.post(f"/projects/{project_id}/audio/gerar", follow_redirects=False)
    assert len(fake_tts.calls) == 2  # narração de teste tem 2 cenas

    detail = app_client.get(f"/projects/{project_id}/audio")
    assert "Gerar/Regenerar todo o áudio" in detail.text

    response = app_client.post(f"/projects/{project_id}/audio/regenerar-tudo", follow_redirects=False)
    assert response.status_code == 303

    # As 2 cenas já tinham áudio — "regenerar tudo" resintetiza as duas de
    # novo (diferente de POST .../audio/gerar, que só preencheria as que
    # ainda estivessem faltando).
    assert len(fake_tts.calls) == 4

    detail_after = app_client.get(f"/projects/{project_id}/audio")
    assert "Áudio completo" in detail_after.text


def test_missing_audio_file_returns_404(app_client):
    project_id = create_test_project(app_client)
    response = app_client.get(f"/projects/{project_id}/audio/narracao.mp3")
    assert response.status_code == 404


def test_audio_status_fragment_available(app_client):
    project_id = create_test_project(app_client)
    response = app_client.get(f"/projects/{project_id}/audio/status")
    assert response.status_code == 200
    assert "audio-status" in response.text


def test_audio_page_404_for_unknown_project(app_client):
    response = app_client.get("/projects/nao-existe/audio")
    assert response.status_code == 404
