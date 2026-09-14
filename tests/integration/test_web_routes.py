def test_dashboard_empty_state(app_client):
    response = app_client.get("/")
    assert response.status_code == 200
    assert "Nenhum projeto em produção" in response.text


def test_new_project_form_renders(app_client):
    response = app_client.get("/projects/new")
    assert response.status_code == 200
    assert "Novo projeto" in response.text


def test_create_project_then_appears_on_dashboard(app_client):
    response = app_client.post(
        "/projects/new",
        data={
            "name": "Evangelho da Semana",
            "bible_reference": "Jo 3:16",
            "passage_text": "Texto de teste da passagem.",
            "biblia_visual_text": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]

    detail = app_client.get(location)
    assert detail.status_code == 200
    assert "Evangelho da Semana" in detail.text

    dashboard = app_client.get("/")
    assert "Evangelho da Semana" in dashboard.text
    assert "Nenhum projeto" not in dashboard.text


def test_create_project_missing_field_shows_error(app_client):
    response = app_client.post(
        "/projects/new",
        data={
            "name": "",
            "bible_reference": "Jo 3:16",
            "passage_text": "Texto",
            "biblia_visual_text": "",
        },
    )
    assert response.status_code == 400
    assert "Informe um nome" in response.text


def test_unknown_project_returns_404(app_client):
    response = app_client.get("/projects/nao-existe-123")
    assert response.status_code == 404


def test_diagnostics_page_renders(app_client):
    response = app_client.get("/diagnostics")
    assert response.status_code == 200
    assert "Diagnóstico" in response.text


def test_settings_page_renders(app_client):
    response = app_client.get("/settings")
    assert response.status_code == 200
    assert "Armazenamento" in response.text


def test_health_endpoint(app_client):
    response = app_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
