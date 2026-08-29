from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import require_admin
from app.database import SessionLocal
from app.main import app
from app.models.user import User, UserRole


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

    assert role_change.status_code == 403
    assert deletion.status_code == 403
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
