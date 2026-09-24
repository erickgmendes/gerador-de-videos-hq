"""Tenta uma cadeia ordenada de adapters de IA, em até duas passadas
completas pela cadeia inteira.

Cada adapter individual (Groq/Gemini/OpenRouter) faz só UMA tentativa por
chamada — nenhum deles espera e tenta de novo sozinho. Quem decide tentar
de novo é este módulo, e a estratégia é "pular para o próximo provedor",
não "insistir no mesmo": relatado pelo usuário com dados reais — com a
Groq no limite de uso e o Gemini sobrecarregado ao mesmo tempo, o design
anterior (cada adapter tentando 3x com 25s de espera antes de sequer
tentar o backup) podia gastar mais de 1 minuto só pra descobrir que os
dois primeiros provedores estavam mesmo fora, quando um provedor
diferente tinha uma chance real de responder na hora.

Se a cadeia INTEIRA falhar numa primeira passada (todo provedor
configurado, não só o primeiro), vale a pena esperar um pouco e tentar de
novo — pode ser um blip momentâneo afetando todo mundo ao mesmo tempo.
Daí as duas passadas, com uma espera só entre elas (não por tentativa)."""

from __future__ import annotations

import time

from app.adapters.ai.base import AIProviderAdapter
from app.domain.errors import AIProviderError

_MAX_PASSES = 2
_PASS_RETRY_WAIT_SECONDS = 20


class FallbackAIAdapter:
    def __init__(self, adapters: list[AIProviderAdapter]) -> None:
        if not adapters:
            raise ValueError("FallbackAIAdapter precisa de pelo menos 1 adapter.")
        self._adapters = adapters

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        errors: list[str] = []
        for pass_number in range(1, _MAX_PASSES + 1):
            errors = []
            for adapter in self._adapters:
                try:
                    return adapter.complete(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode)
                except AIProviderError as exc:
                    errors.append(str(exc))
            if pass_number < _MAX_PASSES:
                time.sleep(_PASS_RETRY_WAIT_SECONDS)
        raise AIProviderError("Todas as IAs configuradas falharam: " + " | ".join(errors))
