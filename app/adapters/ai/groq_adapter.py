"""Implementação de AIProviderAdapter usando a API da Groq (GroqCloud).

A API da Groq é compatível com o SDK OpenAI (base_url próprio) — não existe
SDK dedicado da Groq necessário. Ver https://console.groq.com/docs/openai.

O tier gratuito tem um limite de tokens por minuto (TPM) relativamente
baixo para a maioria dos modelos — duas chamadas em sequência (narração +
enriquecimento de cenas, ver app/services/narration/service.py) podem
esbarrar nele mesmo dentro do uso normal do app, não só em teste de carga
(confirmado ao vivo durante o desenvolvimento). Por isso o retry abaixo é
parte do comportamento esperado, não só uma salvaguarda de borda.
"""

from __future__ import annotations

import time

import openai

from app.domain.errors import AIProviderError

# Códigos HTTP que a Groq usa para "estourei o limite de uso" — 429 é o
# padrão OpenAI-compatível; 413 é o que a Groq de fato devolve na prática
# para "tokens por minuto excedido" e "requisição grande demais" (ambos
# transitórios, o limite é por janela de 60s).
_RATE_LIMIT_STATUS_CODES = {413, 429}
_MAX_ATTEMPTS = 3
_RETRY_WAIT_SECONDS = 25


class GroqAdapter:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.groq.com/openai/v1") -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(self, prompt: str, *, system: str | None = None, max_tokens: int = 4096) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._create_with_retry(messages, max_tokens)

        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice and choice.message else None
        if not text or not text.strip():
            raise AIProviderError("A IA não retornou conteúdo de texto.")
        return text

    def _create_with_retry(self, messages: list[dict[str, str]], max_tokens: int):
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    messages=messages,
                )
            except openai.AuthenticationError as exc:
                raise AIProviderError("Chave de API da Groq inválida ou não configurada.") from exc
            except openai.APIConnectionError as exc:
                raise AIProviderError("Não foi possível conectar à API da Groq. Verifique sua conexão.") from exc
            except openai.APIStatusError as exc:
                is_rate_limit = exc.status_code in _RATE_LIMIT_STATUS_CODES
                if is_rate_limit and attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_WAIT_SECONDS)
                    continue
                if is_rate_limit:
                    raise AIProviderError(
                        "Limite de uso gratuito da Groq atingido (tokens por minuto). "
                        "Tente novamente em cerca de um minuto."
                    ) from exc
                raise AIProviderError(f"Erro no serviço de IA (Groq), código {exc.status_code}.") from exc
        raise AssertionError("unreachable")  # loop sempre retorna ou levanta
