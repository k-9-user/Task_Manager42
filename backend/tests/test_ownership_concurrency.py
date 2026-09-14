"""Ownership mutations must serialize across real JWT requests and DB sessions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select, text

from app.auth.project_permissions import lock_user_projects_for_write
from app.main import app
from app.models.project import Project
from app.models.project_member import ProjectMember, ProjectRole
from app.models.task import Task, TaskStatus
from app.models.user import User


def test_user_project_locks_cover_owned_member_and_assigned_projects(
    db_session, user_factory,
):
    target = user_factory()
    other_owner = user_factory()
    projects = [
        Project(id=UUID(int=3), name="Member", owner_id=other_owner.id),
        Project(id=UUID(int=2), name="Owned", owner_id=target.id),
        Project(id=UUID(int=1), name="Assigned", owner_id=other_owner.id),
    ]
    db_session.add_all(projects)
    db_session.flush()
    db_session.add_all(
        [
            ProjectMember(
                project_id=projects[0].id,
                user_id=target.id,
                role=ProjectRole.EDITOR,
            ),
            Task(
                project_id=projects[2].id,
                title="Assigned after membership removal",
                assignee_id=target.id,
            ),
        ]
    )
    db_session.commit()

    locked = lock_user_projects_for_write(db_session, target.id)

    assert [project.id for project in locked] == [UUID(int=1), UUID(int=2), UUID(int=3)]


@pytest.mark.parametrize("deletion_route", ["admin", "gdpr"])
@pytest.mark.parametrize("membership_exists", [True, False], ids=["member", "assigned-only"])
def test_user_deletion_blocks_member_task_update(
    deletion_route,
    membership_exists,
    client,
    database,
    db_session,
    user_factory,
    auth_headers,
):
    assert database.dialect.name == "postgresql"
    assert app.dependency_overrides == {}
    admin = user_factory(role="admin")
    owner = user_factory()
    editor = user_factory()
    owner_headers = auth_headers(owner)
    editor_headers = auth_headers(editor)
    created = client.post(
        "/api/projects",
        headers=owner_headers,
        json={"name": "Deletion race"},
    )
    assert created.status_code == 201, created.text
    project_id = UUID(created.json()["data"]["project"]["id"])
    invited = client.post(
        f"/api/projects/{project_id}/members", headers=owner_headers,
        json={"user_id": str(editor.id), "role": "editor"},
    )
    assert invited.status_code == 201, invited.text
    task_response = client.post(
        f"/api/projects/{project_id}/tasks", headers=owner_headers,
        json={"title": "Must remain todo", "assignee_id": str(editor.id)},
    )
    assert task_response.status_code == 201, task_response.text
    task_id = UUID(task_response.json()["data"]["task"]["id"])
    if not membership_exists:
        removed = client.delete(
            f"/api/projects/{project_id}/members/{editor.id}", headers=owner_headers,
        )
        assert removed.status_code == 200, removed.text

    deletion_locked = Event()
    update_lock_started = Event()
    release_deletion = Event()
    pids = {}

    def pause_deletion_project_lock(
        connection, cursor, statement, parameters, context, many,
    ):
        if not deletion_locked.is_set() and "FROM projects" in statement and "FOR UPDATE" in statement:
            pids["deletion"] = connection.connection.driver_connection.get_backend_pid()
            deletion_locked.set()
            assert release_deletion.wait(15), "Timed out releasing user deletion"

    def observe_task_project_lock(
        connection, cursor, statement, parameters, context, many,
    ):
        if deletion_locked.is_set() and "FROM projects" in statement and "FOR UPDATE" in statement:
            pid = connection.connection.driver_connection.get_backend_pid()
            if pid != pids["deletion"]:
                pids["update"] = pid
                update_lock_started.set()

    def delete_editor():
        with TestClient(app, base_url="https://testserver") as requester:
            if deletion_route == "admin":
                return requester.delete(
                    f"/api/users/{editor.id}",
                    headers=auth_headers(admin),
                )
            return requester.request(
                "DELETE",
                "/api/gdpr/account",
                headers=editor_headers,
                json={"confirm": True},
            )

    def update_task():
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.put(
                f"/api/tasks/{task_id}", headers=editor_headers,
                json={"status": "done"},
            )

    event.listen(database, "after_cursor_execute", pause_deletion_project_lock)
    event.listen(database, "before_cursor_execute", observe_task_project_lock)
    blocked = False
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            deletion = executor.submit(delete_editor)
            try:
                assert deletion_locked.wait(10), "Deletion never locked the member project"
                update = executor.submit(update_task)
                assert update_lock_started.wait(10), "Task update never requested the project lock"
                assert pids["deletion"] != pids["update"]
                with database.connect() as observer:
                    deadline = monotonic() + 5
                    while monotonic() < deadline:
                        blocked = observer.scalar(
                            text("SELECT :deletion = ANY(pg_blocking_pids(:update))"),
                            pids,
                        )
                        if blocked or update.done():
                            break
                        release_deletion.wait(0.01)
            finally:
                release_deletion.set()
            deleted = deletion.result(timeout=10)
            updated = update.result(timeout=10)
    finally:
        release_deletion.set()
        event.remove(database, "after_cursor_execute", pause_deletion_project_lock)
        event.remove(database, "before_cursor_execute", observe_task_project_lock)

    assert blocked, "Task update bypassed the in-flight user deletion"
    assert deleted.status_code == 200, deleted.text
    assert updated.status_code == 404, updated.text
    db_session.expire_all()
    assert db_session.get(User, editor.id) is None
    task = db_session.get(Task, task_id)
    assert task.status == TaskStatus.TODO
    assert task.assignee_id is None
    assert db_session.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == editor.id,
    )) is None
    assert app.dependency_overrides == {}


def test_gdpr_transfer_blocks_successor_removing_own_membership(
    client, database, db_session, user_factory, auth_headers,
):
    assert database.dialect.name == "postgresql"
    assert app.dependency_overrides == {}
    owner = user_factory()
    successor = user_factory()
    owner_headers = auth_headers(owner)
    successor_headers = auth_headers(successor)
    created = client.post(
        "/api/projects", headers=owner_headers, json={"name": "Concurrent transfer"},
    )
    assert created.status_code == 201, created.text
    project_id = UUID(created.json()["data"]["project"]["id"])
    invited = client.post(
        f"/api/projects/{project_id}/members", headers=owner_headers,
        json={"user_id": str(successor.id), "role": "owner"},
    )
    assert invited.status_code == 201, invited.text

    successor_selected = Event()
    removal_started = Event()
    release_transfer = Event()
    pids = {}

    def pause_after_successor_query(connection, cursor, statement, parameters, context, many):
        if (
            not successor_selected.is_set()
            and statement.lstrip().startswith("SELECT")
            and "FROM project_members" in statement
            and "project_members.user_id !=" in statement
        ):
            # Pause after PostgreSQL has selected B, before GDPR can transfer or
            # delete anything. B already has OWNER role, so no role UPDATE saves us.
            pids["gdpr"] = connection.connection.driver_connection.get_backend_pid()
            successor_selected.set()
            assert release_transfer.wait(15), "Timed out releasing GDPR transfer"

    def observe_removal_query(connection, cursor, statement, parameters, context, many):
        if successor_selected.is_set() and "FROM projects" in statement and "FOR UPDATE" in statement:
            pids["removal"] = connection.connection.driver_connection.get_backend_pid()
            removal_started.set()

    def delete_account():
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.request(
                "DELETE", "/api/gdpr/account",
                headers=owner_headers, json={"confirm": True},
            )

    def remove_self():
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.delete(
                f"/api/projects/{project_id}/members/{successor.id}",
                headers=successor_headers,
            )

    event.listen(database, "after_cursor_execute", pause_after_successor_query)
    event.listen(database, "before_cursor_execute", observe_removal_query)
    blocked = False
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            transfer = executor.submit(delete_account)
            try:
                assert successor_selected.wait(10), "GDPR never selected its successor"
                removal = executor.submit(remove_self)
                assert removal_started.wait(10), "Member removal never reached its project lock"
                assert pids["gdpr"] != pids["removal"]
                # Observe an actual PostgreSQL lock wait, not just a slow thread.
                with database.connect() as observer:
                    deadline = monotonic() + 5
                    while monotonic() < deadline:
                        blocked = observer.scalar(text(
                            "SELECT :gdpr = ANY(pg_blocking_pids(:removal))"
                        ), pids)
                        if blocked or removal.done():
                            break
                        release_transfer.wait(0.01)
            finally:
                release_transfer.set()
            transferred = transfer.result(timeout=10)
            removed = removal.result(timeout=10)
    finally:
        release_transfer.set()
        event.remove(database, "after_cursor_execute", pause_after_successor_query)
        event.remove(database, "before_cursor_execute", observe_removal_query)

    assert blocked, "Member removal bypassed the in-flight GDPR ownership transfer"
    assert transferred.status_code == 200, transferred.text
    assert removed.status_code == 400, removed.text
    assert "dernier owner" in removed.json()["error"]
    assert db_session.get(User, owner.id) is None
    assert db_session.get(Project, project_id).owner_id == successor.id
    members = db_session.scalars(
        select(ProjectMember).where(ProjectMember.project_id == project_id)
    ).all()
    assert [(member.user_id, member.role) for member in members] == [
        (successor.id, ProjectRole.OWNER),
    ]
    visible = client.get(f"/api/projects/{project_id}", headers=successor_headers)
    assert visible.status_code == 200, visible.text
    assert app.dependency_overrides == {}


def test_editor_task_update_waits_for_membership_removal(
    client, database, db_session, user_factory, auth_headers,
):
    assert database.dialect.name == "postgresql"
    assert app.dependency_overrides == {}
    owner = user_factory()
    editor = user_factory()
    owner_headers = auth_headers(owner)
    editor_headers = auth_headers(editor)
    created = client.post(
        "/api/projects", headers=owner_headers, json={"name": "Serialized writes"},
    )
    assert created.status_code == 201, created.text
    project_id = UUID(created.json()["data"]["project"]["id"])
    invited = client.post(
        f"/api/projects/{project_id}/members", headers=owner_headers,
        json={"user_id": str(editor.id), "role": "editor"},
    )
    assert invited.status_code == 201, invited.text
    task_response = client.post(
        f"/api/projects/{project_id}/tasks", headers=owner_headers,
        json={"title": "Must remain todo"},
    )
    assert task_response.status_code == 201, task_response.text
    task_id = UUID(task_response.json()["data"]["task"]["id"])

    removal_locked = Event()
    update_lock_started = Event()
    release_removal = Event()
    pids = {}

    def pause_first_project_lock(connection, cursor, statement, parameters, context, many):
        if not removal_locked.is_set() and "FROM projects" in statement and "FOR UPDATE" in statement:
            pids["removal"] = connection.connection.driver_connection.get_backend_pid()
            removal_locked.set()
            assert release_removal.wait(15), "Timed out releasing membership removal"

    def observe_second_project_lock(connection, cursor, statement, parameters, context, many):
        if removal_locked.is_set() and "FROM projects" in statement and "FOR UPDATE" in statement:
            pid = connection.connection.driver_connection.get_backend_pid()
            if pid != pids["removal"]:
                pids["update"] = pid
                update_lock_started.set()

    def remove_editor():
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.delete(
                f"/api/projects/{project_id}/members/{editor.id}",
                headers=owner_headers,
            )

    def update_task():
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.put(
                f"/api/tasks/{task_id}", headers=editor_headers,
                json={"status": "done"},
            )

    event.listen(database, "after_cursor_execute", pause_first_project_lock)
    event.listen(database, "before_cursor_execute", observe_second_project_lock)
    blocked = False
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            removal = executor.submit(remove_editor)
            try:
                assert removal_locked.wait(10), "Removal never locked its project"
                update = executor.submit(update_task)
                assert update_lock_started.wait(10), "Task update never requested the project lock"
                with database.connect() as observer:
                    deadline = monotonic() + 5
                    while monotonic() < deadline:
                        blocked = observer.scalar(text(
                            "SELECT :removal = ANY(pg_blocking_pids(:update))"
                        ), pids)
                        if blocked or update.done():
                            break
                        release_removal.wait(0.01)
            finally:
                release_removal.set()
            removed = removal.result(timeout=10)
            updated = update.result(timeout=10)
    finally:
        release_removal.set()
        event.remove(database, "after_cursor_execute", pause_first_project_lock)
        event.remove(database, "before_cursor_execute", observe_second_project_lock)

    assert blocked, "Task update did not serialize behind membership removal"
    assert removed.status_code == 200, removed.text
    assert updated.status_code == 404, updated.text
    db_session.expire_all()
    assert db_session.get(Task, task_id).status == TaskStatus.TODO
    assert db_session.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == editor.id,
    )) is None
    assert app.dependency_overrides == {}
