import app.web.routes.narration as narration_routes
from tests.helpers import ENRICHMENT_JSON, NARRATION_TEXT, FakeAIAdapter, create_test_project

_create_project = create_test_project


def test_narracao_tab_shows_warning_when_key_not_configured(app_client):
    project_id = _create_project(app_client)

    response = app_client.get(f"/projects/{project_id}/narracao")

    assert response.status_code == 200
    assert "não configurada" in response.text
    assert "Gerar narração</button>" not in response.text


def test_generate_narracao_without_key_does_not_start_job(app_client):
    project_id = _create_project(app_client)

    response = app_client.post(f"/projects/{project_id}/narracao/gerar", follow_redirects=False)

    assert response.status_code == 303
    detail = app_client.get(f"/projects/{project_id}/narracao")
    assert "não configurada" in detail.text


def test_generate_narracao_end_to_end_with_fake_ai(app_client, monkeypatch):
    project_id = _create_project(app_client)
    fake_ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])
    monkeypatch.setattr(narration_routes, "get_ai_adapter", lambda: fake_ai)

    response = app_client.post(f"/projects/{project_id}/narracao/gerar", follow_redirects=False)
    assert response.status_code == 303

    detail = app_client.get(f"/projects/{project_id}/narracao")
    assert detail.status_code == 200
    assert "Narração gerada" in detail.text
    assert "O chamado à beira-mar" in detail.text
    assert "Jesus" in detail.text

    dashboard = app_client.get("/")
    assert "Narração" in dashboard.text


def test_generate_narracao_shows_flowing_text_without_scene_labels(app_client, monkeypatch):
    project_id = _create_project(app_client)
    fake_ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])
    monkeypatch.setattr(narration_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/narracao/gerar", follow_redirects=False)

    detail = app_client.get(f"/projects/{project_id}/narracao")
    assert "Texto para narração" in detail.text

    texto_corrido = app_client.get(f"/projects/{project_id}/narracao/texto-corrido")
    assert texto_corrido.status_code == 200
    assert "CENA" not in texto_corrido.text
    assert "Local:" not in texto_corrido.text
    assert "Jesus caminhava pela praia" in texto_corrido.text
    assert "Simão e André largaram as redes" in texto_corrido.text


def test_narracao_status_fragment_available(app_client):
    project_id = _create_project(app_client)
    response = app_client.get(f"/projects/{project_id}/narracao/status")
    assert response.status_code == 200
    assert "narracao-status" in response.text


def test_narracao_page_404_for_unknown_project(app_client):
    response = app_client.get("/projects/nao-existe/narracao")
    assert response.status_code == 404
