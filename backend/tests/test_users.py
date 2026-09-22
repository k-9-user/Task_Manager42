from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.dependencies import require_admin
from app.database import SessionLocal
from app.main import app
from app.models.user import User, UserRole, UserStatus


def test_users_list_enforces_admin_access_and_bounded_pagination(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    regular_user = user_factory()
    admin = user_factory(role=UserRole.ADMIN)
    user_factory(oauth_id="pagination-subject-1")
    user_factory(oauth_id="pagination-subject-2")

    anonymous = client.get("/api/users")
    non_admin = client.get("/api/users", headers=auth_headers(regular_user))
    default_page = client.get("/api/users", headers=auth_headers(admin))
    limited_page = client.get(
        "/api/users?page=1&limit=2",
        headers=auth_headers(admin),
    )
    oversized_page = client.get(
        "/api/users?limit=101",
        headers=auth_headers(admin),
    )

    assert anonymous.status_code == 401
    assert non_admin.status_code == 403
    assert default_page.status_code == 200
    assert default_page.json()["data"]["total"] == 4
    assert len(default_page.json()["data"]["users"]) == 4
    assert len(limited_page.json()["data"]["users"]) == 2
    assert oversized_page.status_code == 422


def test_regular_user_cannot_change_roles_or_delete_users(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    regular_user = user_factory()
    target = user_factory()
    headers = auth_headers(regular_user)

    role_change = client.put(
        f"/api/users/{target.id}/role",
        headers=headers,
        json={"role": "admin"},
    )
    deletion = client.delete(
        f"/api/users/{target.id}",
        headers=headers,
    )
    rename = client.put(
        f"/api/users/{target.id}",
        headers=headers,
        json={"display_name": "Nope"},
    )
    ban = client.put(
        f"/api/users/{target.id}/status",
        headers=headers,
        json={"status": "banned"},
    )

    assert role_change.status_code == 403
    assert deletion.status_code == 403
    assert rename.status_code == 403
    assert ban.status_code == 403
    with SessionLocal() as session:
        persisted_target = session.get(User, target.id)
        assert persisted_target is not None
        assert persisted_target.role == UserRole.USER


def test_admin_can_promote_and_demote_another_user(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)
    target = user_factory()

    promoted = client.put(
        f"/api/users/{target.id}/role",
        headers=auth_headers(admin),
        json={"role": "admin"},
    )
    demoted = client.put(
        f"/api/users/{target.id}/role",
        headers=auth_headers(admin),
        json={"role": "user"},
    )

    assert promoted.status_code == 200
    assert promoted.json()["data"]["user"]["role"] == "admin"
    assert demoted.status_code == 200
    assert demoted.json()["data"]["user"]["role"] == "user"


def test_sole_admin_cannot_demote_themselves(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)

    response = client.put(
        f"/api/users/{admin.id}/role",
        headers=auth_headers(admin),
        json={"role": "user"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "At least one administrator is required"


def test_sole_admin_cannot_delete_themselves(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)

    response = client.delete(
        f"/api/users/{admin.id}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 409
    assert response.json()["error"] == "At least one administrator is required"
    with SessionLocal() as session:
        assert session.get(User, admin.id) is not None


def test_admin_can_demote_themselves_when_another_admin_remains(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    actor = user_factory(role=UserRole.ADMIN)
    user_factory(role=UserRole.ADMIN)

    response = client.put(
        f"/api/users/{actor.id}/role",
        headers=auth_headers(actor),
        json={"role": "user"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["role"] == "user"


def test_admin_can_delete_themselves_when_another_admin_remains(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    actor = user_factory(role=UserRole.ADMIN)
    user_factory(role=UserRole.ADMIN)

    response = client.delete(
        f"/api/users/{actor.id}",
        headers=auth_headers(actor),
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {}}
    with SessionLocal() as session:
        assert session.get(User, actor.id) is None


def test_admin_can_delete_a_user_and_missing_target_returns_404(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)
    target = user_factory()

    response = client.delete(
        f"/api/users/{target.id}",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {}}
    missing = client.delete(
        f"/api/users/{uuid4()}",
        headers=auth_headers(admin),
    )

    assert missing.status_code == 404


def test_admin_is_revalidated_after_the_invariant_lock(
    client: TestClient,
    user_factory: Any,
) -> None:
    stale_admin = user_factory(role=UserRole.ADMIN)
    target = user_factory()
    with SessionLocal() as session:
        actor = session.scalar(select(User).where(User.id == stale_admin.id))
        assert actor is not None
        actor.role = UserRole.USER
        session.commit()

    app.dependency_overrides[require_admin] = lambda: stale_admin
    response = client.delete(f"/api/users/{target.id}")

    assert response.status_code == 403
    with SessionLocal() as session:
        assert session.get(User, target.id) is not None


def test_admin_can_rename_another_user(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)
    target = user_factory()

    response = client.put(
        f"/api/users/{target.id}",
        headers=auth_headers(admin),
        json={"username": "admin_renamed", "display_name": "Admin Renamed"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["user"]["username"] == "admin_renamed"
    assert response.json()["data"]["user"]["display_name"] == "Admin Renamed"


def test_admin_can_ban_and_unban_user_with_immediate_token_effect(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)
    target = user_factory()
    target_headers = auth_headers(target)

    banned = client.put(
        f"/api/users/{target.id}/status",
        headers=auth_headers(admin),
        json={"status": "banned", "reason": "abuse report"},
    )
    denied = client.get("/api/users/me", headers=target_headers)
    unbanned = client.put(
        f"/api/users/{target.id}/status",
        headers=auth_headers(admin),
        json={"status": "active"},
    )
    restored = client.get("/api/users/me", headers=target_headers)

    assert banned.status_code == 200
    assert banned.json()["data"]["user"]["status"] == "banned"
    assert denied.status_code == 403
    assert unbanned.status_code == 200
    assert unbanned.json()["data"]["user"]["status"] == "active"
    assert restored.status_code == 200


def test_sole_active_admin_cannot_be_banned(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    active_admin = user_factory(role=UserRole.ADMIN)
    user_factory(role=UserRole.ADMIN, status=UserStatus.BANNED)

    response = client.put(
        f"/api/users/{active_admin.id}/status",
        headers=auth_headers(active_admin),
        json={"status": "banned"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "At least one active administrator is required"


def test_concurrent_admin_bans_preserve_one_active_admin(
    database: object,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    first = user_factory(role=UserRole.ADMIN)
    second = user_factory(role=UserRole.ADMIN)
    barrier = Barrier(2)

    def ban(actor: User, target: User) -> int:
        barrier.wait()
        with TestClient(app, base_url="https://testserver") as test_client:
            response = test_client.put(
                f"/api/users/{target.id}/status",
                headers=auth_headers(actor),
                json={"status": "banned"},
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(
            executor.map(
                lambda pair: ban(*pair),
                ((first, second), (second, first)),
            )
        )

    with SessionLocal() as session:
        active_admins = session.scalar(
            select(func.count()).select_from(User).where(
                User.role == UserRole.ADMIN,
                User.status == UserStatus.ACTIVE,
            )
        )

    assert sorted(statuses) == [200, 403]
    assert active_admins == 1


def test_admin_rename_conflicts_are_reported_and_case_insensitive(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN, username="admin_actor")
    target = user_factory(username="target_user")
    user_factory(username="taken_name")
    headers = auth_headers(admin)

    conflict = client.put(
        f"/api/users/{target.id}",
        headers=headers,
        json={"username": "taken_name"},
    )
    shadowing = client.put(
        f"/api/users/{target.id}",
        headers=headers,
        json={"username": "Taken_Name"},
    )
    accepted = client.put(
        f"/api/users/{target.id}",
        headers=headers,
        json={"username": "Renamed_Target"},
    )

    assert conflict.status_code == 409
    assert conflict.json()["error"] == "Username already taken"
    assert shadowing.status_code == 409
    assert accepted.status_code == 200
    assert accepted.json()["data"]["user"]["username"] == "Renamed_Target"


def test_user_list_pages_newest_first_without_gaps_or_repeats(
    client: TestClient,
    user_factory: Any,
    auth_headers: Any,
) -> None:
    admin = user_factory(role=UserRole.ADMIN)
    for index in range(6):
        user_factory(username=f"paged_user_{index}")
    headers = auth_headers(admin)

    first_page = client.get("/api/users?page=1&limit=3", headers=headers)
    second_page = client.get("/api/users?page=2&limit=3", headers=headers)
    third_page = client.get("/api/users?page=3&limit=3", headers=headers)
    past_the_end = client.get("/api/users?page=4&limit=3", headers=headers)
    rejected = client.get("/api/users?page=0", headers=headers)
    overflowing = client.get("/api/users?page=99999999999999", headers=headers)

    # 1 admin + 6 members = 7 rows, so limit=3 gives pages of 3, 3, 1 and then 0.
    assert first_page.status_code == 200
    for page in (first_page, second_page, third_page, past_the_end):
        assert page.json()["data"]["total"] == 7
    assert len(first_page.json()["data"]["users"]) == 3
    assert len(second_page.json()["data"]["users"]) == 3
    assert len(third_page.json()["data"]["users"]) == 1
    assert past_the_end.json()["data"]["users"] == []

    collected = [
        user["id"]
        for page in (first_page, second_page, third_page, past_the_end)
        for user in page.json()["data"]["users"]
    ]
    assert len(collected) == len(set(collected)) == 7

    created = [
        user["created_at"]
        for page in (first_page, second_page, third_page, past_the_end)
        for user in page.json()["data"]["users"]
    ]
    assert created == sorted(created, reverse=True)

    assert rejected.status_code == 422
    assert overflowing.status_code == 422
