"""Combina uma cadeia ordenada de adapters de IA: tenta cada um na ordem
dada, e só passa para o próximo se o atual falhar (chave inválida, limite
de uso, rede etc.) — desiste só depois que todos falharem.

Motivado por um caso real: o tier gratuito da Groq tem um teto diário de
requisições, e um projeto com muitas cenas pode esgotá-lo no meio da
geração de prompts de imagem — sem isso, o usuário precisava esperar o
teto resetar (até um dia) para continuar. Generalizado de 2 para N
adapters quando um terceiro nível (OpenRouter, só "por segurança") foi
adicionado — ver app/adapters/ai/__init__.py para a ordem/composição real
(Groq -> Gemini -> OpenRouter)."""

from __future__ import annotations

from app.adapters.ai.base import AIProviderAdapter
from app.domain.errors import AIProviderError


class FallbackAIAdapter:
    def __init__(self, adapters: list[AIProviderAdapter]) -> None:
        if len(adapters) < 2:
            raise ValueError("FallbackAIAdapter precisa de pelo menos 2 adapters.")
        self._adapters = adapters

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        errors: list[str] = []
        for adapter in self._adapters:
            try:
                return adapter.complete(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode)
            except AIProviderError as exc:
                errors.append(str(exc))
        raise AIProviderError("Todas as IAs configuradas falharam: " + " | ".join(errors))
