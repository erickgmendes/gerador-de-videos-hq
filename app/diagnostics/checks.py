"""Verificações de ambiente exibidas na tela de Diagnóstico (seção 38).

Cada checagem devolve um CheckResult com status ✓/⚠/✗ e uma mensagem
amigável — nunca um traceback cru para o usuário.
"""

from __future__ import annotations

import platform
import shutil
import socket
import sys
from dataclasses import dataclass
from enum import StrEnum

from app.config import get_settings


class CheckLevel(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class CheckResult:
    name: str
    level: CheckLevel
    detail: str


def check_operating_system() -> CheckResult:
    return CheckResult(
        name="Sistema operacional",
        level=CheckLevel.OK,
        detail=f"{platform.system()} {platform.release()} ({platform.machine()})",
    )


def check_python_version() -> CheckResult:
    version = sys.version.split()[0]
    level = CheckLevel.OK if sys.version_info >= (3, 11) else CheckLevel.WARNING
    detail = f"Python {version}" if level == CheckLevel.OK else (
        f"Python {version} — recomendado 3.11 ou superior."
    )
    return CheckResult(name="Python", level=level, detail=detail)


def check_disk_space() -> CheckResult:
    settings = get_settings()
    settings.ensure_directories()
    usage = shutil.disk_usage(settings.projects_dir)
    free_gb = usage.free / (1024**3)
    level = CheckLevel.OK if free_gb >= 5 else CheckLevel.WARNING
    detail = f"{free_gb:.1f} GB livres em {settings.projects_dir}"
    return CheckResult(name="Espaço em disco", level=level, detail=detail)


def check_internet_access() -> CheckResult:
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=2).close()
        return CheckResult(name="Acesso à internet", level=CheckLevel.OK, detail="Conectado")
    except OSError:
        return CheckResult(
            name="Acesso à internet",
            level=CheckLevel.WARNING,
            detail="Sem conexão — necessária para IA, TTS online e publicação no YouTube.",
        )


def check_ffmpeg() -> CheckResult:
    path = shutil.which("ffmpeg")
    if path:
        return CheckResult(name="FFmpeg", level=CheckLevel.OK, detail=f"Encontrado em {path}")
    return CheckResult(
        name="FFmpeg",
        level=CheckLevel.WARNING,
        detail="Não encontrado no PATH — será obtido automaticamente na Fase 6 (montagem de vídeo).",
    )


def check_ai_configuration() -> CheckResult:
    settings = get_settings()
    if settings.groq_api_key:
        return CheckResult(
            name="IA (Groq — narração)",
            level=CheckLevel.OK,
            detail=f"Chave configurada, modelo {settings.groq_model}",
        )
    return CheckResult(
        name="IA (Groq — narração)",
        level=CheckLevel.WARNING,
        detail="Chave não configurada — necessária para gerar narração. Configure em Configurações.",
    )


def check_gemini_configuration() -> CheckResult:
    settings = get_settings()
    if settings.gemini_api_key:
        return CheckResult(
            name="IA (Gemini — backup)",
            level=CheckLevel.OK,
            detail=f"Chave configurada, modelo {settings.gemini_model}",
        )
    return CheckResult(
        name="IA (Gemini — backup)",
        level=CheckLevel.WARNING,
        detail="Chave não configurada — opcional, usada automaticamente se a Groq falhar. Configure em Configurações.",
    )


def check_youtube_configuration() -> CheckResult:
    settings = get_settings()
    if settings.youtube_client_secret_file and settings.youtube_client_secret_file.exists():
        return CheckResult(name="YouTube", level=CheckLevel.OK, detail="Credenciais configuradas")
    return CheckResult(
        name="YouTube",
        level=CheckLevel.WARNING,
        detail="Credenciais não configuradas — necessárias a partir da Fase 8.",
    )


def run_all_checks() -> list[CheckResult]:
    return [
        check_operating_system(),
        check_python_version(),
        check_disk_space(),
        check_internet_access(),
        check_ffmpeg(),
        check_ai_configuration(),
        check_gemini_configuration(),
        check_youtube_configuration(),
    ]
