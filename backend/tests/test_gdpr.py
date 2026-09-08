"""
Tests pour routers/gdpr.py.

Nécessite les fichiers de A (voir avertissement en tête de conftest.py) et
une vraie base Postgres de test.
"""

import uuid

from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.user import User


def test_export_contains_profile_and_owned_project(client):
    client.post("/api/projects", json={"name": "Mon projet", "description": None})

    response = client.get("/api/gdpr/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename=gdpr_export.json"

    body = response.json()
    assert body["profile"]["id"] == str(client.current_user.id)
    assert "password_hash" not in body["profile"]
    assert [p["name"] for p in body["owned_projects"]] == ["Mon projet"]


def test_delete_account_requires_confirm(client):
    response = client.request("DELETE", "/api/gdpr/account", json={"confirm": False})
    assert response.status_code == 400


def test_delete_account_removes_user_and_owned_projects(client, db_session):
    project_id = uuid.UUID(
        client.post("/api/projects", json={"name": "A supprimer", "description": None}).json()[
            "data"
        ]["id"]
    )
    user_id = client.current_user.id

    response = client.request("DELETE", "/api/gdpr/account", json={"confirm": True})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert db_session.query(User).filter(User.id == user_id).first() is None
    assert db_session.query(Project).filter(Project.id == project_id).first() is None


def test_delete_account_transfers_ownership_to_oldest_remaining_member(
    client, make_user, db_session
):
    project = client.post(
        "/api/projects", json={"name": "A transferer", "description": None}
    ).json()["data"]
    project_id = uuid.UUID(project["id"])
    departing_owner_id = client.current_user.id

    first_member = make_user()
    client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(first_member.id), "role": "viewer"},
    )
    second_member = make_user()
    client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(second_member.id), "role": "editor"},
    )

    response = client.request("DELETE", "/api/gdpr/account", json={"confirm": True})
    assert response.status_code == 200

    project_row = db_session.query(Project).filter(Project.id == project_id).first()
    assert project_row is not None, "le projet doit survivre, il reste des membres"
    assert project_row.owner_id == first_member.id, "le membre le plus ancien devient owner"

    new_owner_membership = (
        db_session.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == first_member.id)
        .first()
    )
    assert new_owner_membership.role == ProjectRole.OWNER

    assert (
        db_session.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id, ProjectMember.user_id == departing_owner_id
        )
        .first()
        is None
    )


def test_delete_account_prefers_existing_owner_as_successor(client, make_user, db_session):
    project = client.post(
        "/api/projects", json={"name": "Deja un autre owner", "description": None}
    ).json()["data"]
    project_id = uuid.UUID(project["id"])

    early_viewer = make_user()
    client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(early_viewer.id), "role": "viewer"},
    )
    co_owner = make_user()
    client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(co_owner.id), "role": "owner"},
    )

    response = client.request("DELETE", "/api/gdpr/account", json={"confirm": True})
    assert response.status_code == 200

    project_row = db_session.query(Project).filter(Project.id == project_id).first()
    assert project_row.owner_id == co_owner.id, "un owner existant est préféré au plus ancien membre"
