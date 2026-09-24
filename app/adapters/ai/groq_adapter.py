"""Implementação de AIProviderAdapter usando a API da Groq (GroqCloud).

A API da Groq é compatível com o SDK OpenAI (base_url próprio) — não existe
SDK dedicado da Groq necessário. Ver https://console.groq.com/docs/openai.

Cada chamada tenta só UMA vez — nunca fica esperando e tentando de novo o
mesmo provedor internamente (isso já foi removido daqui, ver histórico:
até 3 tentativas com 25s de espera cada podiam gastar ~50s só na Groq
antes até de tentar o backup). Quem decide se/quando tentar de novo é
`app/adapters/ai/fallback_adapter.py`, tentando o próximo provedor da
cadeia imediatamente em vez de insistir no mesmo — relatado pelo usuário
com dados reais: com Groq no limite de uso E Gemini sobrecarregado ao
mesmo tempo, esperar tanto tempo dentro de cada adapter antes de sequer
tentar o outro provedor só atrasava chegar numa resposta que funcionasse.
"""

from __future__ import annotations

import openai

from app.domain.errors import AIProviderError

# Códigos HTTP transitórios da Groq — usados só para escolher a mensagem
# de erro amigável certa (não para decidir se tenta de novo, ver acima).
# 429 é o padrão OpenAI-compatível de "estourei o limite de uso"; 413 é o
# que a Groq de fato devolve na prática para "tokens por minuto excedido"
# e "requisição grande demais"; 503 é "servidor sobrecarregado no
# momento" (relatado pelo usuário com dados reais — nada a ver com limite
# de uso).
_RATE_LIMIT_STATUS_CODES = {413, 429}


class GroqAdapter:
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.groq.com/openai/v1") -> None:
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
            raise AIProviderError("A IA não retornou conteúdo de texto.")
        return text

    def _create(self, messages: list[dict[str, str]], max_tokens: int, json_mode: bool):
        # Modelos de "reasoning" (padrão desde a saída do groq/compound, ver
        # app/config.py) intercalam texto de raciocínio ("<think>...</think>")
        # no próprio campo de conteúdo por padrão, o que quebra json.loads
        # mesmo quando a instrução do prompt pede JSON puro. response_format
        # força o modo JSON da API; reasoning_format "hidden" (extensão da
        # Groq, só tem efeito em modelos de reasoning — ignorado nos demais)
        # impede esse raciocínio de vazar para o conteúdo da resposta.
        extra: dict = {}
        if json_mode:
            extra["response_format"] = {"type": "json_object"}
            extra["extra_body"] = {"reasoning_format": "hidden"}
        try:
            return self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                messages=messages,
                **extra,
            )
        except openai.AuthenticationError as exc:
            raise AIProviderError("Chave de API da Groq inválida ou não configurada.") from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError("Não foi possível conectar à API da Groq. Verifique sua conexão.") from exc
        except openai.APIStatusError as exc:
            if exc.status_code == 503:
                raise AIProviderError(
                    "Servidor da Groq temporariamente sobrecarregado. Tente novamente em instantes."
                ) from exc
            if exc.status_code in _RATE_LIMIT_STATUS_CODES:
                raise AIProviderError(
                    "Limite de uso gratuito da Groq atingido (tokens por minuto). "
                    "Tente novamente em cerca de um minuto."
                ) from exc
            raise AIProviderError(f"Erro no serviço de IA (Groq), código {exc.status_code}.") from exc
