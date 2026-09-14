from __future__ import annotations

from app.adapters.tts.base import TextToSpeechAdapter
from app.adapters.tts.edge_tts_adapter import EdgeTTSAdapter


def get_tts_adapter() -> TextToSpeechAdapter:
    return EdgeTTSAdapter()
