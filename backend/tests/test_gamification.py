"""Gamification: catalog rules, activity ledger, awards and progress API."""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.main import app
from app.routers import gdpr as gdpr_router
from app.models.user_achievement import UserAchievement
from app.models.user_activity import UserActivity
from app.models.user_badge import UserBadge
from app.services.gamification.catalog import (
    ACHIEVEMENTS,
    BADGES,
    LEVEL_XP,
    MAX_LEVEL,
    TIER_XP,
    TRACK_THRESHOLDS,
    Track,
    badge_for,
    level_for,
    xp_for_level,
)

from tests.conftest import member_client as client


def test_level_curve_is_exponential():
    assert [level_for(xp) for xp in (0, 49, 50, 210, 211, 41625, 41626, 10**7)] == [
        1, 1, 2, 4, 5, 99, 100, MAX_LEVEL,
    ]
    assert [xp_for_level(level) for level in (2, 5, 10, 25, 50, 100)] == [
        50, 211, 518, 1834, 6281, 41626,
    ]
    steps = [later - earlier for earlier, later in zip(LEVEL_XP, LEVEL_XP[1:])]
    assert steps[0] == 50
    assert all(later >= earlier for earlier, later in zip(steps, steps[1:]))


def test_badges_follow_levels():
    assert [badge.level for badge in BADGES] == [5, 10, 25, 50, 100]
    assert badge_for(4) is None
    assert badge_for(5) == "planner"
    assert badge_for(24) == "organizer"
    assert badge_for(50) == "strategist"
    assert badge_for(MAX_LEVEL) == "grandmaster"


def test_catalog_is_consistent_and_max_level_is_reachable():
    keys = [achievement.key for achievement in ACHIEVEMENTS]
    assert len(keys) == len(set(keys)) == 36
    assert set(TRACK_THRESHOLDS) == set(Track)
    assert all(later == 3 * earlier for earlier, later in zip(TIER_XP, TIER_XP[1:]))
    assert TIER_XP[0] < xp_for_level(2)
    assert len(Track) * TIER_XP[0] >= xp_for_level(5)
    for thresholds in TRACK_THRESHOLDS.values():
        assert list(thresholds) == sorted(set(thresholds))
        assert len(thresholds) <= len(TIER_XP)
    assert sum(achievement.xp for achievement in ACHIEVEMENTS) >= xp_for_level(MAX_LEVEL)


def _project(client, name="Gamified project"):
    response = client.post("/api/projects", json={"name": name, "description": None})
    assert response.status_code == 201, response.text
    return response.json()["data"]["project"]["id"]


def _task(client, project_id, title="Gamified task"):
    response = client.post(f"/api/projects/{project_id}/tasks", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()["data"]["task"]["id"]


def _comment(client, task_id, content="Nice work"):
    response = client.post(f"/api/tasks/{task_id}/comments", json={"content": content})
    assert response.status_code == 201, response.text
    return response.json()["data"]["comment"]["id"]


def _set_status(client, task_id, status):
    response = client.put(f"/api/tasks/{task_id}", json={"status": status})
    assert response.status_code == 200, response.text


def _counts(db_session, user_id):
    rows = db_session.execute(
        select(UserActivity.track, func.count())
        .where(UserActivity.user_id == user_id)
        .group_by(UserActivity.track)
    ).all()
    return dict(rows)


def _unlocked(db_session, user_id):
    return set(
        db_session.scalars(
            select(UserAchievement.achievement_key).where(UserAchievement.user_id == user_id)
        )
    )


def _badges(db_session, user_id):
    return set(
        db_session.scalars(select(UserBadge.badge_key).where(UserBadge.user_id == user_id))
    )


def test_first_actions_level_up_gradually(client, db_session):
    user_id = client.current_user.id
    project_id = _project(client)

    assert _unlocked(db_session, user_id) == {"projects_1"}
    assert _badges(db_session, user_id) == set()

    task_id = _task(client, project_id)
    _set_status(client, task_id, "done")

    assert _unlocked(db_session, user_id) == {
        "projects_1",
        "tasks_created_1",
        "tasks_completed_1",
    }
    assert _badges(db_session, user_id) == set()


def test_every_hooked_action_records_its_track(client, make_user, db_session):
    user_id = client.current_user.id
    project_id = _project(client)
    task_id = _task(client, project_id)
    _set_status(client, task_id, "done")
    _comment(client, task_id)
    message = client.post(f"/api/projects/{project_id}/messages", json={"content": "Hi team"})
    upload = client.post(
        f"/api/tasks/{task_id}/attachments",
        files={"file": ("notes.pdf", b"attachment content", "application/pdf")},
    )
    member = client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(make_user().id), "role": "viewer"},
    )

    assert message.status_code == 201, message.text
    assert upload.status_code == 200, upload.text
    assert member.status_code == 201, member.text
    assert _counts(db_session, user_id) == {
        "projects": 1,
        "tasks_created": 1,
        "tasks_completed": 1,
        "comments": 1,
        "messages": 1,
        "files": 1,
        "collaborators": 1,
    }
    assert len(_unlocked(db_session, user_id)) == 7
    assert _badges(db_session, user_id) == {"planner"}


def test_same_task_completed_again_counts_once(client, db_session):
    user_id = client.current_user.id
    task_id = _task(client, _project(client))

    _set_status(client, task_id, "done")
    _set_status(client, task_id, "todo")
    _set_status(client, task_id, "in_progress")
    _set_status(client, task_id, "done")

    assert _counts(db_session, user_id)["tasks_completed"] == 1
    assert db_session.scalar(
        select(func.count()).select_from(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_key == "tasks_completed_1",
        )
    ) == 1


def test_deleting_items_takes_nothing_back(client, db_session):
    user_id = client.current_user.id
    project_id = _project(client)
    task_id = _task(client, project_id)
    _set_status(client, task_id, "done")
    comment_id = _comment(client, task_id)
    before = (_counts(db_session, user_id), _unlocked(db_session, user_id), _badges(db_session, user_id))

    assert client.delete(f"/api/comments/{comment_id}").status_code == 200
    assert client.delete(f"/api/tasks/{task_id}").status_code == 200
    assert client.delete(f"/api/projects/{project_id}").status_code == 200

    assert (_counts(db_session, user_id), _unlocked(db_session, user_id), _badges(db_session, user_id)) == before


def test_same_collaborator_counts_once(client, make_user, db_session):
    user_id = client.current_user.id
    teammate = make_user()
    first_project = _project(client, "First")
    second_project = _project(client, "Second")

    for project_id in (first_project, second_project):
        response = client.post(
            f"/api/projects/{project_id}/members",
            json={"user_id": str(teammate.id), "role": "editor"},
        )
        assert response.status_code == 201, response.text
    removed = client.delete(f"/api/projects/{first_project}/members/{teammate.id}")

    assert removed.status_code == 200, removed.text
    assert _counts(db_session, user_id)["collaborators"] == 1


def test_refused_actions_record_nothing(client, make_user, login_as, db_session):
    project_id = _project(client)
    task_id = _task(client, project_id)
    viewer = make_user()
    client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(viewer.id), "role": "viewer"},
    )

    login_as(viewer)
    refused = client.post(f"/api/projects/{project_id}/tasks", json={"title": "Nope"})
    invalid = client.post(f"/api/tasks/{task_id}/comments", json={"content": ""})

    assert refused.status_code == 403
    assert invalid.status_code == 422
    assert _counts(db_session, viewer.id) == {}
    assert _unlocked(db_session, viewer.id) == set()


def test_imported_tasks_do_not_count(client, db_session):
    user_id = client.current_user.id
    project_id = _project(client)
    payload = {
        "projects": [
            {
                "id": project_id,
                "name": "Gamified project",
                "tasks": [
                    {"project_id": project_id, "title": f"Imported {index}", "status": "done"}
                    for index in range(12)
                ],
            }
        ]
    }

    response = client.post(
        "/api/import",
        files={"file": ("tasks.json", json.dumps(payload).encode(), "application/json")},
    )

    assert response.status_code == 200, response.text
    assert _counts(db_session, user_id) == {"projects": 1}


def test_concurrent_actions_award_threshold_once(client, database, db_session):
    user_id = client.current_user.id
    task_id = _task(client, _project(client))
    for index in range(9):
        _comment(client, task_id, f"Warm-up {index}")

    first_locked = Event()
    second_waiting = Event()
    release_first = Event()
    pids = {}

    def hold_first_lock(connection, cursor, statement, parameters, context, many):
        if not first_locked.is_set() and "pg_advisory_xact_lock" in statement:
            pids["first"] = connection.connection.driver_connection.get_backend_pid()
            first_locked.set()
            assert release_first.wait(15), "Timed out releasing first request"

    def observe_second_lock(connection, cursor, statement, parameters, context, many):
        if first_locked.is_set() and "pg_advisory_xact_lock" in statement:
            if connection.connection.driver_connection.get_backend_pid() != pids["first"]:
                second_waiting.set()

    def post_comment(content):
        with TestClient(app, base_url="https://testserver") as requester:
            return requester.post(f"/api/tasks/{task_id}/comments", json={"content": content})

    event.listen(database, "after_cursor_execute", hold_first_lock)
    event.listen(database, "before_cursor_execute", observe_second_lock)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(post_comment, "Tenth")
            assert first_locked.wait(15)
            second = executor.submit(post_comment, "Eleventh")
            assert second_waiting.wait(15)
            release_first.set()
            responses = [first.result(timeout=15), second.result(timeout=15)]
    finally:
        release_first.set()
        event.remove(database, "after_cursor_execute", hold_first_lock)
        event.remove(database, "before_cursor_execute", observe_second_lock)

    assert [response.status_code for response in responses] == [201, 201]
    assert _counts(db_session, user_id)["comments"] == 11
    assert db_session.scalar(
        select(func.count()).select_from(UserAchievement).where(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_key == "comments_10",
        )
    ) == 1


def test_progress_requires_authentication(database):
    with TestClient(app, base_url="https://testserver") as anonymous:
        response = anonymous.get("/api/gamification/me")

    assert response.status_code == 401


def test_progress_summary_for_new_user(client):
    response = client.get("/api/gamification/me")

    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["progress"] == {
        "xp": 0, "level": 1, "level_xp": 0, "next_level_xp": 50, "badge": None,
    }
    assert [badge["key"] for badge in data["badges"]] == [badge.key for badge in BADGES]
    assert all(badge["awarded_at"] is None for badge in data["badges"])
    assert [track["key"] for track in data["tracks"]] == [track.value for track in Track]
    assert sum(len(track["achievements"]) for track in data["tracks"]) == len(ACHIEVEMENTS)


def test_progress_summary_after_actions(client):
    task_id = _task(client, _project(client))
    _set_status(client, task_id, "done")

    data = client.get("/api/gamification/me").json()["data"]
    tracks = {track["key"]: track for track in data["tracks"]}

    assert data["progress"] == {
        "xp": 105, "level": 3, "level_xp": 102, "next_level_xp": 156, "badge": None,
    }
    assert tracks["projects"]["count"] == 1
    assert tracks["projects"]["achievements"][0]["unlocked_at"] is not None
    assert tracks["projects"]["achievements"][1]["unlocked_at"] is None
    assert [badge["key"] for badge in data["badges"] if badge["awarded_at"]] == []


def test_members_show_level_and_badge(client, make_user):
    project_id = _project(client)
    teammate = make_user()
    added = client.post(
        f"/api/projects/{project_id}/members",
        json={"user_id": str(teammate.id), "role": "viewer"},
    )

    assert added.status_code == 201, added.text
    assert (added.json()["data"]["member"]["level"], added.json()["data"]["member"]["badge"]) == (1, None)
    members = {
        member["user_id"]: member
        for member in client.get(f"/api/projects/{project_id}").json()["data"]["members"]
    }
    owner = members[str(client.current_user.id)]
    assert (owner["level"], owner["badge"]) == (2, None)
    assert (members[str(teammate.id)]["level"], members[str(teammate.id)]["badge"]) == (1, None)


def test_gdpr_export_includes_progress(client, monkeypatch):
    monkeypatch.setattr(gdpr_router, "send_mail", lambda to, subject, body: None)
    _project(client)

    section = client.get("/api/gdpr/export").json()["gamification"]

    assert {key: section[key] for key in ("xp", "level", "activity")} == {
        "xp": 35, "level": 1, "activity": {"projects": 1},
    }
    assert "title" not in section and "badges" not in section
    assert [(item["achievement"], item["xp"]) for item in section["achievements"]] == [
        ("projects_1", 35)
    ]


def test_account_deletion_removes_progress(client, db_session, monkeypatch):
    monkeypatch.setattr(gdpr_router, "send_mail", lambda to, subject, body: None)
    user = client.current_user
    _project(client)

    response = client.request(
        "DELETE",
        "/api/gdpr/account",
        json={"confirm": True, "confirm_username": user.username},
    )

    assert response.status_code == 200, response.text
    assert _counts(db_session, user.id) == {}
    assert _unlocked(db_session, user.id) == set()
    assert _badges(db_session, user.id) == set()
