"""Porta para o mecanismo de texto-para-fala (Fase 3). Implementação padrão
planejada: edge-tts (gratuito, multiplataforma); adapter offline (Coqui TTS)
como alternativa plugável."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class AudioMeta:
    duration_seconds: float
    size_bytes: int
    format: str


class TextToSpeechAdapter(Protocol):
    def synthesize(self, text: str, *, voice: str, rate: str, out_path: Path) -> AudioMeta: ...
