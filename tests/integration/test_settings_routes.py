import app.config as app_config
from app.config import get_settings


def test_settings_page_shows_secret_field_not_configured(app_client):
    response = app_client.get("/settings")
    assert response.status_code == 200
    assert "Chave da API da Groq" in response.text
    assert "⚠ Não configurada" in response.text
    assert 'action="/settings/secrets/GROQ_API_KEY"' in response.text


def test_settings_page_shows_how_to_get_key_instructions(app_client):
    response = app_client.get("/settings")
    assert response.status_code == 200
    assert "Como obter essa chave" in response.text
    assert "console.groq.com" in response.text
    assert "Create API Key" in response.text


def test_saving_secret_takes_effect_immediately(app_client, tmp_path, monkeypatch):
    env_path = tmp_path / "app_client.env"
    monkeypatch.setattr(app_config, "get_env_file_path", lambda: env_path)
    get_settings.cache_clear()

    response = app_client.post(
        "/settings/secrets/GROQ_API_KEY", data={"value": "sk-from-ui"}, follow_redirects=False
    )
    assert response.status_code == 303

    assert get_settings().groq_api_key == "sk-from-ui"
    assert "GROQ_API_KEY=sk-from-ui" in env_path.read_text(encoding="utf-8")

    settings_page = app_client.get("/settings")
    assert "✓ Configurada" in settings_page.text

    get_settings.cache_clear()


def test_narracao_tab_links_to_settings_when_key_missing(app_client):
    create = app_client.post(
        "/projects/new",
        data={
            "name": "Evangelho de Teste",
            "bible_reference": "Jo 3:16",
            "passage_text": "Texto de teste.",
            "biblia_visual_text": "",
        },
        follow_redirects=False,
    )
    project_id = create.headers["location"].rsplit("/", 1)[-1]

    response = app_client.get(f"/projects/{project_id}/narracao")

    assert response.status_code == 200
    assert 'href="/settings#groq_api_key"' in response.text


def test_blank_secret_submission_does_not_erase_existing_value(app_client, tmp_path, monkeypatch):
    env_path = tmp_path / "app_client.env"
    monkeypatch.setattr(app_config, "get_env_file_path", lambda: env_path)
    get_settings.cache_clear()

    app_client.post("/settings/secrets/GROQ_API_KEY", data={"value": "sk-keep-me"}, follow_redirects=False)
    app_client.post("/settings/secrets/GROQ_API_KEY", data={"value": ""}, follow_redirects=False)

    assert get_settings().groq_api_key == "sk-keep-me"
    get_settings.cache_clear()


def test_unknown_secret_key_is_ignored(app_client, tmp_path, monkeypatch):
    env_path = tmp_path / "app_client.env"
    monkeypatch.setattr(app_config, "get_env_file_path", lambda: env_path)

    response = app_client.post(
        "/settings/secrets/SOME_RANDOM_VAR", data={"value": "hack"}, follow_redirects=False
    )

    assert response.status_code == 303
    assert not env_path.exists()
