"""Testa o retry/tratamento de erro do GeminiAdapter contra um cliente OpenAI
mockado — sem chamar a API de verdade e sem esperas reais (time.sleep é
mockado). Espelha tests/unit/test_groq_adapter.py; a única diferença de
comportamento é que o Gemini só trata 429 como rate limit transitório
(a Groq também trata 413) — ver app/adapters/ai/gemini_adapter.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx2
import openai
import pytest

from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.domain.errors import AIProviderError


def _api_status_error(status_code: int, cls: type[openai.APIStatusError] = openai.APIStatusError):
    request = httpx2.Request("POST", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions")
    response = httpx2.Response(status_code, request=request)
    return cls(f"erro simulado {status_code}", response=response, body=None)


def _make_completion(text: str):
    completion = MagicMock()
    choice = MagicMock()
    choice.message.content = text
    completion.choices = [choice]
    return completion


@pytest.fixture()
def adapter(monkeypatch):
    monkeypatch.setattr("app.adapters.ai.gemini_adapter.time.sleep", lambda seconds: None)
    instance = GeminiAdapter(api_key="test-key", model="gemini-3.8-flash")
    instance._client = MagicMock()
    return instance


def test_complete_returns_text_on_success(adapter):
    adapter._client.chat.completions.create.return_value = _make_completion("olá mundo")

    result = adapter.complete("oi")

    assert result == "olá mundo"


def test_complete_retries_once_on_rate_limit_then_succeeds(adapter):
    adapter._client.chat.completions.create.side_effect = [
        _api_status_error(429),
        _make_completion("funcionou na segunda tentativa"),
    ]

    result = adapter.complete("oi")

    assert result == "funcionou na segunda tentativa"
    assert adapter._client.chat.completions.create.call_count == 2


def test_complete_gives_up_after_max_attempts_with_friendly_message(adapter):
    adapter._client.chat.completions.create.side_effect = _api_status_error(429)

    with pytest.raises(AIProviderError, match="Limite de uso gratuito"):
        adapter.complete("oi")

    assert adapter._client.chat.completions.create.call_count == 3


def test_complete_does_not_retry_non_rate_limit_status_errors(adapter):
    adapter._client.chat.completions.create.side_effect = _api_status_error(500)

    with pytest.raises(AIProviderError, match="código 500"):
        adapter.complete("oi")

    assert adapter._client.chat.completions.create.call_count == 1


def test_complete_raises_friendly_error_on_authentication_failure(adapter):
    adapter._client.chat.completions.create.side_effect = _api_status_error(
        401, cls=openai.AuthenticationError
    )

    with pytest.raises(AIProviderError, match="Chave de API do Gemini inválida"):
        adapter.complete("oi")

    assert adapter._client.chat.completions.create.call_count == 1


def test_complete_raises_friendly_error_when_response_is_empty(adapter):
    adapter._client.chat.completions.create.return_value = _make_completion("")

    with pytest.raises(AIProviderError, match="não retornou conteúdo"):
        adapter.complete("oi")


def test_complete_does_not_request_json_mode_by_default(adapter):
    adapter._client.chat.completions.create.return_value = _make_completion("texto livre")

    adapter.complete("oi")

    _, kwargs = adapter._client.chat.completions.create.call_args
    assert "response_format" not in kwargs


def test_complete_requests_json_mode_when_asked(adapter):
    adapter._client.chat.completions.create.return_value = _make_completion('{"ok": true}')

    result = adapter.complete("oi", json_mode=True)

    assert result == '{"ok": true}'
    _, kwargs = adapter._client.chat.completions.create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}
