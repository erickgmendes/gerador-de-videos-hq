"""Testa FallbackAIAdapter (cadeia Groq -> Gemini -> OpenRouter, tentando
cada provedor uma vez por passada, com até duas passadas pela cadeia
inteira) e a lógica de composição em get_ai_adapter() — sem chamar
nenhuma API de verdade e sem esperas reais (time.sleep é mockado)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.adapters.ai import get_ai_adapter
from app.adapters.ai.fallback_adapter import FallbackAIAdapter
from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.adapters.ai.groq_adapter import GroqAdapter
from app.adapters.ai.openrouter_adapter import OpenRouterAdapter
from app.domain.errors import AIProviderError


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr("app.adapters.ai.fallback_adapter.time.sleep", lambda seconds: None)


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


def test_fallback_uses_second_immediately_when_first_fails_no_retry_on_first():
    # Regressão: relatado pelo usuário com dados reais — o design antigo
    # insistia no MESMO provedor (retry com espera) antes de sequer tentar
    # o próximo; agora pula pro próximo na hora, sem nenhuma espera.
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


def test_fallback_retries_whole_chain_once_after_a_wait_when_every_provider_fails(monkeypatch):
    # Se a cadeia INTEIRA falhar numa primeira passada, vale tentar de
    # novo (pode ser um blip afetando todo mundo ao mesmo tempo) — uma
    # segunda passada, com espera só entre elas, não por adapter.
    sleep_calls: list[int] = []
    monkeypatch.setattr("app.adapters.ai.fallback_adapter.time.sleep", lambda seconds: sleep_calls.append(seconds))

    first = MagicMock()
    first.complete.side_effect = [AIProviderError("Groq indisponível"), "resposta na segunda passada"]
    fallback = FallbackAIAdapter([first])

    result = fallback.complete("oi")

    assert result == "resposta na segunda passada"
    assert first.complete.call_count == 2
    assert len(sleep_calls) == 1  # esperou uma vez, entre a 1ª e a 2ª passada


def test_fallback_raises_combined_error_when_all_fail_both_passes():
    first = _fake_adapter(error=AIProviderError("Groq indisponível"))
    second = _fake_adapter(error=AIProviderError("Gemini indisponível"))
    third = _fake_adapter(error=AIProviderError("OpenRouter indisponível"))
    fallback = FallbackAIAdapter([first, second, third])

    with pytest.raises(AIProviderError, match="Groq indisponível.*Gemini indisponível.*OpenRouter indisponível"):
        fallback.complete("oi")

    # 2 passadas completas pelos 3 adapters
    assert first.complete.call_count == 2
    assert second.complete.call_count == 2
    assert third.complete.call_count == 2


def test_fallback_forwards_system_and_max_tokens():
    first = _fake_adapter(return_value="ok")
    second = _fake_adapter(return_value="ok")
    fallback = FallbackAIAdapter([first, second])

    fallback.complete("oi", system="regras", max_tokens=123)

    first.complete.assert_called_once_with("oi", system="regras", max_tokens=123, json_mode=False)


def test_fallback_works_with_a_single_adapter():
    # Desde que get_ai_adapter() passou a sempre envolver em
    # FallbackAIAdapter (mesmo com 1 só provedor configurado), não faz
    # mais sentido exigir 2+ — um só adapter ainda se beneficia da segunda
    # passada depois de uma falha transitória.
    only = _fake_adapter(return_value="ok")
    fallback = FallbackAIAdapter([only])

    assert fallback.complete("oi") == "ok"


def test_fallback_rejects_empty_adapter_list():
    with pytest.raises(ValueError):
        FallbackAIAdapter([])


def test_get_ai_adapter_returns_fallback_wrapping_groq_when_only_groq_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, FallbackAIAdapter)
    assert [type(a) for a in adapter._adapters] == [GroqAdapter]


def test_get_ai_adapter_returns_fallback_wrapping_gemini_when_only_gemini_configured(test_settings, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, FallbackAIAdapter)
    assert [type(a) for a in adapter._adapters] == [GeminiAdapter]


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


def test_get_ai_adapter_returns_fallback_wrapping_openrouter_when_only_openrouter_configured(
    test_settings, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    from app.config import get_settings

    get_settings.cache_clear()

    adapter = get_ai_adapter()

    assert isinstance(adapter, FallbackAIAdapter)
    assert [type(a) for a in adapter._adapters] == [OpenRouterAdapter]


def test_get_ai_adapter_raises_when_neither_configured(test_settings):
    from app.config import get_settings

    get_settings.cache_clear()

    with pytest.raises(AIProviderError, match="Nenhuma chave de IA configurada"):
        get_ai_adapter()
