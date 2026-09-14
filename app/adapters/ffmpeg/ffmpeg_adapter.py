"""Wrapper fino sobre o binário FFmpeg (obtido via imageio-ffmpeg, portátil
e multiplataforma — sem exigir instalação manual). Usado pela Fase 3 para
concatenar os áudios por cena num único arquivo; cresce na Fase 6 com um
método de montagem de vídeo.

Duração é lida com `mutagen` (metadados do MP3), não via FFmpeg/ffprobe —
`imageio-ffmpeg` só empacota o `ffmpeg`, não o `ffprobe`.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import imageio_ffmpeg
from mutagen.mp3 import MP3

from app.domain.errors import AudioAssemblyError

# Parâmetros de loudnorm (EBU R128) padrão para voz narrada: -16 LUFS é o
# alvo comum para conteúdo falado (podcasts/audiobooks), bem abaixo do
# clipping e consistente entre os trechos sintetizados separadamente —
# resolve tanto pequenas variações de volume entre cenas quanto qualquer
# diferença residual de nível na emenda.
_LOUDNORM_FILTER = "loudnorm=I=-16:TP=-1.5:LRA=11"


class FFmpegAdapter:
    def __init__(self) -> None:
        self._ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    def get_duration(self, path: Path) -> float:
        try:
            return round(MP3(path).info.length, 2)
        except Exception as exc:
            raise AudioAssemblyError(f"Não foi possível ler a duração de {path.name}.") from exc

    def concat_audio(self, paths: list[Path], out_path: Path) -> None:
        """Concatena os áudios na ordem dada em um único arquivo, com
        normalização de volume (loudnorm) para não haver salto de volume
        nem corte perceptível na emenda entre cenas.

        Se a normalização falhar — o encoder libmp3lame tem um bug
        conhecido que trava com loudnorm sobre áudio de silêncio digital
        puro (observado em teste; improvável com fala real do TTS, mas
        não impossível numa cena muito curta/silenciosa) — cai para uma
        concatenação sem normalização em vez de falhar a etapa inteira.
        """
        if not paths:
            raise AudioAssemblyError("Nenhum áudio de cena para concatenar.")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        list_path = self._write_concat_list(paths)
        try:
            result = self._run_concat(list_path, out_path, apply_loudnorm=True)
            if result.returncode != 0 or not out_path.exists():
                result = self._run_concat(list_path, out_path, apply_loudnorm=False)
            if result.returncode != 0 or not out_path.exists():
                raise AudioAssemblyError(
                    "Falha ao concatenar os áudios das cenas com o FFmpeg. "
                    f"Detalhe técnico: {result.stderr[-500:].strip()}"
                )
        finally:
            list_path.unlink(missing_ok=True)

    @staticmethod
    def _write_concat_list(paths: list[Path]) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as list_file:
            for path in paths:
                escaped = path.resolve().as_posix().replace("'", "'\\''")
                list_file.write(f"file '{escaped}'\n")
            return Path(list_file.name)

    def _run_concat(self, list_path: Path, out_path: Path, *, apply_loudnorm: bool) -> subprocess.CompletedProcess:
        args = [
            self._ffmpeg_exe,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_path),
        ]
        if apply_loudnorm:
            args += ["-af", _LOUDNORM_FILTER]
        args += ["-ar", "24000", "-ac", "1", "-b:a", "128k", str(out_path)]
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
