import pytest

from app.domain.errors import ProjectNotFoundError, ValidationError
from app.domain.states import ProjectState
from app.schemas.project import ProjectCreate
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
