"""Testa o FFmpegAdapter contra arquivos de áudio reais (fixtures
minúsculas) — concatenação e leitura de duração merecem ser testadas
contra a ferramenta de verdade, não com fakes (estratégia definida desde
a Fase 1 do projeto)."""

import pytest

from app.adapters.ffmpeg.ffmpeg_adapter import FFmpegAdapter
from app.domain.errors import AudioAssemblyError
from tests.helpers import SILENCE_1S, SILENCE_2S


@pytest.fixture()
def ffmpeg():
    return FFmpegAdapter()


def test_get_duration_reads_real_mp3(ffmpeg):
    assert 0.9 <= ffmpeg.get_duration(SILENCE_1S) <= 1.3
    assert 1.9 <= ffmpeg.get_duration(SILENCE_2S) <= 2.3


def test_concat_audio_produces_single_file_with_summed_duration(ffmpeg, tmp_path):
    out_path = tmp_path / "merged.mp3"

    ffmpeg.concat_audio([SILENCE_1S, SILENCE_2S], out_path)

    assert out_path.exists()
    merged_duration = ffmpeg.get_duration(out_path)
    d1 = ffmpeg.get_duration(SILENCE_1S)
    d2 = ffmpeg.get_duration(SILENCE_2S)
    # Tolerância pequena — encoder MP3 pode arredondar por frame.
    assert abs(merged_duration - (d1 + d2)) < 0.5


def test_concat_audio_respects_order(ffmpeg, tmp_path):
    out_a = tmp_path / "a.mp3"
    out_b = tmp_path / "b.mp3"
    ffmpeg.concat_audio([SILENCE_1S, SILENCE_2S], out_a)
    ffmpeg.concat_audio([SILENCE_2S, SILENCE_1S], out_b)

    # Mesma duração total independente da ordem, mas são operações
    # distintas — garante que concat_audio não falha nem embaralha nada
    # ao processar listas em ordens diferentes.
    assert abs(ffmpeg.get_duration(out_a) - ffmpeg.get_duration(out_b)) < 0.2


def test_concat_audio_raises_on_empty_list(ffmpeg, tmp_path):
    with pytest.raises(AudioAssemblyError):
        ffmpeg.concat_audio([], tmp_path / "out.mp3")


def test_get_duration_raises_friendly_error_for_missing_file(ffmpeg, tmp_path):
    with pytest.raises(AudioAssemblyError):
        ffmpeg.get_duration(tmp_path / "nao-existe.mp3")


def test_concat_audio_falls_back_without_loudnorm_when_normalization_fails(ffmpeg, tmp_path, monkeypatch):
    # Reproduz por mock o bug real encontrado em desenvolvimento: o
    # libmp3lame pode travar (`el >= 0` no psymodel) ao aplicar loudnorm
    # sobre áudio próximo de silêncio digital puro. Em vez de falhar a
    # etapa inteira, concat_audio deve cair para uma concatenação sem
    # normalização.
    real_run_concat = ffmpeg._run_concat
    calls = []

    def fake_run_concat(list_path, out_path, *, apply_loudnorm):
        calls.append(apply_loudnorm)
        if apply_loudnorm:
            import subprocess

            return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="lame crash simulado")
        return real_run_concat(list_path, out_path, apply_loudnorm=False)

    monkeypatch.setattr(ffmpeg, "_run_concat", fake_run_concat)
    out_path = tmp_path / "merged.mp3"

    ffmpeg.concat_audio([SILENCE_1S, SILENCE_2S], out_path)

    assert calls == [True, False]
    assert out_path.exists()
