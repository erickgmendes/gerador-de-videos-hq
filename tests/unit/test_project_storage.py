from app.storage import project_storage


def test_create_project_tree_creates_all_subdirs(test_settings):
    root = project_storage.create_project_tree("projeto-teste")

    assert root == test_settings.projects_dir / "projeto-teste"
    for subdir in project_storage.SUBDIRS:
        assert (root / subdir).is_dir()


def test_project_exists(test_settings):
    assert project_storage.project_exists("inexistente") is False
    project_storage.create_project_tree("existe")
    assert project_storage.project_exists("existe") is True


def test_path_helpers_point_inside_project_root(test_settings):
    project_storage.create_project_tree("p1")
    assert project_storage.input_passagem_path("p1").parent.name == "input"
    assert project_storage.scenes_json_path("p1").parent.name == "roteiro"
