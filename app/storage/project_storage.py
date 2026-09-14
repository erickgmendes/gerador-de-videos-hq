"""Único módulo autorizado a montar caminhos dentro de PROJECTS_DIR.

Nenhum outro módulo deve construir Path(...) apontando para dentro da
pasta de um projeto — sempre passar por aqui, para manter a árvore de
diretórios (seção 8 da especificação) consistente em todo o sistema.
"""

from __future__ import annotations

from pathlib import Path

from app.config import get_settings

SUBDIRS = (
    "input",
    "roteiro",
    "audio",
    "audio/scenes",
    "prompts",
    "images",
    "videos",
    "output",
    "metadata",
    "metadata/logs",
)


def project_root(project_id: str) -> Path:
    return get_settings().projects_dir / project_id


def create_project_tree(project_id: str) -> Path:
    root = project_root(project_id)
    for subdir in SUBDIRS:
        (root / subdir).mkdir(parents=True, exist_ok=True)
    return root


def project_exists(project_id: str) -> bool:
    return project_root(project_id).is_dir()


def input_passagem_path(project_id: str) -> Path:
    return project_root(project_id) / "input" / "passagem.md"


def input_biblia_visual_path(project_id: str) -> Path:
    return project_root(project_id) / "input" / "biblia-visual-personagens.md"


def project_json_path(project_id: str) -> Path:
    return project_root(project_id) / "metadata" / "project.json"


def scenes_json_path(project_id: str) -> Path:
    return project_root(project_id) / "roteiro" / "cenas.json"


def narracao_md_path(project_id: str) -> Path:
    return project_root(project_id) / "roteiro" / "narracao.md"


def narracao_texto_corrido_path(project_id: str) -> Path:
    """Só o texto que será narrado, corrido, sem os rótulos CENA/Local/
    Momento — para o narrador ler/gravar, e para a Fase 3 (TTS) sintetizar."""
    return project_root(project_id) / "roteiro" / "texto_narracao.txt"


def audio_scene_path(project_id: str, order: int) -> Path:
    """Artefato principal de áudio: um MP3 por cena, editável/substituível
    independentemente — mesmo padrão de imagens/vídeos por cena."""
    return project_root(project_id) / "audio" / "scenes" / f"{order:03d}.mp3"


def audio_final_path(project_id: str) -> Path:
    """Arquivo único mesclado (todas as cenas concatenadas) — o que a
    seção 14 da especificação chama de audio/narracao.mp3, usado na
    montagem final do vídeo (Fase 6)."""
    return project_root(project_id) / "audio" / "narracao.mp3"


def image_prompts_export_path(project_id: str) -> Path:
    """Exportação de todos os prompts de imagem num único .txt, no formato
    da seção 22 da especificação — nome já previsto desde a seção 8."""
    return project_root(project_id) / "prompts" / "imagens.txt"


def image_file_path(project_id: str, global_order: int, extension: str) -> Path:
    """Uma imagem por painel, numerada globalmente (001.png, 002.png...) —
    `extension` inclui o ponto (ex.: ".png"), preservando o formato
    enviado pelo usuário."""
    return project_root(project_id) / "images" / f"{global_order:03d}{extension}"
