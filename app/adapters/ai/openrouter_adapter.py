"""Implementação de AIProviderAdapter usando a API da OpenRouter — também
compatível com o SDK OpenAI (base_url próprio). Ver
https://openrouter.ai/docs/quickstart.

Terceiro nível do fallback (`app/adapters/ai/fallback_adapter.py`), só
"por segurança": entra em ação apenas se Groq E Gemini falharem ao mesmo
tempo. O tier gratuito da OpenRouter é baixo demais (50 requisições/dia
no total, não por modelo, sem nunca ter comprado crédito — conferido ao
vivo em 2026) para ser um backup de uso normal, mas serve como último
recurso de emergência. Modelo padrão `openrouter/free`: não é um modelo
específico, é o roteador da própria OpenRouter que escolhe entre os
modelos gratuitos disponíveis no momento e já filtra por suporte a
"structured outputs" — evita depender de um único modelo gratuito fixo,
que a OpenRouter roda/remove da lista sem aviso.

Estrutura propositalmente igual aos outros dois adapters, mantida em
arquivo próprio pelo mesmo motivo de isolamento já documentado em
gemini_adapter.py.
"""

from __future__ import annotations

import openai

from app.domain.errors import AIProviderError

# 429 é limite de uso; usado só para escolher a mensagem de erro amigável
# certa — não para decidir se tenta de novo aqui dentro (isso é
# responsabilidade de app/adapters/ai/fallback_adapter.py, tentando o
# próximo provedor da cadeia em vez de insistir no mesmo).
_RATE_LIMIT_STATUS_CODES = {429}


class OpenRouterAdapter:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._create(messages, max_tokens, json_mode)

        choice = response.choices[0] if response.choices else None
        text = choice.message.content if choice and choice.message else None
        if not text or not text.strip():
            raise AIProviderError("A IA (OpenRouter) não retornou conteúdo de texto.")
        return text

    def _create(self, messages: list[dict[str, str]], max_tokens: int, json_mode: bool):
        extra: dict = {}
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
        try:
            return self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=messages,
                **extra,
            )
        except openai.AuthenticationError as exc:
            raise AIProviderError("Chave de API da OpenRouter inválida ou não configurada.") from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError("Não foi possível conectar à API da OpenRouter. Verifique sua conexão.") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 503:
                raise AIProviderError(
                    "Nenhum modelo gratuito da OpenRouter disponível no momento. Tente novamente em instantes."
                ) from exc
            if exc.status_code in _RATE_LIMIT_STATUS_CODES:
                raise AIProviderError(
                    "Limite de uso gratuito da OpenRouter atingido. Tente novamente em instantes."
                ) from exc
            raise AIProviderError(f"Erro no serviço de IA (OpenRouter), código {exc.status_code}.") from exc
