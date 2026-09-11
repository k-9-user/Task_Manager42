"""Assembly checks and a real JWT flow, without dependency overrides."""

import json
from uuid import UUID

import pytest
from sqlalchemy import select

from app.main import app
from app.config import get_settings
from app.models.api_key import ApiKey
from app.models.attachment import Attachment
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task
from app.models.user import User, UserRole


def test_real_app_registers_all_feature_routes():
    expected = {
        ("POST", "/api/auth/register"),
        ("POST", "/api/auth/login"),
        ("GET", "/api/users/me"),
        ("GET", "/health"),
        ("GET", "/api/projects"),
        ("POST", "/api/projects"),
        ("GET", "/api/projects/{project_id}"),
        ("PUT", "/api/projects/{project_id}"),
        ("DELETE", "/api/projects/{project_id}"),
        ("POST", "/api/projects/{project_id}/members"),
        ("DELETE", "/api/projects/{project_id}/members/{user_id}"),
        ("GET", "/api/projects/{project_id}/tasks"),
        ("POST", "/api/projects/{project_id}/tasks"),
        ("PUT", "/api/tasks/{task_id}"),
        ("DELETE", "/api/tasks/{task_id}"),
        ("GET", "/api/gdpr/export"),
        ("DELETE", "/api/gdpr/account"),
        ("GET", "/api/notifications"),
        ("PUT", "/api/notifications/{notification_id}/read"),
        ("PUT", "/api/notifications/read-all"),
        ("GET", "/api/search/tasks"),
        ("POST", "/api/tasks/{task_id}/attachments"),
        ("DELETE", "/api/attachments/{attachment_id}"),
        ("GET", "/api/export"),
        ("POST", "/api/import"),
        ("GET", "/api/v1/public/projects"),
        ("GET", "/api/v1/public/tasks"),
        ("POST", "/api/v1/public/tasks"),
        ("PUT", "/api/v1/public/tasks/{task_id}"),
        ("DELETE", "/api/v1/public/tasks/{task_id}"),
    }
    actual = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", ())
    }
    assert expected <= actual, f"Missing routes: {sorted(expected - actual)}"


def test_real_jwt_project_task_flow_enforces_membership(client, db_session):
    assert app.dependency_overrides == {}
    assert client.get("/api/projects").status_code == 401
    owner = client.post("/api/auth/register", json={
        "email": "owner@example.com", "username": "project_owner",
        "password": "valid-password-42",
    })
    outsider = client.post("/api/auth/register", json={
        "email": "outsider@example.com", "username": "project_outsider",
        "password": "valid-password-42",
    })
    assert owner.status_code == outsider.status_code == 201
    headers = {"Authorization": f"Bearer {owner.json()['data']['token']}"}
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['data']['token']}"}
    project_response = client.post("/api/projects", headers=headers, json={"name": "JWT project"})
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()["data"]["project"]
    tasks_url = f"/api/projects/{project['id']}/tasks"
    created = client.post(tasks_url, headers=headers, json={"title": "JWT task"})
    assert created.status_code == 201, created.text
    task = created.json()["data"]["task"]
    search = client.get("/api/search/tasks", headers=headers, params={"q": "JWT task"})
    assert search.status_code == 200, search.text
    assert [item["id"] for item in search.json()["data"]["tasks"]] == [task["id"]]
    hidden_search = client.get("/api/search/tasks", headers=outsider_headers)
    assert hidden_search.status_code == 200
    assert hidden_search.json()["data"] == {"tasks": [], "total": 0}
    assert client.get("/api/search/tasks").status_code == 401
    task_url = f"/api/tasks/{task['id']}"
    denied = client.put(task_url, headers=outsider_headers, json={"status": "done"})
    assert denied.status_code == 404
    invited = client.post(f"/api/projects/{project['id']}/members", headers=headers, json={
        "user_id": outsider.json()["data"]["user"]["id"], "role": "viewer",
    })
    assert invited.status_code == 201, invited.text
    visible = client.get(tasks_url, headers=outsider_headers)
    assert visible.status_code == 200
    assert [item["id"] for item in visible.json()["data"]["tasks"]] == [task["id"]]
    assert client.put(task_url, headers=outsider_headers, json={"status": "done"}).status_code == 403
    updated = client.put(task_url, headers=headers, json={"status": "done"})
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["task"]["status"] == "done"
    persisted = db_session.scalar(select(Task).where(Task.id == UUID(task["id"])))
    assert persisted.status.value == "done"
    assert app.dependency_overrides == {}


def test_real_jwt_gdpr_cannot_delete_last_admin(client, user_factory, auth_headers, db_session):
    admin = user_factory(role=UserRole.ADMIN)
    response = client.request(
        "DELETE", "/api/gdpr/account", headers=auth_headers(admin), json={"confirm": True},
    )
    assert response.status_code == 409
    assert response.json()["error"] == "At least one active administrator is required"
    assert db_session.get(User, admin.id) is not None


def test_owner_id_alone_grants_no_c_access(client, user_factory, auth_headers, db_session):
    owner = user_factory()
    project = Project(name="Not a membership", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    task = Task(project_id=project.id, title="Hidden owner task")
    key = ApiKey(user_id=owner.id, key="owner-without-membership-key")
    db_session.add_all([task, key])
    db_session.commit()
    headers = auth_headers(owner)
    key_headers = {"X-API-Key": key.key}
    assert db_session.query(ProjectMember).filter_by(project_id=project.id).count() == 0

    search = client.get("/api/search/tasks", headers=headers)
    assert search.status_code == 200
    assert search.json()["data"] == {"tasks": [], "total": 0}
    exported = client.get("/api/export?format=json", headers=headers)
    assert exported.status_code == 200
    assert exported.json()["projects"] == []
    for resource in ("projects", "tasks"):
        response = client.get(f"/api/v1/public/{resource}", headers=key_headers)
        assert response.status_code == 200
        assert response.json()["data"][resource] == []
    denied_requests = [
        client.post("/api/v1/public/tasks", headers=key_headers, json={
            "project_id": str(project.id), "title": "Denied",
        }),
        client.put(f"/api/v1/public/tasks/{task.id}", headers=key_headers, json={"status": "done"}),
        client.delete(f"/api/v1/public/tasks/{task.id}", headers=key_headers),
        client.post(f"/api/tasks/{task.id}/attachments", headers=headers, files={
            "file": ("denied.txt", b"denied", "text/plain"),
        }),
        client.post("/api/import", headers=headers, files={
            "file": ("denied.json", json.dumps({"projects": [{
                "id": str(project.id), "name": project.name,
                "tasks": [{"project_id": str(project.id), "title": "Denied import"}],
            }]}), "application/json"),
        }),
    ]
    for response in denied_requests:
        assert response.status_code == 404, f"{response.request.url}: {response.text}"
    db_session.expire_all()
    assert db_session.get(Task, task.id).status.value == "todo"
    assert db_session.query(Task).filter_by(project_id=project.id).count() == 1


@pytest.mark.parametrize("parent", ["task", "project", "uploader"])
def test_attachment_restricts_parent_deletion_and_rolls_back(
    client, user_factory, auth_headers, db_session, tmp_path, parent, monkeypatch,
):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    owner = user_factory(role=UserRole.ADMIN)
    uploader = user_factory()
    project = Project(name="Protected parent", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    member = ProjectMember(project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER)
    task = Task(project_id=project.id, title="Protected task")
    db_session.add_all([member, task])
    db_session.flush()
    stored_path = tmp_path / "protected.txt"
    stored_path.write_bytes(b"must survive restricted deletion")
    attachment = Attachment(
        task_id=task.id, uploaded_by=uploader.id,
        file_url="/uploads/protected.txt", file_name="protected.txt",
    )
    db_session.add(attachment)
    db_session.commit()
    ids = (project.id, member.id, task.id, uploader.id, attachment.id)
    paths = {
        "task": f"/api/tasks/{task.id}",
        "project": f"/api/projects/{project.id}",
        "uploader": f"/api/users/{uploader.id}",
    }

    response = client.delete(paths[parent], headers=auth_headers(owner))

    assert response.status_code == 409, response.text
    assert response.json() == {
        "success": False,
        "error": (
            "User has related resources" if parent == "uploader"
            else "Resource has related data or a referenced resource no longer exists"
        ),
    }
    db_session.expire_all()
    for model, identity in zip((Project, ProjectMember, Task, User, Attachment), ids):
        assert db_session.get(model, identity) is not None
    assert stored_path.read_bytes() == b"must survive restricted deletion"
    # A fresh request/session must still be usable after the rejected deletion.
    assert client.get(f"/api/projects/{ids[0]}", headers=auth_headers(owner)).status_code == 200
