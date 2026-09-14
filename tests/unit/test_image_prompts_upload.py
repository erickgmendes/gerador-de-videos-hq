import pytest

from app.models.orm import ImagePrompt, Job, Project, Scene
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.schemas.project import ProjectCreate
from app.services.image_prompts.upload import (
    associate_single_upload,
    associate_uploaded_images,
    parse_global_order_from_filename,
)
from app.services.project_service import ProjectService


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("001.png", 1),
        ("042.jpg", 42),
        ("cena_007.jpeg", 7),
        ("cena_007_v2.png", 7),
        ("IMG-003-final.webp", 3),
        ("sem-numero.png", None),
        ("", None),
    ],
)
def test_parse_global_order_from_filename(filename, expected):
    assert parse_global_order_from_filename(filename) == expected


def _create_project_with_panels(db_session, test_settings, count: int = 3) -> Project:
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Teste Upload", bible_reference="Jo 1:1", passage_text="texto")
    )
    scene = Scene(project_id=project.id, order=1, narration_excerpt="texto da cena", actual_duration=10.0)
    db_session.add(scene)
    db_session.commit()
    db_session.refresh(scene)

    for i in range(1, count + 1):
        db_session.add(
            ImagePrompt(
                project_id=project.id,
                scene_id=scene.id,
                global_order=i,
                order_in_scene=i,
                prompt_text=f"prompt {i}",
            )
        )
    db_session.commit()
    return project


def test_associate_uploaded_images_matches_by_filename_number(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=3)

    result = associate_uploaded_images(
        db_session,
        project.id,
        [("001.png", b"fake-bytes-1"), ("003.png", b"fake-bytes-3")],
    )

    assert result.expected_total == 3
    assert result.matched == [1, 3]
    assert result.missing == [2]
    assert result.unmatched_filenames == []

    panels = ImagePromptRepository(db_session).list_for_project(project.id)
    by_order = {p.global_order: p for p in panels}
    assert by_order[1].image_path is not None
    assert by_order[1].status == "image_ready"
    assert by_order[2].image_path is None
    assert by_order[3].image_path is not None


def test_associate_uploaded_images_reports_unmatched_filenames(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=2)

    result = associate_uploaded_images(db_session, project.id, [("sem-numero.png", b"data")])

    assert result.unmatched_filenames == ["sem-numero.png"]
    assert result.matched == []
    assert result.missing == [1, 2]


def test_associate_uploaded_images_ignores_number_with_no_matching_panel(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=2)

    result = associate_uploaded_images(db_session, project.id, [("099.png", b"data")])

    assert result.matched == []
    assert result.unmatched_filenames == ["099.png"]


def test_associate_single_upload_replaces_one_panel(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=2)

    ok = associate_single_upload(db_session, project.id, 2, "qualquer-nome.jpg", b"data")

    assert ok is True
    panel = ImagePromptRepository(db_session).get_by_global_order(project.id, 2)
    assert panel.image_path is not None
    assert panel.status == "image_ready"


def test_associate_single_upload_returns_false_for_unknown_panel(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=1)

    ok = associate_single_upload(db_session, project.id, 999, "x.png", b"data")

    assert ok is False
