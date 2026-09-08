"""
Tests pour routers/projects.py — cf la liste de cas dans SUIVI-PERSONNE-B.md.

Nécessite les fichiers de A (voir avertissement en tête de conftest.py) et
une vraie base Postgres de test.
"""

import uuid

from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole


def _add_member(db_session, project_id, user_id, role: ProjectRole) -> ProjectMember:
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db_session.add(member)
    db_session.commit()
    return member


def _create_project_via_api(client, name="Projet test", description="desc"):
    response = client.post("/api/projects", json={"name": name, "description": description})
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# POST /api/projects
# ---------------------------------------------------------------------------


def test_create_project_success(client):
    data = _create_project_via_api(client)

    assert data["name"] == "Projet test"
    assert data["description"] == "desc"
    assert data["owner_id"] == str(client.current_user.id)


def test_create_project_auto_creates_owner_membership(client, db_session):
    data = _create_project_via_api(client)

    membership = (
        db_session.query(ProjectMember)
        .filter(
            ProjectMember.project_id == uuid.UUID(data["id"]),
            ProjectMember.user_id == client.current_user.id,
        )
        .first()
    )
    assert membership is not None
    assert membership.role == ProjectRole.OWNER


def test_create_project_missing_name(client):
    response = client.post("/api/projects", json={"description": "desc"})
    assert response.status_code == 422


def test_create_project_description_too_long_rejected(client):
    response = client.post(
        "/api/projects", json={"name": "Test", "description": "x" * 5001}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/projects
# ---------------------------------------------------------------------------


def test_list_projects_only_mine(client, make_user, db_session):
    _create_project_via_api(client, name="A moi")

    other = make_user()
    other_project = Project(name="Pas a moi", owner_id=other.id)
    db_session.add(other_project)
    db_session.flush()
    _add_member(db_session, other_project.id, other.id, ProjectRole.OWNER)

    response = client.get("/api/projects")
    names = [p["name"] for p in response.json()["data"]["projects"]]

    assert "A moi" in names
    assert "Pas a moi" not in names


# ---------------------------------------------------------------------------
# GET /api/projects/{id}
# ---------------------------------------------------------------------------


def test_get_project_detail_success(client):
    data = _create_project_via_api(client)

    response = client.get(f"/api/projects/{data['id']}")
    detail = response.json()["data"]

    assert response.status_code == 200
    assert detail["project"]["id"] == data["id"]
    assert len(detail["members"]) == 1
    assert detail["members"][0]["role"] == "owner"
    assert detail["tasks"] == []


def test_get_project_detail_not_a_member(client, make_user, db_session):
    other = make_user()
    other_project = Project(name="Pas a moi", owner_id=other.id)
    db_session.add(other_project)
    db_session.flush()
    _add_member(db_session, other_project.id, other.id, ProjectRole.OWNER)

    response = client.get(f"/api/projects/{other_project.id}")
    assert response.status_code == 404


def test_get_project_detail_unknown_id(client):
    response = client.get(f"/api/projects/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/projects/{id}
# ---------------------------------------------------------------------------


def test_update_project_as_owner(client):
    data = _create_project_via_api(client)

    response = client.put(f"/api/projects/{data['id']}", json={"name": "Nouveau nom"})

    assert response.status_code == 200
    assert response.json()["data"]["name"] == "Nouveau nom"


def test_update_project_as_editor_forbidden(client, make_user, db_session, login_as):
    data = _create_project_via_api(client)
    editor = make_user()
    _add_member(db_session, uuid.UUID(data["id"]), editor.id, ProjectRole.EDITOR)

    login_as(editor)
    response = client.put(f"/api/projects/{data['id']}", json={"name": "Hacked"})

    assert response.status_code == 403


def test_update_project_as_viewer_forbidden(client, make_user, db_session, login_as):
    data = _create_project_via_api(client)
    viewer = make_user()
    _add_member(db_session, uuid.UUID(data["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.put(f"/api/projects/{data['id']}", json={"name": "Hacked"})

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# DELETE /api/projects/{id}
# ---------------------------------------------------------------------------


def test_delete_project_as_owner_cascades(client, db_session):
    data = _create_project_via_api(client)
    project_id = uuid.UUID(data["id"])

    response = client.delete(f"/api/projects/{project_id}")

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert db_session.query(Project).filter(Project.id == project_id).first() is None
    assert (
        db_session.query(ProjectMember).filter(ProjectMember.project_id == project_id).count()
        == 0
    )


def test_delete_project_as_viewer_forbidden(client, make_user, db_session, login_as):
    data = _create_project_via_api(client)
    viewer = make_user()
    _add_member(db_session, uuid.UUID(data["id"]), viewer.id, ProjectRole.VIEWER)

    login_as(viewer)
    response = client.delete(f"/api/projects/{data['id']}")

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/projects/{id}/members
# ---------------------------------------------------------------------------


def test_add_member_as_owner(client, make_user):
    data = _create_project_via_api(client)
    new_member = make_user()

    response = client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(new_member.id), "role": "editor"},
    )

    assert response.status_code == 201
    assert response.json()["data"]["role"] == "editor"


def test_add_member_as_viewer_forbidden(client, make_user, db_session, login_as):
    data = _create_project_via_api(client)
    viewer = make_user()
    _add_member(db_session, uuid.UUID(data["id"]), viewer.id, ProjectRole.VIEWER)
    someone_else = make_user()

    login_as(viewer)
    response = client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(someone_else.id), "role": "editor"},
    )

    assert response.status_code == 403


def test_add_member_unknown_user_id(client):
    data = _create_project_via_api(client)

    response = client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(uuid.uuid4()), "role": "editor"},
    )

    assert response.status_code == 400


def test_add_member_already_member(client, make_user):
    data = _create_project_via_api(client)
    duplicate = make_user()

    first = client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(duplicate.id), "role": "viewer"},
    )
    assert first.status_code == 201

    second = client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(duplicate.id), "role": "editor"},
    )
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# DELETE /api/projects/{id}/members/{user_id}
# ---------------------------------------------------------------------------


def test_remove_member_success(client, make_user):
    data = _create_project_via_api(client)
    member = make_user()
    client.post(
        f"/api/projects/{data['id']}/members",
        json={"user_id": str(member.id), "role": "viewer"},
    )

    response = client.delete(f"/api/projects/{data['id']}/members/{member.id}")

    assert response.status_code == 200
    assert response.json() == {"success": True}


def test_remove_last_owner_forbidden(client):
    data = _create_project_via_api(client)

    response = client.delete(
        f"/api/projects/{data['id']}/members/{client.current_user.id}"
    )

    assert response.status_code == 400
