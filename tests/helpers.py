"""Duplas de teste compartilhadas entre tests/unit e tests/integration."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from mutagen.mp3 import MP3

from app.adapters.tts.base import AudioMeta
from app.domain.errors import AIProviderError, TTSError

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "audio"
SILENCE_1S = FIXTURES_DIR / "silence_1s.mp3"
SILENCE_2S = FIXTURES_DIR / "silence_2s.mp3"

NARRATION_TEXT = """\
CENA 1 — O chamado à beira-mar
Local:
Às margens do mar da Galileia
Momento:
Início da manhã
Narração:
Jesus caminhava pela praia enquanto pescadores recolhiam suas redes.

CENA 2 — A resposta imediata
Local:
Ainda às margens do mar
Momento:
Pouco depois
Narração:
Simão e André largaram as redes e o seguiram, sem hesitar.
"""

ENRICHMENT_JSON = json.dumps(
    [
        {
            "order": 1,
            "characters": ["Jesus"],
            "action": "Caminha pela praia",
            "emotion": "expectativa",
            "visual_importance": "medium",
        },
        {
            "order": 2,
            "characters": ["Simão", "André", "Jesus"],
            "action": "Deixam as redes e o seguem",
            "emotion": "decisão",
            "visual_importance": "high",
        },
    ]
)


class FakeAIAdapter:
    """Satisfaz o Protocol AIProviderAdapter sem chamar nenhuma API de verdade."""

    def __init__(self, responses: list[str]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        self.calls.append({"prompt": prompt, "system": system, "max_tokens": max_tokens, "json_mode": json_mode})
        if not self._responses:
            raise AssertionError("FakeAIAdapter esgotou as respostas configuradas")
        return self._responses.pop(0)


class FailingAIAdapter:
    def complete(
        self, prompt: str, *, system: str | None = None, max_tokens: int = 4096, json_mode: bool = False
    ) -> str:
        raise AIProviderError("Chave inválida (simulado)")


class FakeTTSAdapter:
    """Satisfaz o Protocol TextToSpeechAdapter copiando um fixture de áudio
    minúsculo real (não gera silêncio nem chama nenhum serviço de rede) —
    permite testar o restante do pipeline (FFmpegAdapter incluso) com
    arquivos de áudio de verdade, só sem depender da internet."""

    def __init__(self, source: Path = SILENCE_1S):
        self.source = source
        self.calls: list[str] = []

    def synthesize(self, text: str, *, voice: str, rate: str, out_path: Path) -> AudioMeta:
        self.calls.append(text)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self.source, out_path)
        return AudioMeta(
            duration_seconds=round(MP3(out_path).info.length, 2),
            size_bytes=out_path.stat().st_size,
            format="mp3",
        )


class FailingTTSAdapter:
    def synthesize(self, text: str, *, voice: str, rate: str, out_path: Path) -> AudioMeta:
        raise TTSError("Sem conexão com a internet (simulado)")


def create_test_project(app_client, name: str = "Evangelho da Semana") -> str:
    response = app_client.post(
        "/projects/new",
        data={
            "name": name,
            "bible_reference": "Mc 1:16-20",
            "passage_text": "Texto bíblico de teste.",
            "biblia_visual_text": "",
        },
        follow_redirects=False,
    )
    return response.headers["location"].rsplit("/", 1)[-1]


def generate_test_narration(app_client, monkeypatch, project_id: str) -> None:
    """Gera a narração (via FakeAIAdapter) de um projeto já criado, para
    testes que precisam de cenas prontas antes de exercitar outra fase
    (ex.: áudio)."""
    import app.web.routes.narration as narration_routes

    fake_ai = FakeAIAdapter([NARRATION_TEXT, ENRICHMENT_JSON])
    monkeypatch.setattr(narration_routes, "get_ai_adapter", lambda: fake_ai)
    app_client.post(f"/projects/{project_id}/narracao/gerar", follow_redirects=False)


def generate_test_audio(app_client, monkeypatch, project_id: str) -> None:
    """Gera o áudio (via FakeTTSAdapter) de um projeto que já tem cenas —
    para testes que precisam de `Scene.actual_duration` preenchido (ex.:
    prompts de imagem)."""
    import app.web.routes.audio as audio_routes

    monkeypatch.setattr(audio_routes, "get_tts_adapter", lambda: FakeTTSAdapter())
    app_client.post(f"/projects/{project_id}/audio/gerar", follow_redirects=False)


def get_test_db_session(app_client):
    """Sessão de banco isolada de um teste, a partir do `app_client` — para
    inspecionar/ajustar dados diretamente quando a UI não expõe algo (ex.:
    pegar o id de uma cena). Lembre de fechar (`.close()`) depois de usar."""
    from app.db import get_db

    return next(app_client.app.dependency_overrides[get_db]())
