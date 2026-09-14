from __future__ import annotations

from app.adapters.ai.base import AIProviderAdapter
from app.adapters.ai.fallback_adapter import FallbackAIAdapter
from app.adapters.ai.gemini_adapter import GeminiAdapter
from app.adapters.ai.groq_adapter import GroqAdapter
from app.config import get_settings
from app.domain.errors import AIProviderError


def get_ai_adapter() -> AIProviderAdapter:
    """Groq é a IA principal; o Gemini (gratuito, compatível com OpenAI)
    entra automaticamente como backup se ambos estiverem configurados —
    ver app/adapters/ai/fallback_adapter.py. Funciona com só um dos dois
    configurado também."""
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

    if groq and gemini:
        return FallbackAIAdapter(primary=groq, secondary=gemini)
    if groq:
        return groq
    if gemini:
        return gemini

    raise AIProviderError(
        "Nenhuma chave de IA configurada. Defina GROQ_API_KEY e/ou GEMINI_API_KEY "
        "no arquivo .env (ou na tela de Configurações) e reinicie a aplicação."
    )
