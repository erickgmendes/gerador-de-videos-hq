"""Configuração da aplicação.

Segredos (API keys, client secrets) só via variáveis de ambiente/.env —
nunca hardcoded e nunca gravados em log (ver app/diagnostics). Preferências
não sensíveis (caminhos, formato de mídia etc.) também começam aqui.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz do repositório (dois níveis acima deste arquivo: app/config.py -> app/ -> raiz).
BASE_DIR = Path(__file__).resolve().parent.parent


def get_env_file_path() -> Path:
    """Caminho do .env local. Indireção deliberada (função, não constante)
    — tanto get_settings() quanto app/services/settings_service.py chamam
    esta função (via referência ao módulo, não import direto do nome) para
    que os testes consigam substituí-la e nunca leiam/escrevam o .env real
    do projeto."""
    return BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    data_dir: Path = BASE_DIR / "data"
    projects_dir: Path = BASE_DIR / "projects"
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'app.db').as_posix()}"

    groq_api_key: str | None = None
    # groq/compound (escolhido originalmente pelo teto de 70K tokens/min no
    # tier gratuito, bem maior que os 8K dos modelos gpt-oss/qwen) foi
    # descontinuado pela Groq em 21/09/2026 — chamadas a ele agora
    # devolvem 404. TODOS os modelos restantes do tier gratuito
    # compartilham o teto de 8K TPM, insuficiente até para uma única
    # narração (ver ARCHITECTURE.md). Por isso o backup via GEMINI_API_KEY
    # (`app/adapters/ai/fallback_adapter.py`, tier gratuito do Gemini tem
    # ~250K TPM) deixou de ser opcional na prática — sem ele, a Groq
    # sozinha esbarra no limite com frequência.
    groq_model: str = "openai/gpt-oss-120b"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # IA backup (Fase 2+) — usada automaticamente se a Groq falhar (chave
    # ausente, limite de uso etc.), via app/adapters/ai/fallback_adapter.py.
    # Gratuito, sem cartão, compatível com OpenAI (mesmo padrão da Groq).
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # TTS (Fase 3) — edge-tts, gratuito, sem API key, precisa de internet.
    tts_voice: str = "pt-BR-AntonioNeural"
    tts_rate: str = "-4%"

    # Imagens (Fase 4) — quantos segundos de vídeo cada imagem cobre na
    # ferramenta de animação externa; usado para calcular quantos painéis
    # cada cena precisa (duração da cena ÷ este valor, arredondado para
    # cima). Depende da ferramenta real usada na Fase 5 — ajustável.
    video_segment_seconds: float = 5.0

    # Teto de imagens do projeto inteiro — pedido do usuário para editar o
    # vídeo manualmente no Kdenlive num primeiro momento, sem depender de
    # animação por IA para cada cena. Quando a soma dos painéis "ideais"
    # (por duração) passa deste teto, a alocação é redistribuída
    # proporcionalmente à duração de cada cena (cenas maiores continuam
    # recebendo mais painéis que as curtas, só numa escala menor).
    max_image_prompts: int = 50

    youtube_client_secret_file: Path | None = None

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        (self.data_dir / "logs").mkdir(parents=True, exist_ok=True)
        self.projects_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=get_env_file_path())
