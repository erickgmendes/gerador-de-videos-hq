"""Testa FallbackAIAdapter (retry em cadeia Groq -> Gemini -> OpenRouter)
e a lógica de composição em get_ai_adapter() — sem chamar nenhuma API de
verdade."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.adapters.ai import get_ai_adapter
from app.adapters.ai.fallback_adapter import FallbackAIAdapter
from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.adapters.ai.groq_adapter import GroqAdapter
from app.adapters.ai.openrouter_adapter import OpenRouterAdapter
from app.domain.errors import AIProviderError


def _fake_adapter(return_value: str | None = None, error: Exception | None = None) -> MagicMock:
    adapter = MagicMock()
    if error is not None:
        adapter.complete.side_effect = error
    else:
        adapter.complete.return_value = return_value
    return adapter


def test_fallback_uses_first_only_when_it_succeeds():
    first = _fake_adapter(return_value="resposta principal")
    second = _fake_adapter(return_value="resposta backup")
    fallback = FallbackAIAdapter([first, second])

    result = fallback.complete("oi")

    assert result == "resposta principal"
    second.complete.assert_not_called()


def test_fallback_uses_second_when_first_fails():
    first = _fake_adapter(error=AIProviderError("Groq indisponível"))
    second = _fake_adapter(return_value="resposta backup")
    fallback = FallbackAIAdapter([first, second])

    result = fallback.complete("oi")

    assert result == "resposta backup"
    first.complete.assert_called_once()
    second.complete.assert_called_once()


def test_fallback_falls_through_to_third_tier_when_first_two_fail():
    first = _fake_adapter(error=AIProviderError("Groq indisponível"))
    second = _fake_adapter(error=AIProviderError("Gemini indisponível"))
    third = _fake_adapter(return_value="resposta de emergência")
    fallback = FallbackAIAdapter([first, second, third])

    result = fallback.complete("oi")

    assert result == "resposta de emergência"
    third.complete.assert_called_once()


def test_fallback_raises_combined_error_when_all_fail():
    first = _fake_adapter(error=AIProviderError("Groq indisponível"))
    second = _fake_adapter(error=AIProviderError("Gemini indisponível"))
    third = _fake_adapter(error=AIProviderError("OpenRouter indisponível"))
    fallback = FallbackAIAdapter([first, second, third])

    with pytest.raises(AIProviderError, match="Groq indisponível.*Gemini indisponível.*OpenRouter indisponível"):
        fallback.complete("oi")


def test_fallback_forwards_system_and_max_tokens():
    first = _fake_adapter(return_value="ok")
    second = _fake_adapter(return_value="ok")
    fallback = FallbackAIAdapter([first, second])

    fallback.complete("oi", system="regras", max_tokens=123)

    first.complete.assert_called_once_with("oi", system="regras", max_tokens=123, json_mode=False)


def test_fallback_requires_at_least_two_adapters():
    with pytest.raises(ValueError):
        FallbackAIAdapter([_fake_adapter()])


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
    assert [type(a) for a in adapter._adapters] == [GroqAdapter, GeminiAdapter]


def test_get_ai_adapter_returns_fallback_chain_in_order_when_all_three_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, FallbackAIAdapter)
    assert [type(a) for a in adapter._adapters] == [GroqAdapter, GeminiAdapter, OpenRouterAdapter]


def test_get_ai_adapter_returns_openrouter_when_only_openrouter_configured(test_settings, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, OpenRouterAdapter)


def test_get_ai_adapter_raises_when_neither_configured(test_settings):
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(AIProviderError, match="Nenhuma chave de IA configurada"):
        get_ai_adapter()
