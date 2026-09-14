"""Porta para publicação no YouTube (Fase 8), via API oficial do YouTube
(OAuth 2.0 desktop flow)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class YouTubeAdapter(Protocol):
    def upload(self, *, video_path: Path, title: str, description: str, tags: list[str], visibility: str) -> str: ...
