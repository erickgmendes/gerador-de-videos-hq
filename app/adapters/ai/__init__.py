from __future__ import annotations

from app.adapters.ai.base import AIProviderAdapter
from app.adapters.ai.fallback_adapter import FallbackAIAdapter
from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.adapters.ai.groq_adapter import GroqAdapter
from app.adapters.ai.openrouter_adapter import OpenRouterAdapter
from app.config import get_settings
from app.domain.errors import AIProviderError


def get_ai_adapter() -> AIProviderAdapter:
    """Monta a cadeia de IA na ordem Groq -> Gemini -> OpenRouter, usando
    só os provedores com chave configurada (funciona com 1, 2 ou os 3).
    Groq é a principal; Gemini é o backup de uso normal (tier gratuito bem
    mais folgado, ver ARCHITECTURE.md); OpenRouter é um terceiro nível só
    "por segurança" — tier gratuito baixo demais (50 requisições/dia) para
    uso normal, só entra se Groq E Gemini falharem ao mesmo tempo. Ver
    app/adapters/ai/fallback_adapter.py para a lógica de tentar cada um em
    ordem."""
    settings = get_settings()

    groq = (
        GroqAdapter(api_key=settings.groq_api_key, model=settings.groq_model, base_url=settings.groq_base_url)
        if settings.groq_api_key
        else None
    )
    gemini = (
        GeminiAdapter(api_key=settings.gemini_api_key, model=settings.gemini_model, base_url=settings.gemini_base_url)
        if settings.gemini_api_key
        else None
    )
    openrouter = (
        OpenRouterAdapter(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
        )
        if settings.openrouter_api_key
        else None
    )

    adapters = [a for a in (groq, gemini, openrouter) if a is not None]
    if not adapters:
        raise AIProviderError(
            "Nenhuma chave de IA configurada. Defina GROQ_API_KEY e/ou GEMINI_API_KEY "
            "(e opcionalmente OPENROUTER_API_KEY) no arquivo .env (ou na tela de Configurações) "
            "e reinicie a aplicação."
        )
    if len(adapters) == 1:
        return adapters[0]
    return FallbackAIAdapter(adapters)
