"""Gerencia os segredos (API keys, arquivos de credenciais) editáveis pela
tela de Configurações.

Segredos são sempre persistidos no arquivo .env local — nunca no banco de
dados nem em log — conforme a seção 42 da especificação. Este é o único
módulo autorizado a escrever nesse arquivo. Cada nova integração (YouTube
etc.) só precisa adicionar uma entrada em `list_secret_fields` e uma rota
de formulário — o padrão de leitura/gravação já é genérico.
"""

from __future__ import annotations

from dataclasses import dataclass

from app import config as app_config
from app.config import BASE_DIR, get_settings
from app.domain.errors import ValidationError

# Registro de todos os segredos configuráveis pela UI. `key` é o nome exato
# da variável de ambiente lida por app/config.py. `how_to_get` é o
# passo a passo mostrado na tela de Configurações — cada integração nova
# (YouTube etc.) só precisa de uma entrada aqui com seus próprios passos.
_SECRET_FIELD_DEFS: list[dict] = [
    {
        "key": "GROQ_API_KEY",
        "label": "Chave da API da Groq",
        "category": "IA",
        "help_text": "Necessária para gerar narração. Gratuita, sem cartão de crédito.",
        "is_configured": lambda settings: bool(settings.groq_api_key),
        "how_to_get": [
            'Acesse <a href="https://console.groq.com" target="_blank" rel="noopener">console.groq.com</a> e crie uma conta gratuita (e-mail ou Google) — não pede cartão de crédito.',
            'No menu lateral, vá em <a href="https://console.groq.com/keys" target="_blank" rel="noopener">API Keys</a>.',
            'Clique em "Create API Key", dê um nome (ex.: "producao-biblica") e confirme.',
            'Copie a chave gerada (começa com "gsk_") — ela só é exibida uma vez nesse momento.',
            "Cole a chave no campo abaixo e clique em Salvar.",
        ],
        "extra_note": (
            "O plano gratuito tem limites de requisições/tokens por minuto — de sobra para o "
            "uso deste projeto (algumas gerações de narração por dia)."
        ),
    },
    {
        "key": "GEMINI_API_KEY",
        "label": "Chave da API do Gemini (backup)",
        "category": "IA",
        "help_text": (
            "Opcional. Se configurada, a aplicação usa automaticamente o Gemini quando a Groq "
            "falhar (chave ausente, limite de uso atingido etc.) — ou como única IA, se preferir "
            "usar só o Gemini. Gratuito, sem cartão de crédito."
        ),
        "is_configured": lambda settings: bool(settings.gemini_api_key),
        "how_to_get": [
            'Acesse <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener">aistudio.google.com/apikey</a> e entre com sua conta Google — não pede cartão de crédito.',
            'Clique em "Create API key" (ou "Get API key" → "Create API key").',
            "Escolha um projeto do Google Cloud existente ou deixe criar um novo automaticamente.",
            "Copie a chave gerada.",
            "Cole a chave no campo abaixo e clique em Salvar.",
        ],
        "extra_note": (
            "O tier gratuito do Gemini não tem prazo de expiração, mas tem limites diários — "
            "verifique em aistudio.google.com/apikey se ficar sem cota."
        ),
    },
]

KNOWN_SECRET_KEYS = {field["key"] for field in _SECRET_FIELD_DEFS}


@dataclass(frozen=True)
class SecretField:
    key: str
    label: str
    category: str
    help_text: str
    configured: bool
    how_to_get: list[str]
    extra_note: str | None


def list_secret_fields() -> list[SecretField]:
    settings = get_settings()
    return [
        SecretField(
            key=field["key"],
            label=field["label"],
            category=field["category"],
            help_text=field["help_text"],
            configured=field["is_configured"](settings),
            how_to_get=field.get("how_to_get", []),
            extra_note=field.get("extra_note"),
        )
        for field in _SECRET_FIELD_DEFS
    ]


def _read_env_lines() -> list[str]:
    # Chamado via módulo (não `from app.config import get_env_file_path`)
    # para que um monkeypatch em app.config.get_env_file_path — o mesmo que
    # get_settings() respeita — também valha aqui. Ver app/config.py.
    env_path = app_config.get_env_file_path()
    if env_path.exists():
        return env_path.read_text(encoding="utf-8").splitlines()

    example_path = BASE_DIR / ".env.example"
    if example_path.exists():
        return example_path.read_text(encoding="utf-8").splitlines()

    return []


def set_secret(key: str, value: str) -> None:
    """Grava (ou atualiza) uma variável no .env local e recarrega as
    configurações em memória — a mudança vale imediatamente, sem reiniciar
    a aplicação. Um valor em branco é ignorado (não apaga a chave já
    salva) — quem quiser remover uma chave deve editar o .env manualmente."""
    if key not in KNOWN_SECRET_KEYS:
        raise ValidationError(f"'{key}' não é uma chave configurável reconhecida.")

    value = value.strip()
    if not value:
        return

    lines = _read_env_lines()
    prefix = f"{key}="
    updated = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")

    env_path = app_config.get_env_file_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    get_settings.cache_clear()
