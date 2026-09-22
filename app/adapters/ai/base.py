"""Porta para o provedor de IA usado na geração de narração e prompts
(Fase 2+). Implementação concreta: GroqAdapter (GroqCloud), em
app/adapters/ai/groq_adapter.py — aqui só a interface."""

from __future__ import annotations

from typing import Protocol


class AIProviderAdapter(Protocol):
    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str: ...
