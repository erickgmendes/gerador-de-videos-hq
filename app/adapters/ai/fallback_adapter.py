"""Combina dois adapters de IA: tenta o principal, e se ele falhar (chave
inválida, limite de uso, rede etc.) tenta o backup antes de desistir.

Motivado por um caso real: o tier gratuito da Groq tem um teto diário de
requisições, e um projeto com muitas cenas pode esgotá-lo no meio da
geração de prompts de imagem — sem isso, o usuário precisava esperar o
teto resetar (até um dia) para continuar."""

from __future__ import annotations

from app.adapters.ai.base import AIProviderAdapter
from app.domain.errors import AIProviderError


class FallbackAIAdapter:
    def __init__(self, primary: AIProviderAdapter, secondary: AIProviderAdapter) -> None:
        self._primary = primary
        self._secondary = secondary

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        try:
            return self._primary.complete(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode)
        except AIProviderError as primary_error:
            try:
                return self._secondary.complete(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode)
            except AIProviderError as secondary_error:
                raise AIProviderError(
                    f"IA principal falhou ({primary_error}) e o backup também falhou ({secondary_error})."
                ) from secondary_error
