"""Assembly checks and a real JWT flow, without dependency overrides."""

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.auth.api_key_auth import hash_api_key
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
        ("POST", "/api/auth/oauth/google/exchange"),
        ("POST", "/api/api-keys"),
        ("GET", "/api/api-keys"),
        ("DELETE", "/api/api-keys/{key_id}"),
        ("POST", "/api/api-keys/{key_id}/rotate"),
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
        ("GET", "/api/tasks/{task_id}/attachments"),
        ("POST", "/api/tasks/{task_id}/attachments"),
        ("GET", "/api/attachments/{attachment_id}"),
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
    schema = app.openapi()
    assert "get" in schema["paths"]["/api/tasks/{task_id}/attachments"]
    assert "get" in schema["paths"]["/api/attachments/{attachment_id}"]


def test_real_app_does_not_serve_upload_storage_directly(client):
    upload_file = Path(get_settings().upload_dir) / f"private-{uuid4().hex}.txt"
    upload_file.write_text("private attachment", encoding="utf-8")
    try:
        response = client.get(f"/uploads/{upload_file.name}")
    finally:
        upload_file.unlink(missing_ok=True)

    assert response.status_code == 404


def test_real_app_serves_swagger_docs_but_not_redoc(client):
    docs = client.get("/docs")

    assert docs.status_code == 200
    assert "swagger-ui-bundle.js" in docs.text
    assert client.get("/redoc").status_code == 404


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


def test_postgres_treats_hostile_content_as_data_and_keeps_tenant_boundaries(
    client,
    user_factory,
    auth_headers,
    db_session,
):
    owner = user_factory()
    outsider = user_factory()
    owner_headers = auth_headers(owner)
    outsider_headers = auth_headers(outsider)
    hostile_text = "%_\\' OR 1=1; DROP TABLE tasks; -- <script>alert(1)</script> $(id)"

    project_response = client.post(
        "/api/projects",
        headers=owner_headers,
        json={"name": hostile_text, "description": hostile_text},
    )
    assert project_response.status_code == 201
    project = project_response.json()["data"]["project"]
    assert project["name"] == hostile_text

    hostile_task_response = client.post(
        f"/api/projects/{project['id']}/tasks",
        headers=owner_headers,
        json={"title": hostile_text, "description": hostile_text},
    )
    assert hostile_task_response.status_code == 201
    hostile_task = hostile_task_response.json()["data"]["task"]
    client.post(
        f"/api/projects/{project['id']}/tasks",
        headers=owner_headers,
        json={"title": "Ordinary visible task"},
    )

    private_project = client.post(
        "/api/projects",
        headers=outsider_headers,
        json={"name": "Private hostile project"},
    ).json()["data"]["project"]
    client.post(
        f"/api/projects/{private_project['id']}/tasks",
        headers=outsider_headers,
        json={"title": hostile_text},
    )

    search_response = client.get(
        "/api/search/tasks",
        headers=owner_headers,
        params={"q": "%"},
    )
    assert search_response.status_code == 200
    assert [task["id"] for task in search_response.json()["data"]["tasks"]] == [
        hostile_task["id"]
    ]

    imported_title = "'); DROP TABLE tasks; --"
    import_response = client.post(
        "/api/import",
        headers=owner_headers,
        files={
            "file": (
                "hostile.json",
                json.dumps(
                    {
                        "tasks": [
                            {
                                "project_id": project["id"],
                                "title": imported_title,
                            }
                        ]
                    }
                ),
                "application/json",
            )
        },
    )
    assert import_response.status_code == 200

    comment_response = client.post(
        f"/api/tasks/{hostile_task['id']}/comments",
        headers=owner_headers,
        json={"content": hostile_text},
    )
    assert comment_response.status_code == 201
    assert comment_response.json()["data"]["comment"]["content"] == hostile_text

    db_session.expire_all()
    imported_task = db_session.scalar(select(Task).where(Task.title == imported_title))
    assert imported_task is not None
    assert db_session.scalar(select(Task).where(Task.title == hostile_text)) is not None


def test_real_jwt_gdpr_cannot_delete_last_admin(client, user_factory, auth_headers, db_session):
    admin = user_factory(role=UserRole.ADMIN)
    response = client.request(
        "DELETE", "/api/gdpr/account", headers=auth_headers(admin),
        json={"confirm": True, "confirm_username": admin.username},
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
    raw_key = "owner-without-membership-key"
    key = ApiKey(user_id=owner.id, key_hash=hash_api_key(raw_key))
    db_session.add_all([task, key])
    db_session.commit()
    headers = auth_headers(owner)
    key_headers = {"X-API-Key": raw_key}
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


@pytest.mark.parametrize("parent", ["task", "public-task", "project"])
def test_deleting_parent_removes_attachments_and_files(
    client, user_factory, auth_headers, db_session, tmp_path, parent, monkeypatch,
):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    owner = user_factory()
    uploader = user_factory()
    raw_key = "parent-deletion-key"
    project = Project(name="Parent with files", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    task = Task(project_id=project.id, title="Task with files", banner_url="/uploads/banner.png")
    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER),
        ApiKey(user_id=owner.id, key_hash=hash_api_key(raw_key)),
        task,
    ])
    db_session.flush()
    db_session.add_all([
        Attachment(
            task_id=task.id, uploaded_by=uploader.id,
            file_url=f"/uploads/{name}", file_name=name,
        )
        for name in ("first.txt", "second.pdf")
    ])
    db_session.commit()
    project_id, task_id = project.id, task.id
    stored_files = [tmp_path / name for name in ("first.txt", "second.pdf", "banner.png")]
    bystander = tmp_path / "bystander.txt"
    for path in (*stored_files, bystander):
        path.write_bytes(b"stored")
    requests = {
        "task": (f"/api/tasks/{task_id}", auth_headers(owner)),
        "public-task": (f"/api/v1/public/tasks/{task_id}", {"X-API-Key": raw_key}),
        "project": (f"/api/projects/{project_id}", auth_headers(owner)),
    }

    url, headers = requests[parent]
    response = client.delete(url, headers=headers)

    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(Task, task_id) is None
    assert db_session.query(Attachment).filter_by(task_id=task_id).count() == 0
    assert (db_session.get(Project, project_id) is None) == (parent == "project")
    assert db_session.get(User, uploader.id) is not None
    assert [path.name for path in stored_files if path.exists()] == []
    assert bystander.read_bytes() == b"stored"


def test_deleting_uploader_keeps_attachment_anonymized(
    client, user_factory, auth_headers, db_session, tmp_path, monkeypatch,
):
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    owner = user_factory(role=UserRole.ADMIN)
    uploader = user_factory()
    project = Project(name="Shared files", owner_id=owner.id)
    db_session.add(project)
    db_session.flush()
    task = Task(project_id=project.id, title="Shared task")
    db_session.add_all([
        ProjectMember(project_id=project.id, user_id=owner.id, role=ProjectRole.OWNER),
        task,
    ])
    db_session.flush()
    stored_path = tmp_path / "kept.txt"
    stored_path.write_bytes(b"project file outlives its uploader")
    attachment = Attachment(
        task_id=task.id, uploaded_by=uploader.id,
        file_url="/uploads/kept.txt", file_name="kept.txt",
    )
    db_session.add(attachment)
    db_session.commit()

    response = client.delete(f"/api/users/{uploader.id}", headers=auth_headers(owner))

    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.get(User, uploader.id) is None
    assert db_session.get(Attachment, attachment.id).uploaded_by is None
    assert stored_path.read_bytes() == b"project file outlives its uploader"
