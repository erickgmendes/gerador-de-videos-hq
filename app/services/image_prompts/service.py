"""Orquestra a geração de prompts de imagem: calcula quantos painéis cada
cena precisa (duração real ÷ segundos por clipe de vídeo), gera as
descrições via IA (uma chamada por cena, cache de personagens entre
cenas) e monta o prompt final injetando o bloco fixo de estilo/formato.

Roda em background — abre sua própria sessão via `session_factory`, igual
ao padrão já usado em narration/service.py e audio/service.py.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.adapters.ai.base import AIProviderAdapter
from app.config import Settings, get_settings
from app.domain.errors import AIProviderError, DomainError, ImagePromptError
from app.domain.states import ProjectState
from app.models.orm import Character, ImagePrompt, Job, Location, Project, Scene
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.repositories.scene_repository import SceneRepository
from app.services.image_prompts.prompts import (
    IMAGE_PROMPT_SYSTEM_PROMPT,
    build_panel_prompt_text,
    build_scene_user_message,
)
from app.storage import project_storage

# Teto de max_tokens do groq/compound (ver app/config.py) — uma cena com
# vários painéis + personagens novos cabe folgado nesse orçamento.
PANEL_MAX_TOKENS = 4096


def compute_panel_count(actual_duration: float, segment_seconds: float) -> int:
    """Quantos painéis uma cena "idealmente" precisa para que o vídeo
    final (Fase 5, ~`segment_seconds` por clipe) não fique congelado
    enquanto a narração continua. Sempre pelo menos 1. Esse número pode
    ser reduzido depois por `allocate_panel_counts` se estourar o teto do
    projeto (`Settings.max_image_prompts`)."""
    if segment_seconds <= 0:
        return 1
    return max(1, math.ceil(actual_duration / segment_seconds))


def allocate_panel_counts(
    scene_durations: dict[str, float], segment_seconds: float, max_total: int
) -> dict[str, int]:
    """Quantos painéis cada cena recebe, respeitando um teto para a soma
    do lote inteiro (pedido do usuário: editar manualmente no Kdenlive,
    sem precisar de uma imagem a cada `segment_seconds`).

    Se a soma "ideal" (por duração) já cabe no teto, usa ela sem
    modificação — o teto só entra em ação quando o projeto pediria mais
    painéis do que o combinado. Quando precisa cortar, redistribui
    `max_total` proporcionalmente à duração de cada cena (método dos
    maiores restos, para a soma bater exatamente), sempre com pelo menos
    1 painel por cena — se houver mais cenas do que `max_total`, o teto é
    ultrapassado propositalmente (nunca zero painéis numa cena)."""
    scene_ids = list(scene_durations.keys())
    if not scene_ids:
        return {}

    ideal = {sid: compute_panel_count(scene_durations[sid], segment_seconds) for sid in scene_ids}
    if sum(ideal.values()) <= max_total:
        return ideal

    budget = max(max_total, len(scene_ids))  # nunca menos de 1 painel por cena
    total_duration = sum(scene_durations.values()) or 1.0
    shares = {sid: budget * (scene_durations[sid] / total_duration) for sid in scene_ids}
    allocation = {sid: max(1, math.floor(shares[sid])) for sid in scene_ids}

    remainder = budget - sum(allocation.values())
    if remainder > 0:
        # Sobrou orçamento por causa do floor — dá 1 a mais para quem tem
        # a maior parte fracionária perdida no arredondamento, até bater.
        order = sorted(scene_ids, key=lambda sid: shares[sid] - math.floor(shares[sid]), reverse=True)
        for sid in order[:remainder]:
            allocation[sid] += 1
    elif remainder < 0:
        # O mínimo de 1 por cena empurrou a soma além do orçamento (muitas
        # cenas curtas) — tira 1 de quem tem mais, sem nunca zerar ninguém.
        order = sorted(scene_ids, key=lambda sid: allocation[sid], reverse=True)
        i = 0
        while remainder < 0 and any(allocation[sid] > 1 for sid in scene_ids):
            sid = order[i % len(order)]
            if allocation[sid] > 1:
                allocation[sid] -= 1
                remainder += 1
            i += 1

    return allocation


def _strip_code_fences(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


def _parse_panel_response(
    raw_json: str, expected_panel_count: int
) -> tuple[dict[str, str], dict[str, str], list[dict]]:
    try:
        data = json.loads(_strip_code_fences(raw_json))
    except json.JSONDecodeError as exc:
        raise ImagePromptError("A IA não retornou um JSON válido ao gerar os painéis.") from exc

    if not isinstance(data, dict) or "panels" not in data:
        raise ImagePromptError("A resposta da IA não veio no formato esperado (faltou 'panels').")

    new_characters = data.get("new_characters") or {}
    new_locations = data.get("new_locations") or {}
    panels = data.get("panels") or []
    if not isinstance(panels, list) or len(panels) == 0:
        raise ImagePromptError("A IA não gerou nenhum painel para a cena.")
    if len(panels) != expected_panel_count:
        # Tolerante: usa o que veio, mas não falha por uma diferença de
        # contagem — a IA pode arredondar de forma ligeiramente diferente.
        pass
    return new_characters, new_locations, panels


def recompute_project_state(all_scenes: list[Scene], image_prompts: list[ImagePrompt]) -> str:
    """Deriva o estado macro a partir dos dados reais (não de um valor
    fixo) — usado ao final do job e também pelas rotas de upload
    (app/web/routes/image_prompts.py), já que subir uma imagem também
    pode fazer o projeto avançar de estado.

    Importante: só considera os prompts "prontos" quando TODAS as cenas já
    têm pelo menos um painel — senão um job que processou só algumas cenas
    (interrompido, ou uma geração resumível) reportaria erroneamente
    IMAGE_PROMPTS_READY. Enquanto isso, o estado fica em
    IMAGE_PROMPTS_GENERATING — mesmo padrão que AUDIO_GENERATING já usa
    como "repouso parcial", não só "rodando agora" (ver audio/service.py).
    """
    covered_scene_ids = {p.scene_id for p in image_prompts}
    if len(covered_scene_ids) < len(all_scenes):
        return ProjectState.IMAGE_PROMPTS_GENERATING.value
    if not image_prompts:
        return ProjectState.AUDIO_READY.value
    if all(p.image_path for p in image_prompts):
        return ProjectState.IMAGES_READY.value
    if any(p.image_path for p in image_prompts):
        return ProjectState.WAITING_IMAGES.value
    return ProjectState.IMAGE_PROMPTS_READY.value


def _process_scene(
    db: Session,
    project_id: str,
    scene: Scene,
    ai: AIProviderAdapter,
    settings: Settings,
    biblia_visual_text: str,
    character_cache: dict[str, str],
    location_cache: dict[str, str],
    existing_panels: list[ImagePrompt],
    next_global_order: int,
    allocated_panel_count: int,
) -> int:
    """Gera (ou regenera) os painéis de uma cena. Devolve o próximo
    global_order livre (só muda quando a cena ganha painéis pela primeira
    vez; regeneração reaproveita os slots já existentes).

    `allocated_panel_count` já vem calculado por `allocate_panel_counts`
    para o lote inteiro (respeita o teto do projeto) — só é usado quando a
    cena está ganhando painéis pela primeira vez; regeneração sempre
    mantém a contagem que a cena já tinha."""
    is_regeneration = bool(existing_panels)
    panel_count = len(existing_panels) if is_regeneration else allocated_panel_count

    # Manda o cache INTEIRO (não só os nomes que batem exatamente com
    # scene.characters) — a IA precisa ver tudo já definido para conseguir
    # reconhecer que "Gabriel" numa cena e "o anjo Gabriel" noutra são a
    # mesma pessoa (ver regra de continuidade no system prompt). Filtrar
    # antes por igualdade de string era exatamente o que quebrava a
    # continuidade quando o nome variava de uma cena para outra.
    response = ai.complete(
        build_scene_user_message(
            location=scene.location,
            time=scene.time,
            action=scene.action,
            emotion=scene.emotion,
            narration_excerpt=scene.narration_excerpt,
            panel_count=panel_count,
            scene_characters=scene.characters,
            known_characters=character_cache,
            known_locations=location_cache,
            biblia_visual_text=biblia_visual_text,
        ),
        system=IMAGE_PROMPT_SYSTEM_PROMPT,
        max_tokens=PANEL_MAX_TOKENS,
    )
    new_characters, new_locations, panels = _parse_panel_response(response, panel_count)

    for name, description in new_characters.items():
        # Guarda contra a IA reenviar um personagem que já está no cache
        # (aconteceu na prática, mesmo instruída a não fazer isso) — sem
        # este "if", cada reenvio criava uma segunda linha em `characters`
        # com uma descrição DIFERENTE da primeira, e cenas diferentes
        # podiam acabar usando versões inconsistentes do mesmo personagem
        # (idade/roupa/altura mudando de cena pra cena).
        if name in character_cache:
            continue
        character_cache[name] = description
        db.add(Character(project_id=project_id, name=name, visual_description=description))

    for name, description in new_locations.items():
        # Mesma guarda que `new_characters` já usa, pelo mesmo motivo —
        # sem ela, um cenário reenviado pela IA podia acabar com duas
        # descrições diferentes e cenas voltando ao mesmo lugar com
        # arquitetura/iluminação inconsistente entre si.
        if name in location_cache:
            continue
        location_cache[name] = description
        db.add(Location(project_id=project_id, name=name, visual_description=description))

    if is_regeneration:
        for panel_row, panel_data in zip(existing_panels, panels):
            panel_row.shot_type = str(panel_data.get("shot_type", ""))
            panel_row.prompt_text = build_panel_prompt_text(
                str(panel_data.get("description", "")), panel_row.shot_type
            )
            panel_row.image_path = None
            panel_row.image_uploaded_at = None
            panel_row.status = "ready"
        return next_global_order

    order = next_global_order
    for index, panel_data in enumerate(panels, start=1):
        shot_type = str(panel_data.get("shot_type", ""))
        db.add(
            ImagePrompt(
                project_id=project_id,
                scene_id=scene.id,
                global_order=order,
                order_in_scene=index,
                shot_type=shot_type,
                prompt_text=build_panel_prompt_text(str(panel_data.get("description", "")), shot_type),
                status="ready",
            )
        )
        order += 1
    return order


def _write_export_file(project_id: str, image_prompts: list[ImagePrompt]) -> None:
    # Só os textos dos prompts, um por bloco, separados por linha em
    # branco — sem rótulo "PROMPT NNN" (pedido do usuário: a ferramenta
    # externa não precisa dele, só usa a linha em branco para separar um
    # prompt do outro; um rótulo a mais só teria virado ruído/mais um
    # "prompt" indesejado).
    project_storage.image_prompts_export_path(project_id).write_text(
        "\n\n".join(p.prompt_text for p in image_prompts), encoding="utf-8"
    )


def run_image_prompts_job(
    project_id: str,
    job_id: str,
    ai: AIProviderAdapter,
    session_factory: sessionmaker,
    scene_ids: list[str] | None = None,
) -> None:
    db: Session = session_factory()
    try:
        project = db.get(Project, project_id)
        job = db.get(Job, job_id)
        if project is None or job is None:
            return

        try:
            settings = get_settings()
            all_scenes = SceneRepository(db).list_for_project(project_id)
            if not all_scenes:
                raise ImagePromptError("Este projeto ainda não tem cenas — gere a narração primeiro.")
            if any(s.actual_duration is None for s in all_scenes):
                raise ImagePromptError(
                    "Nem todas as cenas têm áudio gerado — gere o áudio primeiro (aba Áudio)."
                )

            image_prompt_repo = ImagePromptRepository(db)
            biblia_visual_text = project_storage.input_biblia_visual_path(project_id).read_text(encoding="utf-8")
            character_cache = {c.name: c.visual_description for c in db.query(Character).filter(Character.project_id == project_id)}
            location_cache = {l.name: l.visual_description for l in db.query(Location).filter(Location.project_id == project_id)}

            if scene_ids is not None:
                targets = [s for s in all_scenes if s.id in scene_ids]
            else:
                covered_scene_ids = {p.scene_id for p in image_prompt_repo.list_for_project(project_id)}
                targets = [s for s in all_scenes if s.id not in covered_scene_ids]

            existing_panels_by_scene = {s.id: image_prompt_repo.list_for_scene(s.id) for s in targets}
            new_scenes = [s for s in targets if not existing_panels_by_scene[s.id]]

            # O teto (Settings.max_image_prompts) é do projeto inteiro, não
            # só do lote sendo processado agora — desconta os painéis que
            # outras cenas (já prontas ou sendo regeneradas) já têm.
            new_scene_ids = {s.id for s in new_scenes}
            already_allocated = sum(
                1 for p in image_prompt_repo.list_for_project(project_id) if p.scene_id not in new_scene_ids
            )
            remaining_budget = max(len(new_scenes), settings.max_image_prompts - already_allocated)
            allocation = allocate_panel_counts(
                {s.id: s.actual_duration for s in new_scenes}, settings.video_segment_seconds, remaining_budget
            )

            next_global_order = image_prompt_repo.max_global_order(project_id) + 1
            for scene in targets:
                existing_panels = existing_panels_by_scene[scene.id]
                next_global_order = _process_scene(
                    db,
                    project_id,
                    scene,
                    ai,
                    settings,
                    biblia_visual_text,
                    character_cache,
                    location_cache,
                    existing_panels,
                    next_global_order,
                    allocation.get(scene.id, 1),
                )
                db.commit()  # cada cena persiste por conta própria — falha não perde as anteriores

            all_prompts = image_prompt_repo.list_for_project(project_id)
            _write_export_file(project_id, all_prompts)
            project.state = recompute_project_state(all_scenes, all_prompts)
            job.status = "success"
            job.progress_percent = 100
        except (AIProviderError, ImagePromptError, DomainError) as exc:
            project.state = recompute_project_state(
                SceneRepository(db).list_for_project(project_id), ImagePromptRepository(db).list_for_project(project_id)
            )
            job.status = "failed"
            job.error_message = str(exc)
        except Exception as exc:  # salvaguarda: nunca deixar o job travado em "running"
            project.state = recompute_project_state(
                SceneRepository(db).list_for_project(project_id), ImagePromptRepository(db).list_for_project(project_id)
            )
            job.status = "failed"
            job.error_message = f"Erro inesperado ao gerar os prompts. Tente novamente. ({exc.__class__.__name__})"
        finally:
            job.finished_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
