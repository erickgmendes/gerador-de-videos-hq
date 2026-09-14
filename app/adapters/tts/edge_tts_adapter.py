"""Implementação de TextToSpeechAdapter usando edge-tts (vozes de nuvem do
Microsoft Edge) — gratuito, sem API key, mas precisa de internet.

`edge_tts.Communicate.save()` é assíncrono; `asyncio.run()` aqui mantém a
interface síncrona para o resto do app (mesmo padrão do GroqAdapter),
seguro porque isto roda dentro de uma background task síncrona (sem event
loop já rodando na thread — ver app/services/audio/service.py).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import edge_tts
from mutagen.mp3 import MP3

from app.adapters.tts.base import AudioMeta
from app.domain.errors import TTSError


class EdgeTTSAdapter:
    def synthesize(self, text: str, *, voice: str, rate: str, out_path: Path) -> AudioMeta:
        if not text.strip():
            raise TTSError("Não há texto para sintetizar.")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            asyncio.run(self._save(text, voice, rate, out_path))
        except TTSError:
            raise
        except Exception as exc:  # rede instável, serviço indisponível etc.
            raise TTSError(
                "Não foi possível sintetizar o áudio (verifique sua conexão com a internet)."
            ) from exc

        if not out_path.exists() or out_path.stat().st_size == 0:
            raise TTSError("A síntese de voz não gerou nenhum áudio.")

        try:
            duration = MP3(out_path).info.length
        except Exception as exc:
            raise TTSError("O arquivo de áudio gerado está corrompido ou inválido.") from exc

        return AudioMeta(
            duration_seconds=round(duration, 2),
            size_bytes=out_path.stat().st_size,
            format="mp3",
        )

    @staticmethod
    async def _save(text: str, voice: str, rate: str, out_path: Path) -> None:
        communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
        await communicate.save(str(out_path))
