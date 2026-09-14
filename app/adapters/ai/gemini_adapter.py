"""Implementação de AIProviderAdapter usando a API do Google Gemini, via
a interface compatível com OpenAI que o Gemini expõe — dispensa um SDK
próprio. Ver https://ai.google.dev/gemini-api/docs/openai.

Backup da Groq (`groq_adapter.py`): estrutura e comportamento de retry
propositalmente iguais (mesma filosofia de rate limit transitório), mas
mantidos como arquivos separados em vez de uma base compartilhada — são
poucas linhas, e isolados assim cada adapter pode evoluir sozinho (ex.:
peculiaridades de erro de um provedor) sem arriscar o outro, que já está
em produção. Ver `app/adapters/ai/__init__.py` para como os dois se
combinam num fallback automático.
"""

from __future__ import annotations

import time

import openai

from app.domain.errors import AIProviderError

_RATE_LIMIT_STATUS_CODES = {429}
_MAX_ATTEMPTS = 3
_RETRY_WAIT_SECONDS = 25


class GeminiAdapter:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
    ) -> None:
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
            raise AIProviderError("A IA (Gemini) não retornou conteúdo de texto.")
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
                raise AIProviderError("Chave de API do Gemini inválida ou não configurada.") from exc
            except openai.APIConnectionError as exc:
                raise AIProviderError("Não foi possível conectar à API do Gemini. Verifique sua conexão.") from exc
            except openai.APIStatusError as exc:
                is_rate_limit = exc.status_code in _RATE_LIMIT_STATUS_CODES
                if is_rate_limit and attempt < _MAX_ATTEMPTS:
                    time.sleep(_RETRY_WAIT_SECONDS)
                    continue
                if is_rate_limit:
                    raise AIProviderError(
                        "Limite de uso gratuito do Gemini atingido. Tente novamente em instantes."
                    ) from exc
                raise AIProviderError(f"Erro no serviço de IA (Gemini), código {exc.status_code}.") from exc
        raise AssertionError("unreachable")  # loop sempre retorna ou levanta
