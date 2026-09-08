"""
Tests pour routers/tasks.py — cf la liste de cas dans SUIVI-PERSONNE-B.md.

Nécessite les fichiers de A (voir avertissement en tête de conftest.py) et
une vraie base Postgres de test.
"""

import uuid

from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus


def _add_member(db_session, project_id, user_id, role: ProjectRole) -> ProjectMember:
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db_session.add(member)
    db_session.commit()
    return member


def _create_project_via_api(client, name="Projet test"):
    response = client.post("/api/projects", json={"name": name, "description": None})
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/tasks
# ---------------------------------------------------------------------------


def test_create_task_as_owner(client):
    project = _create_project_via_api(client)

    response = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Premiere tache"}
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Premiere tache"
    assert data["status"] == "todo"
    assert data["project_id"] == project["id"]


def test_create_task_description_too_long_rejected(client):
    project = _create_project_via_api(client)

    response = client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache", "description": "x" * 5001},
    )

    assert response.status_code == 422


def test_create_task_as_editor(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    editor = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), editor.id, ProjectRole.EDITOR)

    login_as(editor)
    response = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Tache editor"}
    )

    assert response.status_code == 201


def test_create_task_as_viewer_forbidden(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    viewer = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Interdit"}
    )

    assert response.status_code == 403


def test_create_task_assignee_not_a_member_rejected(client, make_user):
    project = _create_project_via_api(client)
    outsider = make_user()

    response = client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache", "assignee_id": str(outsider.id)},
    )

    assert response.status_code == 400


def test_create_task_assignee_member_ok(client, make_user):
    project = _create_project_via_api(client)
    member = make_user()
    client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(member.id), "role": "viewer"},
    )

    response = client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache assignee", "assignee_id": str(member.id)},
    )

    assert response.status_code == 201
    assert response.json()["data"]["assignee_id"] == str(member.id)


# ---------------------------------------------------------------------------
# GET /api/projects/{id}/tasks
# ---------------------------------------------------------------------------


def test_list_tasks_filter_by_status(client, db_session):
    project = _create_project_via_api(client)
    project_id = uuid.UUID(project["id"])

    todo_resp = client.post(f"/api/projects/{project['id']}/tasks", json={"title": "Todo"})
    done_task_id = uuid.UUID(
        client.post(f"/api/projects/{project['id']}/tasks", json={"title": "Done"}).json()[
            "data"
        ]["id"]
    )
    db_session.query(Task).filter(Task.id == done_task_id).update(
        {"status": TaskStatus.DONE}
    )
    db_session.commit()

    response = client.get(f"/api/projects/{project['id']}/tasks", params={"status": "done"})
    titles = [t["title"] for t in response.json()["data"]["tasks"]]

    assert titles == ["Done"]
    assert response.json()["data"]["total"] == 1


def test_list_tasks_as_viewer_allowed(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    client.post(f"/api/projects/{project['id']}/tasks", json={"title": "Une tache"})

    viewer = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.get(f"/api/projects/{project['id']}/tasks")

    assert response.status_code == 200
    assert response.json()["data"]["total"] == 1


# ---------------------------------------------------------------------------
# PUT /api/tasks/{id}
# ---------------------------------------------------------------------------


def test_update_task_status_as_owner(client):
    project = _create_project_via_api(client)
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Tache"}
    ).json()["data"]["id"]

    response = client.put(f"/api/tasks/{task_id}", json={"status": "in_progress"})

    assert response.status_code == 200
    assert response.json()["data"]["status"] == "in_progress"


def test_update_task_as_viewer_forbidden(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Tache"}
    ).json()["data"]["id"]

    viewer = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.put(f"/api/tasks/{task_id}", json={"status": "done"})

    assert response.status_code == 403


def test_update_task_assignee_not_a_member_rejected(client, make_user):
    project = _create_project_via_api(client)
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Tache"}
    ).json()["data"]["id"]
    outsider = make_user()

    response = client.put(
        f"/api/tasks/{task_id}", json={"assignee_id": str(outsider.id)}
    )

    assert response.status_code == 400


def test_update_task_unknown_id(client):
    response = client.put(f"/api/tasks/{uuid.uuid4()}", json={"status": "done"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/tasks/{id}
# ---------------------------------------------------------------------------


def test_delete_task_as_editor(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "A supprimer"}
    ).json()["data"]["id"]

    editor = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), editor.id, ProjectRole.EDITOR)

    login_as(editor)
    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_delete_task_as_viewer_forbidden(client, make_user, db_session, login_as):
    project = _create_project_via_api(client)
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks", json={"title": "Protegee"}
    ).json()["data"]["id"]

    viewer = make_user()
    _add_member(db_session, uuid.UUID(project["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.delete(f"/api/tasks/{task_id}")

    assert response.status_code == 403
