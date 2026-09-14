"""Estado macro do pipeline de um projeto e status de etapas/jobs individuais.

Duas dimensões deliberadamente separadas (ver ARCHITECTURE.md):
- ProjectState: estágio linear do pipeline, mostrado no dashboard.
- StepStatus: status pontual de um job/artefato, onde erros ficam
  localizados sem invalidar artefatos já concluídos de outras etapas.
"""

from __future__ import annotations

from enum import StrEnum


class ProjectState(StrEnum):
    CREATED = "created"
    NARRATION_GENERATING = "narration_generating"
    NARRATION_READY = "narration_ready"
    AUDIO_GENERATING = "audio_generating"
    AUDIO_READY = "audio_ready"
    IMAGE_PROMPTS_GENERATING = "image_prompts_generating"
    IMAGE_PROMPTS_READY = "image_prompts_ready"
    WAITING_IMAGES = "waiting_images"
    IMAGES_READY = "images_ready"
    VIDEO_PROMPTS_READY = "video_prompts_ready"
    WAITING_VIDEOS = "waiting_videos"
    VIDEOS_READY = "videos_ready"
    ASSEMBLING = "assembling"
    ASSEMBLED = "assembled"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"


# Ordem canônica do pipeline, usada para calcular o percentual de progresso
# exibido no dashboard.
PROJECT_STATE_ORDER: list[ProjectState] = list(ProjectState)


def progress_percent(state: ProjectState) -> int:
    """Percentual aproximado de conclusão do projeto com base no estágio atual."""
    index = PROJECT_STATE_ORDER.index(state)
    return round(index / (len(PROJECT_STATE_ORDER) - 1) * 100)


class StepStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class StepKey(StrEnum):
    """Etapas exibidas nos indicadores ✓/◉/○/⚠ do dashboard e do detalhe do projeto."""

    DADOS = "dados"
    NARRACAO = "narracao"
    AUDIO = "audio"
    PROMPTS_IMAGEM = "prompts_imagem"
    IMAGENS = "imagens"
    PROMPTS_VIDEO = "prompts_video"
    VIDEOS = "videos"
    MONTAGEM = "montagem"
    REVISAO = "revisao"
    YOUTUBE = "youtube"


# Para cada etapa exibida na UI: quais estados macro contam como "em
# andamento" (◉) e qual estado marca a etapa como concluída (✓). Índices
# fora dessas listas e anteriores ao "ready" contam como pendentes (○).
_STEP_DEFINITIONS: dict[StepKey, tuple[list[ProjectState], ProjectState]] = {
    StepKey.DADOS: ([], ProjectState.CREATED),
    StepKey.NARRACAO: ([ProjectState.NARRATION_GENERATING], ProjectState.NARRATION_READY),
    StepKey.AUDIO: ([ProjectState.AUDIO_GENERATING], ProjectState.AUDIO_READY),
    StepKey.PROMPTS_IMAGEM: ([ProjectState.IMAGE_PROMPTS_GENERATING], ProjectState.IMAGE_PROMPTS_READY),
    StepKey.IMAGENS: ([ProjectState.WAITING_IMAGES], ProjectState.IMAGES_READY),
    StepKey.PROMPTS_VIDEO: ([], ProjectState.VIDEO_PROMPTS_READY),
    StepKey.VIDEOS: ([ProjectState.WAITING_VIDEOS], ProjectState.VIDEOS_READY),
    StepKey.MONTAGEM: ([ProjectState.ASSEMBLING], ProjectState.ASSEMBLED),
    StepKey.REVISAO: ([ProjectState.REVIEWING], ProjectState.APPROVED),
    StepKey.YOUTUBE: ([], ProjectState.PUBLISHED),
}


def step_statuses(current_state: ProjectState) -> dict[StepKey, StepStatus]:
    """Deriva o status (✓ concluído / ◉ em andamento / ○ pendente) de cada etapa da UI."""
    current_index = PROJECT_STATE_ORDER.index(current_state)
    result: dict[StepKey, StepStatus] = {}
    for key, (running_states, ready_state) in _STEP_DEFINITIONS.items():
        ready_index = PROJECT_STATE_ORDER.index(ready_state)
        if current_index >= ready_index:
            result[key] = StepStatus.SUCCESS
        elif current_state in running_states:
            result[key] = StepStatus.RUNNING
        else:
            result[key] = StepStatus.PENDING
    return result
