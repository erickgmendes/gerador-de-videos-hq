import json

import pytest

from app.domain.errors import ProjectNotFoundError, ValidationError
from app.domain.states import ProjectState
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project_service import ProjectService
from app.storage import project_storage


def test_create_project_persists_db_row_and_files(db_session, test_settings):
    service = ProjectService(db_session)
    data = ProjectCreate(
        name="Evangelho de Teste",
        bible_reference="Lucas 15:11-32",
        passage_text="Texto completo da passagem.",
    )

    project = service.create_project(data)

    assert project.id.startswith("evangelho-de-teste-")
    assert project.state == ProjectState.CREATED.value
    assert project_storage.project_exists(project.id)
    assert project_storage.input_passagem_path(project.id).read_text(encoding="utf-8") == "Texto completo da passagem."
    assert project_storage.project_json_path(project.id).exists()


def test_create_project_rejects_empty_name(db_session):
    service = ProjectService(db_session)
    data = ProjectCreate(name=" ", bible_reference="Jo 3:16", passage_text="texto")

    with pytest.raises(ValidationError):
        service.create_project(data)


def test_list_projects_returns_summary_with_progress(db_session):
    service = ProjectService(db_session)
    service.create_project(
        ProjectCreate(name="Projeto A", bible_reference="Mt 1:1", passage_text="texto")
    )

    summaries = service.list_projects()

    assert len(summaries) == 1
    assert summaries[0].name == "Projeto A"
    assert summaries[0].progress == 0


def test_get_project_raises_when_missing(db_session):
    service = ProjectService(db_session)
    with pytest.raises(ProjectNotFoundError):
        service.get_project("nao-existe")


def test_update_project_persists_new_name_reference_and_files(db_session):
    service = ProjectService(db_session)
    project = service.create_project(
        ProjectCreate(name="Nome Original", bible_reference="Mt 1:1", passage_text="texto original")
    )

    updated = service.update_project(
        project.id,
        ProjectUpdate(
            name="Nome Novo",
            bible_reference="Mt 2:1",
            passage_text="texto novo",
            biblia_visual_text="bíblia visual nova",
        ),
    )

    assert updated.name == "Nome Novo"
    assert updated.bible_reference == "Mt 2:1"
    assert updated.id == project.id  # id/pasta nunca mudam
    assert project_storage.input_passagem_path(project.id).read_text(encoding="utf-8") == "texto novo"
    assert (
        project_storage.input_biblia_visual_path(project.id).read_text(encoding="utf-8") == "bíblia visual nova"
    )
    metadata = json.loads(project_storage.project_json_path(project.id).read_text(encoding="utf-8"))
    assert metadata["name"] == "Nome Novo"
    assert metadata["bible_reference"] == "Mt 2:1"


def test_update_project_rejects_empty_name(db_session):
    service = ProjectService(db_session)
    project = service.create_project(
        ProjectCreate(name="Nome Original", bible_reference="Mt 1:1", passage_text="texto")
    )

    with pytest.raises(ValidationError):
        service.update_project(
            project.id, ProjectUpdate(name=" ", bible_reference="Mt 2:1", passage_text="texto novo")
        )


def test_update_project_raises_when_missing(db_session):
    service = ProjectService(db_session)
    with pytest.raises(ProjectNotFoundError):
        service.update_project(
            "nao-existe", ProjectUpdate(name="X", bible_reference="Mt 1:1", passage_text="texto")
        )


def test_delete_project_removes_db_row_and_files(db_session):
    service = ProjectService(db_session)
    project = service.create_project(
        ProjectCreate(name="Projeto a Apagar", bible_reference="Mt 1:1", passage_text="texto")
    )
    assert project_storage.project_exists(project.id)

    service.delete_project(project.id)

    with pytest.raises(ProjectNotFoundError):
        service.get_project(project.id)
    assert not project_storage.project_exists(project.id)


def test_delete_project_raises_when_missing(db_session):
    service = ProjectService(db_session)
    with pytest.raises(ProjectNotFoundError):
        service.delete_project("nao-existe")


def test_delete_project_cascades_child_rows(db_session):
    from app.models.orm import Scene
    from app.repositories.scene_repository import SceneRepository

    service = ProjectService(db_session)
    project = service.create_project(
        ProjectCreate(name="Projeto com Cenas", bible_reference="Mt 1:1", passage_text="texto")
    )
    SceneRepository(db_session).replace_all(
        project.id, [Scene(project_id=project.id, order=1, narration_excerpt="Cena 1.")]
    )

    service.delete_project(project.id)

    assert db_session.query(Scene).filter(Scene.project_id == project.id).count() == 0
