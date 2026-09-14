import pytest

import app.config as app_config
from app.config import get_settings
from app.domain.errors import ValidationError
from app.services import settings_service


@pytest.fixture()
def env_path(tmp_path, monkeypatch, test_settings):
    path = tmp_path / "fake.env"
    monkeypatch.setattr(app_config, "get_env_file_path", lambda: path)
    yield path
    get_settings.cache_clear()


def test_set_secret_creates_env_file_when_missing(env_path):
    settings_service.set_secret("GROQ_API_KEY", "sk-test-123")

    assert env_path.exists()
    assert "GROQ_API_KEY=sk-test-123" in env_path.read_text(encoding="utf-8")


def test_set_secret_updates_existing_key_and_preserves_other_lines(env_path):
    env_path.write_text("GROQ_API_KEY=old-value\nGROQ_MODEL=openai/gpt-oss-120b\n", encoding="utf-8")

    settings_service.set_secret("GROQ_API_KEY", "new-value")

    content = env_path.read_text(encoding="utf-8")
    assert "GROQ_API_KEY=new-value" in content
    assert "GROQ_MODEL=openai/gpt-oss-120b" in content
    assert "old-value" not in content


def test_set_secret_blank_value_is_ignored(env_path):
    env_path.write_text("GROQ_API_KEY=keep-me\n", encoding="utf-8")

    settings_service.set_secret("GROQ_API_KEY", "   ")

    assert "GROQ_API_KEY=keep-me" in env_path.read_text(encoding="utf-8")


def test_set_secret_rejects_unknown_key(env_path):
    with pytest.raises(ValidationError):
        settings_service.set_secret("SOME_RANDOM_VAR", "value")


def test_set_secret_takes_effect_immediately_without_restart(env_path, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")  # garante que não há override de ambiente
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()
    assert get_settings().groq_api_key is None

    settings_service.set_secret("GROQ_API_KEY", "sk-live")

    assert get_settings().groq_api_key == "sk-live"


def test_list_secret_fields_reflects_configured_state(env_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    get_settings.cache_clear()

    fields_before = settings_service.list_secret_fields()
    assert fields_before[0].key == "GROQ_API_KEY"
    assert fields_before[0].configured is False

    settings_service.set_secret("GROQ_API_KEY", "sk-live")

    fields_after = settings_service.list_secret_fields()
    assert fields_after[0].configured is True
