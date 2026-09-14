"""Rótulos e ícones (✓/◉/○) usados só pelos templates — mapeiam os enums de
domínio para texto amigável, sem misturar apresentação com regra de negócio."""

from __future__ import annotations

from app.diagnostics.checks import CheckLevel
from app.domain.states import StepKey, StepStatus

STEP_LABELS: dict[StepKey, str] = {
    StepKey.DADOS: "Dados",
    StepKey.NARRACAO: "Narração",
    StepKey.AUDIO: "Áudio",
    StepKey.PROMPTS_IMAGEM: "Prompts de imagem",
    StepKey.IMAGENS: "Imagens",
    StepKey.PROMPTS_VIDEO: "Prompts de vídeo",
    StepKey.VIDEOS: "Vídeos",
    StepKey.MONTAGEM: "Montagem",
    StepKey.REVISAO: "Revisão",
    StepKey.YOUTUBE: "YouTube",
}

STEP_ORDER: list[StepKey] = list(StepKey)

STEP_ICONS: dict[StepStatus, str] = {
    StepStatus.SUCCESS: "✓",  # ✓
    StepStatus.RUNNING: "◉",  # ◉
    StepStatus.PENDING: "○",  # ○
    StepStatus.FAILED: "⚠",  # ⚠
}

STEP_CSS_CLASS: dict[StepStatus, str] = {
    StepStatus.SUCCESS: "step-success",
    StepStatus.RUNNING: "step-running",
    StepStatus.PENDING: "step-pending",
    StepStatus.FAILED: "step-pending",
}

CHECK_ICONS: dict[CheckLevel, str] = {
    CheckLevel.OK: "✓",
    CheckLevel.WARNING: "⚠",
    CheckLevel.ERROR: "✗",
}

CHECK_BADGE_CLASS: dict[CheckLevel, str] = {
    CheckLevel.OK: "badge-ok",
    CheckLevel.WARNING: "badge-warning",
    CheckLevel.ERROR: "badge-error",
}

# Abas da tela de detalhe do projeto e a URL de cada uma quando já
# implementada. Abas sem URL aparecem desabilitadas — esqueleto de
# navegação para as fases ainda não construídas.
PROJECT_TABS: list[tuple[str, str, str | None]] = [
    ("info", "Informações", "/projects/{id}"),
    ("narracao", "Narração", "/projects/{id}/narracao"),
    ("audio", "Áudio", "/projects/{id}/audio"),
    ("imagens", "Imagens", "/projects/{id}/imagens"),
    ("videos", "Vídeos", None),
    ("montagem", "Montagem", None),
    ("revisao", "Revisão", None),
    ("youtube", "YouTube", None),
]
