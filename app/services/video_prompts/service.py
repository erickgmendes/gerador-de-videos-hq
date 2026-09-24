"""Orquestra a geração dos prompts de vídeo (Fase 5): para cada painel que
já tem imagem enviada, escreve o prompt fixo de animação (sem IA — ver
app/services/video_prompts/prompts.py) e recalcula o estado do projeto.

Diferente das fases anteriores, roda de forma síncrona dentro da própria
requisição HTTP — não é um job em background. Sem chamada de IA, escrever
o prompt de até algumas dezenas de painéis é uma operação de
milissegundos; criar toda a infraestrutura de job/spinner/polling só para
isso seria complexidade sem benefício real (ver
app/services/image_prompts/service.py para o padrão usado quando existe,
de fato, uma chamada lenta e sujeita a rate limit)."""

from __future__ import annotations

from app.config import get_settings
from app.domain.errors import VideoPromptError
from app.domain.states import ProjectState
from app.models.orm import ImagePrompt
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.services.video_prompts.prompts import build_video_prompt_text
from app.storage import project_storage


def recompute_project_state(image_prompts: list[ImagePrompt]) -> str:
    """Deriva o estado macro a partir dos dados reais dos painéis — mesma
    filosofia de app/services/image_prompts/service.py.recompute_project_state
    (nunca um valor fixo, sempre derivado do que já está salvo)."""
    if not image_prompts or not all(p.image_path for p in image_prompts):
        # A Fase 4 (imagens) ainda não terminou — a Fase 5 não deveria ter
        # avançado o estado; devolve um estado plausível dela. Na prática
        # não deveria ser alcançado por rota nenhuma (ambas as ações desta
        # fase já checam isso antes), mas fica como salvaguarda.
        return ProjectState.WAITING_IMAGES.value
    if not all(p.video_prompt_text for p in image_prompts):
        return ProjectState.IMAGES_READY.value
    if all(p.video_path for p in image_prompts):
        return ProjectState.VIDEOS_READY.value
    if any(p.video_path for p in image_prompts):
        return ProjectState.WAITING_VIDEOS.value
    return ProjectState.VIDEO_PROMPTS_READY.value


def _require_images_ready(image_prompts: list[ImagePrompt]) -> None:
    if not image_prompts:
        raise VideoPromptError(
            "Este projeto ainda não tem painéis de imagem — gere e envie as imagens primeiro (aba Imagens)."
        )
    if not all(p.image_path for p in image_prompts):
        raise VideoPromptError(
            "Nem todos os painéis têm imagem enviada ainda — termine o upload na aba Imagens primeiro."
        )


def _write_export_file(project_id: str, image_prompts: list[ImagePrompt]) -> None:
    # Mesmo formato da Fase 4: só os textos, um por bloco, linha em branco
    # só ENTRE blocos — a ferramenta externa usa isso pra separar um
    # prompt do outro.
    project_storage.video_prompts_export_path(project_id).write_text(
        "\n\n".join(p.video_prompt_text for p in image_prompts), encoding="utf-8"
    )


def generate_video_prompts(db, project_id: str) -> int:
    """Preenche `video_prompt_text` de todo painel que ainda não tem um —
    idempotente, nunca sobrescreve um painel já preenchido (diferente de
    `regenerate_all_video_prompts`). Devolve quantos painéis foram
    preenchidos nesta chamada."""
    repo = ImagePromptRepository(db)
    all_prompts = repo.list_for_project(project_id)
    _require_images_ready(all_prompts)

    settings = get_settings()
    filled = 0
    for panel in all_prompts:
        if panel.video_prompt_text:
            continue
        panel.video_prompt_text = build_video_prompt_text(settings.video_segment_seconds)
        filled += 1

    _write_export_file(project_id, all_prompts)
    db.commit()
    return filled


def regenerate_all_video_prompts(db, project_id: str) -> int:
    """Zera `video_prompt_text`/`video_path` de TODO painel e gera de
    novo — diferente de `generate_video_prompts`, que só preenche o que
    falta. Útil se o texto fixo do prompt for ajustado depois (nova versão
    do código) e o usuário quiser reaproveitar as mesmas imagens já
    prontas; como o vídeo antigo foi gerado a partir do prompt antigo, o
    upload feito também é limpo — mesma lógica de "gerar-tudo" da Fase 4."""
    repo = ImagePromptRepository(db)
    all_prompts = repo.list_for_project(project_id)
    _require_images_ready(all_prompts)

    settings = get_settings()
    for panel in all_prompts:
        panel.video_prompt_text = build_video_prompt_text(settings.video_segment_seconds)
        panel.video_path = None
        panel.video_uploaded_at = None

    _write_export_file(project_id, all_prompts)
    db.commit()
    return len(all_prompts)
