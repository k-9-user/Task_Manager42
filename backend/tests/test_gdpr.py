"""
Tests pour routers/gdpr.py.

Nécessite les fichiers de A (voir avertissement en tête de conftest.py) et
une vraie base Postgres de test.
"""

import re
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import member_client as client

from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User
from app.routers import gdpr as gdpr_router


@pytest.fixture(autouse=True)
def sent_mails(monkeypatch):
    mails = []
    monkeypatch.setattr(
        gdpr_router, "send_mail", lambda to, subject, body: mails.append((to, subject))
    )
    return mails


def _delete_account(client, **overrides):
    payload = {"confirm": True, "confirm_username": client.current_user.username}
    payload.update(overrides)
    return client.request("DELETE", "/api/gdpr/account", json=payload)


UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def test_export_contains_profile_and_owned_project(client):
    client.post("/api/projects", json={"name": "Mon projet", "description": None})

    response = client.get("/api/gdpr/export")

    assert response.status_code == 200
    assert response.headers["content-disposition"] == "attachment; filename=gdpr_export.json"

    body = response.json()
    assert body["profile"]["username"] == client.current_user.username
    assert body["profile"]["sign_in"] == "password"
    assert "password_hash" not in body["profile"]
    assert body["projects"] == [
        {
            "name": "Mon projet",
            "your_role": "owner",
            "owner": True,
            "joined_at": body["projects"][0]["joined_at"],
        }
    ]
    assert body["projects"][0]["joined_at"].endswith(" UTC")


def test_export_omits_empty_sections_and_internal_ids(client):
    response = client.get("/api/gdpr/export")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"about", "profile"}
    assert "display_name" not in body["profile"]
    assert UUID_PATTERN.search(response.text) is None


def test_export_covers_user_content_without_secrets(client, db_session, sent_mails):
    project_id = uuid.UUID(
        client.post("/api/projects", json={"name": "Export", "description": None}).json()[
            "data"
        ]["project"]["id"]
    )
    user_id = client.current_user.id
    task = Task(project_id=project_id, title="Exported task", assignee_id=user_id)
    db_session.add(task)
    db_session.flush()
    db_session.add(Comment(task_id=task.id, author_id=user_id, content="my comment"))
    db_session.add(
        Attachment(task_id=task.id, file_url="/uploads/x.txt", file_name="x.txt", uploaded_by=user_id)
    )
    db_session.commit()

    response = client.get("/api/gdpr/export")

    assert response.status_code == 200
    body = response.json()
    assert [(c["task"], c["project"], c["text"]) for c in body["comments"]] == [
        ("Exported task", "Export", "my comment")
    ]
    assert [(f["file_name"], f["task"]) for f in body["uploaded_files"]] == [
        ("x.txt", "Exported task")
    ]
    assert [(t["title"], t["project"]) for t in body["assigned_tasks"]] == [
        ("Exported task", "Export")
    ]
    assert UUID_PATTERN.search(response.text) is None
    assert "password_hash" not in response.text
    assert "key_hash" not in response.text
    assert "oauth_id" not in response.text
    assert sent_mails == [(client.current_user.email, "Your Task Manager data export")]


def test_delete_account_requires_confirm(client, sent_mails):
    response = _delete_account(client, confirm=False)
    assert response.status_code == 400
    assert sent_mails == []


def test_delete_account_requires_matching_username(client, db_session, sent_mails):
    response = _delete_account(client, confirm_username="someone-else")

    assert response.status_code == 400
    assert db_session.get(User, client.current_user.id) is not None
    assert sent_mails == []


def test_delete_account_removes_user_and_owned_projects(client, db_session, sent_mails):
    project_id = uuid.UUID(
        client.post("/api/projects", json={"name": "A supprimer", "description": None}).json()[
            "data"
        ]["project"]["id"]
    )
    user_id = client.current_user.id

    response = _delete_account(client)

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {}}
    assert db_session.query(User).filter(User.id == user_id).first() is None
    assert db_session.query(Project).filter(Project.id == project_id).first() is None
    assert sent_mails == [(client.current_user.email, "Your Task Manager account was deleted")]


def test_delete_account_keeps_uploaded_attachment_anonymized(client, make_user, db_session):
    other_owner = make_user()
    project = Project(name="Someone else's", owner_id=other_owner.id)
    db_session.add(project)
    db_session.flush()
    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=other_owner.id, role=ProjectRole.OWNER),
        ProjectMember(
            project_id=project.id, user_id=client.current_user.id, role=ProjectRole.EDITOR,
        ),
    ])
    task = Task(project_id=project.id, title="Shared task")
    db_session.add(task)
    db_session.flush()
    attachment = Attachment(
        task_id=task.id,
        file_url="/uploads/shared.pdf",
        file_name="shared.pdf",
        uploaded_by=client.current_user.id,
    )
    db_session.add(attachment)
    db_session.commit()
    attachment_id = attachment.id

    response = _delete_account(client)

    assert response.status_code == 200
    db_session.expire_all()
    kept = db_session.get(Attachment, attachment_id)
    assert kept is not None
    assert kept.uploaded_by is None


def test_delete_account_transfers_ownership_to_oldest_remaining_member(
    client, make_user, db_session
):
    project = client.post(
        "/api/projects", json={"name": "A transferer", "description": None}
    ).json()["data"]["project"]
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

    joined = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.query(ProjectMember).filter_by(
        project_id=project_id, user_id=first_member.id,
    ).update({
        "id": uuid.UUID("ffffffff-ffff-ffff-ffff-fffffffffffe"),
        "joined_at": joined,
    })
    db_session.query(ProjectMember).filter_by(
        project_id=project_id, user_id=second_member.id,
    ).update({
        "id": uuid.UUID("00000000-0000-0000-0000-000000000002"),
        "joined_at": joined + timedelta(hours=1),
    })
    db_session.commit()

    response = _delete_account(client)
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
    ).json()["data"]["project"]
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

    response = _delete_account(client)
    assert response.status_code == 200

    project_row = db_session.query(Project).filter(Project.id == project_id).first()
    assert project_row.owner_id == co_owner.id, "un owner existant est préféré au plus ancien membre"
