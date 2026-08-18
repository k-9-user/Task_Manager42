"""
Tests pour le module bonus notifications : les déclencheurs automatiques
dans routers/tasks.py + routers/projects.py, et routers/notifications.py.

Nécessite les fichiers de A (voir avertissement en tête de conftest.py) et
une vraie base Postgres de test.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.notification import Notification, NotificationType


def _create_project_via_api(client, name="Projet test"):
    response = client.post("/api/projects", json={"name": name, "description": None})
    assert response.status_code == 201, response.text
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Déclencheurs automatiques
# ---------------------------------------------------------------------------


def test_create_task_with_assignee_notifies(client, make_user, login_as):
    project = _create_project_via_api(client)
    member = make_user()
    client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(member.id), "role": "editor"},
    )

    client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache assignee", "assignee_id": str(member.id)},
    )

    login_as(member)
    response = client.get("/api/notifications")
    notifications = response.json()["data"]["notifications"]
    assert any(n["type"] == "task_assigned" for n in notifications)


def test_update_task_status_notifies_assignee(client, make_user, login_as):
    project = _create_project_via_api(client)
    member = make_user()
    client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(member.id), "role": "editor"},
    )
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache", "assignee_id": str(member.id)},
    ).json()["data"]["id"]

    client.put(f"/api/tasks/{task_id}", json={"status": "in_progress"})

    login_as(member)
    response = client.get("/api/notifications")
    types = [n["type"] for n in response.json()["data"]["notifications"]]
    assert "task_status_changed" in types


def test_reassign_task_notifies_new_assignee(client, make_user, login_as):
    project = _create_project_via_api(client)
    first = make_user()
    second = make_user()
    for user in (first, second):
        client.post(
            f"/api/projects/{project['id']}/members",
            json={"user_id": str(user.id), "role": "editor"},
        )
    task_id = client.post(
        f"/api/projects/{project['id']}/tasks",
        json={"title": "Tache", "assignee_id": str(first.id)},
    ).json()["data"]["id"]

    client.put(f"/api/tasks/{task_id}", json={"assignee_id": str(second.id)})

    login_as(second)
    response = client.get("/api/notifications")
    assert any(
        n["type"] == "task_assigned" for n in response.json()["data"]["notifications"]
    )


def test_add_member_notifies_project_invite(client, make_user, login_as):
    project = _create_project_via_api(client)
    new_member = make_user()

    client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(new_member.id), "role": "viewer"},
    )

    login_as(new_member)
    response = client.get("/api/notifications")
    types = [n["type"] for n in response.json()["data"]["notifications"]]
    assert "project_invite" in types


# ---------------------------------------------------------------------------
# GET /api/notifications
# ---------------------------------------------------------------------------


def test_list_notifications_only_mine(client, make_user, db_session):
    other = make_user()
    db_session.add(
        Notification(
            user_id=other.id,
            type=NotificationType.PROJECT_INVITE,
            content="Pas pour moi",
        )
    )
    db_session.commit()

    response = client.get("/api/notifications")
    assert response.json()["data"]["notifications"] == []


def test_list_notifications_unread_only(client, db_session):
    db_session.add_all(
        [
            Notification(
                user_id=client.current_user.id,
                type=NotificationType.PROJECT_INVITE,
                content="Lue",
                read=True,
            ),
            Notification(
                user_id=client.current_user.id,
                type=NotificationType.PROJECT_INVITE,
                content="Non lue",
                read=False,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/notifications", params={"unread_only": True})
    contents = [n["content"] for n in response.json()["data"]["notifications"]]
    assert contents == ["Non lue"]


# ---------------------------------------------------------------------------
# PUT /api/notifications/{id}/read
# ---------------------------------------------------------------------------


def test_mark_notification_read(client, db_session):
    notification = Notification(
        user_id=client.current_user.id,
        type=NotificationType.PROJECT_INVITE,
        content="A lire",
        read=False,
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    response = client.put(f"/api/notifications/{notification.id}/read")

    assert response.status_code == 200
    assert response.json()["data"]["read"] is True


def test_mark_notification_read_not_mine(client, make_user, db_session):
    other = make_user()
    notification = Notification(
        user_id=other.id, type=NotificationType.PROJECT_INVITE, content="Pas pour moi"
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)

    response = client.put(f"/api/notifications/{notification.id}/read")
    assert response.status_code == 404


def test_mark_notification_read_unknown_id(client):
    response = client.put(f"/api/notifications/{uuid.uuid4()}/read")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /api/notifications/read-all
# ---------------------------------------------------------------------------


def test_mark_all_read(client, db_session):
    db_session.add_all(
        [
            Notification(
                user_id=client.current_user.id,
                type=NotificationType.PROJECT_INVITE,
                content="Une",
                read=False,
            ),
            Notification(
                user_id=client.current_user.id,
                type=NotificationType.PROJECT_INVITE,
                content="Deux",
                read=False,
            ),
        ]
    )
    db_session.commit()

    response = client.put("/api/notifications/read-all")
    assert response.status_code == 200
    assert response.json() == {"success": True}

    remaining_unread = client.get(
        "/api/notifications", params={"unread_only": True}
    ).json()["data"]["notifications"]
    assert remaining_unread == []


# ---------------------------------------------------------------------------
# Sécurité : échappement HTML + comptes inactifs
# ---------------------------------------------------------------------------


def test_notification_content_escapes_html(client, make_user, login_as):
    project = _create_project_via_api(client, name="<script>alert(1)</script>")
    member = make_user()

    client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(member.id), "role": "viewer"},
    )

    login_as(member)
    response = client.get("/api/notifications")
    content = response.json()["data"]["notifications"][0]["content"]

    assert "<script>" not in content
    assert "&lt;script&gt;" in content


def test_no_notification_for_inactive_account(client, make_user, db_session):
    project = _create_project_via_api(client)
    stale_member = make_user()
    db_session.query(type(stale_member)).filter(
        type(stale_member).id == stale_member.id
    ).update({"updated_at": datetime.now(timezone.utc) - timedelta(days=200)})
    db_session.commit()

    response = client.post(
        f"/api/projects/{project['id']}/members",
        json={"user_id": str(stale_member.id), "role": "viewer"},
    )
    assert response.status_code == 201

    count = (
        db_session.query(Notification)
        .filter(Notification.user_id == stale_member.id)
        .count()
    )
    assert count == 0
