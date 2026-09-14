"""Infraestrutura genérica de jobs em background (ver tabela `jobs`,
Fase 1). Independente do tipo de job — narração hoje, outras operações
longas nas próximas fases.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.states import ProjectState
from app.models.orm import Job, Project

# Estado macro do qual cada job_type parte de volta em caso de interrupção
# — usado quando o estado correto é sempre fixo (a etapa é tudo-ou-nada,
# sem progresso parcial possível).
_ROLLBACK_STATE_BY_JOB_TYPE: dict[str, ProjectState] = {
    "narration": ProjectState.CREATED,
    "audio": ProjectState.NARRATION_READY,
}


def _reconcile_image_prompts_state(db: Session, project_id: str) -> str:
    """`image_prompts` pode ter progresso parcial de verdade (algumas
    cenas já com painéis gerados quando o processo foi encerrado) — um
    alvo fixo aqui subestimaria o progresso já salvo. Import local para
    não acoplar este módulo genérico a um serviço de uma fase específica
    fora deste caso."""
    from app.repositories.image_prompt_repository import ImagePromptRepository
    from app.repositories.scene_repository import SceneRepository
    from app.services.image_prompts.service import recompute_project_state

    return recompute_project_state(
        SceneRepository(db).list_for_project(project_id),
        ImagePromptRepository(db).list_for_project(project_id),
    )


# job_type -> função que recalcula o estado a partir dos dados reais —
# usado quando progresso parcial é possível e importa preservá-lo.
_CUSTOM_ROLLBACK_BY_JOB_TYPE: dict[str, Callable[[Session, str], str]] = {
    "image_prompts": _reconcile_image_prompts_state,
}


def reconcile_stale_jobs(db: Session) -> int:
    """Ao iniciar a aplicação, qualquer Job que ficou "running" porque o
    processo anterior foi encerrado no meio é marcado como falho, e o
    projeto volta ao estado anterior à etapa interrompida — nunca fica
    travado mostrando um spinner infinito (seção 41 da especificação)."""
    stale_jobs = list(db.scalars(select(Job).where(Job.status == "running")))
    for job in stale_jobs:
        job.status = "failed"
        job.error_message = "Interrompido porque a aplicação foi reiniciada. Tente novamente."
        job.finished_at = datetime.now(timezone.utc)

        project = db.get(Project, job.project_id)
        if project is None:
            continue

        custom_rollback = _CUSTOM_ROLLBACK_BY_JOB_TYPE.get(job.job_type)
        if custom_rollback is not None:
            project.state = custom_rollback(db, job.project_id)
        else:
            rollback_state = _ROLLBACK_STATE_BY_JOB_TYPE.get(job.job_type)
            if rollback_state is not None:
                project.state = rollback_state.value

    if stale_jobs:
        db.commit()
    return len(stale_jobs)


def get_latest_job(db: Session, project_id: str, job_type: str) -> Job | None:
    stmt = (
        select(Job)
        .where(Job.project_id == project_id, Job.job_type == job_type)
        .order_by(Job.started_at.desc())
    )
    return db.scalars(stmt).first()
