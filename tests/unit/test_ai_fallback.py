"""Testa FallbackAIAdapter (retry cruzado Groq -> Gemini) e a lógica de
composição em get_ai_adapter() — sem chamar nenhuma API de verdade."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.adapters.ai import get_ai_adapter
from app.adapters.ai.fallback_adapter import FallbackAIAdapter
from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.adapters.ai.groq_adapter import GroqAdapter
from app.domain.errors import AIProviderError


def _fake_adapter(return_value: str | None = None, error: Exception | None = None) -> MagicMock:
    adapter = MagicMock()
    if error is not None:
        adapter.complete.side_effect = error
    else:
        adapter.complete.return_value = return_value
    return adapter


def test_fallback_uses_primary_only_when_it_succeeds():
    primary = _fake_adapter(return_value="resposta principal")
    secondary = _fake_adapter(return_value="resposta backup")
    fallback = FallbackAIAdapter(primary=primary, secondary=secondary)

    result = fallback.complete("oi")

    assert result == "resposta principal"
    secondary.complete.assert_not_called()


def test_fallback_uses_secondary_when_primary_fails():
    primary = _fake_adapter(error=AIProviderError("Groq indisponível"))
    secondary = _fake_adapter(return_value="resposta backup")
    fallback = FallbackAIAdapter(primary=primary, secondary=secondary)

    result = fallback.complete("oi")

    assert result == "resposta backup"
    primary.complete.assert_called_once()
    secondary.complete.assert_called_once()


def test_fallback_raises_combined_error_when_both_fail():
    primary = _fake_adapter(error=AIProviderError("Groq indisponível"))
    secondary = _fake_adapter(error=AIProviderError("Gemini indisponível"))
    fallback = FallbackAIAdapter(primary=primary, secondary=secondary)

    with pytest.raises(AIProviderError, match="Groq indisponível.*Gemini indisponível"):
        fallback.complete("oi")


def test_fallback_forwards_system_and_max_tokens():
    primary = _fake_adapter(return_value="ok")
    secondary = _fake_adapter(return_value="ok")
    fallback = FallbackAIAdapter(primary=primary, secondary=secondary)

    fallback.complete("oi", system="regras", max_tokens=123)

    primary.complete.assert_called_once_with("oi", system="regras", max_tokens=123)


def test_get_ai_adapter_returns_groq_when_only_groq_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, GroqAdapter)


def test_get_ai_adapter_returns_gemini_when_only_gemini_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, GeminiAdapter)


def test_get_ai_adapter_returns_fallback_when_both_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, FallbackAIAdapter)
    assert isinstance(adapter._primary, GroqAdapter)
    assert isinstance(adapter._secondary, GeminiAdapter)


def test_get_ai_adapter_raises_when_neither_configured(test_settings):
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(AIProviderError, match="Nenhuma chave de IA configurada"):
        get_ai_adapter()
