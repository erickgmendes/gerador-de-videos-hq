"""Implementação de AIProviderAdapter usando a API do Google Gemini, via
a interface compatível com OpenAI que o Gemini expõe — dispensa um SDK
próprio. Ver https://ai.google.dev/gemini-api/docs/openai.

Backup da Groq (`groq_adapter.py`): estrutura propositalmente igual, mas
mantidos como arquivos separados em vez de uma base compartilhada — são
poucas linhas, e isolados assim cada adapter pode evoluir sozinho (ex.:
peculiaridades de erro de um provedor) sem arriscar o outro, que já está
em produção. Ver `app/adapters/ai/__init__.py` para como os dois se
combinam num fallback automático — inclusive a decisão de tentar de novo
(ver `fallback_adapter.py`), que não é responsabilidade deste arquivo.
"""

from __future__ import annotations

import openai

from app.domain.errors import AIProviderError

# 429 é limite de uso; 503 é "modelo sobrecarregado no momento" — comum no
# Gemini mesmo com cota sobrando (relatado pelo usuário com dados reais).
# Usados só para escolher a mensagem de erro amigável certa — não para
# decidir se tenta de novo aqui dentro (ver docstring do módulo).
_RATE_LIMIT_STATUS_CODES = {429}


class GeminiAdapter:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/",
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
            raise AIProviderError("A IA (Gemini) não retornou conteúdo de texto.")
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
            raise AIProviderError("Chave de API do Gemini inválida ou não configurada.") from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError("Não foi possível conectar à API do Gemini. Verifique sua conexão.") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 503:
                raise AIProviderError(
                    "Modelo do Gemini temporariamente sobrecarregado. Tente novamente em instantes."
                ) from exc
            if exc.status_code in _RATE_LIMIT_STATUS_CODES:
                raise AIProviderError(
                    "Limite de uso gratuito do Gemini atingido. Tente novamente em instantes."
                ) from exc
            raise AIProviderError(f"Erro no serviço de IA (Gemini), código {exc.status_code}.") from exc
