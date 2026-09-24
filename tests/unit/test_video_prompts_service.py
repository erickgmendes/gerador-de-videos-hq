import pytest

from app.domain.errors import VideoPromptError
from app.models.orm import ImagePrompt, Project, Scene
from app.repositories.image_prompt_repository import ImagePromptRepository
from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService
from app.services.video_prompts.service import (
    generate_video_prompts,
    recompute_project_state,
    regenerate_all_video_prompts,
)
from app.storage import project_storage


def _create_project_with_panels(db_session, test_settings, count: int = 3, with_images: bool = True) -> Project:
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Teste Vídeo", bible_reference="Jo 1:1", passage_text="texto")
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
                image_path=f"images/{i:03d}.png" if with_images else None,
            )
        )
    db_session.commit()
    return project


def test_generate_video_prompts_fills_all_panels_and_writes_export(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=3)

    filled = generate_video_prompts(db_session, project.id)

    assert filled == 3
    panels = ImagePromptRepository(db_session).list_for_project(project.id)
    assert all(p.video_prompt_text for p in panels)
    # o texto é fixo — todo painel recebe exatamente o mesmo prompt.
    assert len({p.video_prompt_text for p in panels}) == 1

    export_text = project_storage.video_prompts_export_path(project.id).read_text(encoding="utf-8")
    blocks = export_text.split("\n\n")
    assert len(blocks) == 3
    for block in blocks:
        assert "\n" not in block


def test_generate_video_prompts_is_idempotent_and_never_overwrites(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=2)
    generate_video_prompts(db_session, project.id)

    panel = ImagePromptRepository(db_session).get_by_global_order(project.id, 1)
    panel.video_prompt_text = "texto customizado que não deve ser sobrescrito"
    db_session.commit()

    filled = generate_video_prompts(db_session, project.id)

    assert filled == 0  # os dois painéis já tinham texto — nada novo preenchido
    panel = ImagePromptRepository(db_session).get_by_global_order(project.id, 1)
    assert panel.video_prompt_text == "texto customizado que não deve ser sobrescrito"


def test_generate_video_prompts_fails_when_no_panels(db_session, test_settings):
    project = ProjectService(db_session).create_project(
        ProjectCreate(name="Sem painéis", bible_reference="Jo 1:1", passage_text="texto")
    )

    with pytest.raises(VideoPromptError, match="painéis de imagem"):
        generate_video_prompts(db_session, project.id)


def test_generate_video_prompts_fails_when_images_incomplete(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=3, with_images=False)
    # só o primeiro painel tem imagem
    panel = ImagePromptRepository(db_session).get_by_global_order(project.id, 1)
    panel.image_path = "images/001.png"
    db_session.commit()

    with pytest.raises(VideoPromptError, match="imagem enviada"):
        generate_video_prompts(db_session, project.id)


def test_regenerate_all_video_prompts_clears_existing_video_uploads(db_session, test_settings):
    project = _create_project_with_panels(db_session, test_settings, count=2)
    generate_video_prompts(db_session, project.id)
    panel = ImagePromptRepository(db_session).get_by_global_order(project.id, 1)
    panel.video_path = "videos/001.mp4"
    db_session.commit()

    count = regenerate_all_video_prompts(db_session, project.id)

    assert count == 2
    panels = ImagePromptRepository(db_session).list_for_project(project.id)
    assert all(p.video_prompt_text for p in panels)
    assert all(p.video_path is None for p in panels)


def test_recompute_project_state_ladder():
    def panel(**kwargs):
        return ImagePrompt(project_id="p", scene_id="s", global_order=1, order_in_scene=1, **kwargs)

    assert recompute_project_state([]) == "waiting_images"
    assert recompute_project_state([panel(image_path=None)]) == "waiting_images"
    assert recompute_project_state([panel(image_path="x.png")]) == "images_ready"
    assert (
        recompute_project_state([panel(image_path="x.png", video_prompt_text="p")]) == "video_prompts_ready"
    )
    assert (
        recompute_project_state(
            [panel(image_path="x.png", video_prompt_text="p", video_path="x.mp4")]
        )
        == "videos_ready"
    )
    assert (
        recompute_project_state(
            [
                panel(image_path="x.png", video_prompt_text="p", video_path="x.mp4"),
                panel(image_path="y.png", video_prompt_text="p", video_path=None),
            ]
        )
        == "waiting_videos"
    )
