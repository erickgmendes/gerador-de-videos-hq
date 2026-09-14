"""Porta para montagem de vídeo (Fase 6). Implementação planejada via FFmpeg
(binário obtido através de imageio-ffmpeg, ver ARCHITECTURE.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class VideoAssemblyAdapter(Protocol):
    def assemble(self, *, narration_path: Path, scene_video_paths: list[Path], out_path: Path, config: dict) -> Path: ...
