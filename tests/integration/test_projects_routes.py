from app.storage import project_storage
from tests.helpers import create_test_project


def test_edit_form_prefilled_with_current_values(app_client):
    project_id = create_test_project(app_client)

    response = app_client.get(f"/projects/{project_id}/editar")

    assert response.status_code == 200
    assert "Evangelho da Semana" in response.text
    assert "Mc 1:16-20" in response.text
    assert "Texto bíblico de teste." in response.text


def test_edit_form_404_for_unknown_project(app_client):
    response = app_client.get("/projects/nao-existe/editar")
    assert response.status_code == 404


def test_update_project_persists_changes_and_redirects(app_client):
    project_id = create_test_project(app_client)

    response = app_client.post(
        f"/projects/{project_id}/editar",
        data={
            "name": "Nome Atualizado",
            "bible_reference": "Jo 3:16",
            "passage_text": "Texto novo da passagem.",
            "biblia_visual_text": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/projects/{project_id}"

    detail = app_client.get(f"/projects/{project_id}")
    assert "Nome Atualizado" in detail.text
    assert "Jo 3:16" in detail.text
    assert project_storage.input_passagem_path(project_id).read_text(encoding="utf-8") == "Texto novo da passagem."


def test_update_project_rejects_empty_name_and_reshows_form(app_client):
    project_id = create_test_project(app_client)

    response = app_client.post(
        f"/projects/{project_id}/editar",
        data={
            "name": " ",
            "bible_reference": "Jo 3:16",
            "passage_text": "Texto novo.",
            "biblia_visual_text": "",
        },
    )

    assert response.status_code == 400
    assert "Informe um nome" in response.text
    # o projeto original não deve ter sido alterado
    detail = app_client.get(f"/projects/{project_id}")
    assert "Evangelho da Semana" in detail.text


def test_delete_project_removes_it_and_redirects_to_dashboard(app_client):
    project_id = create_test_project(app_client)
    assert project_storage.project_exists(project_id)

    response = app_client.post(f"/projects/{project_id}/excluir", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert not project_storage.project_exists(project_id)

    detail = app_client.get(f"/projects/{project_id}")
    assert detail.status_code == 404

    dashboard = app_client.get("/")
    assert "Evangelho da Semana" not in dashboard.text


def test_delete_project_404_for_unknown_project(app_client):
    response = app_client.post("/projects/nao-existe/excluir")
    assert response.status_code == 404
