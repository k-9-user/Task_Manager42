from uuid import uuid4

from alembic import command
from sqlalchemy import select, text

from app.auth.api_key_auth import hash_api_key
from app.models.api_key import ApiKey
from app.models.user import UserStatus


def test_lifecycle_routes_require_jwt(client):
    requests = (
        ("POST", "/api/api-keys"),
        ("GET", "/api/api-keys"),
        ("DELETE", "/api/api-keys/00000000-0000-0000-0000-000000000001"),
        ("POST", "/api/api-keys/00000000-0000-0000-0000-000000000001/rotate"),
    )
    for method, path in requests:
        assert client.request(method, path).status_code == 401


def test_banned_user_cannot_manage_api_keys(
    client, db_session, user_factory, auth_headers,
):
    user = user_factory(status=UserStatus.BANNED)
    api_key = ApiKey(user_id=user.id, key_hash=hash_api_key("banned-user-key"))
    db_session.add(api_key)
    db_session.commit()
    db_session.refresh(api_key)

    assert client.post("/api/api-keys", headers=auth_headers(user)).status_code == 403
    assert client.get("/api/api-keys", headers=auth_headers(user)).status_code == 403
    assert client.delete(
        f"/api/api-keys/{api_key.id}", headers=auth_headers(user),
    ).status_code == 403
    assert client.post(
        f"/api/api-keys/{api_key.id}/rotate", headers=auth_headers(user),
    ).status_code == 403
    db_session.expire_all()
    assert db_session.get(ApiKey, api_key.id) is not None


def test_issue_lists_metadata_and_authenticates_raw_key(
    client, db_session, user_factory, auth_headers,
):
    user = user_factory()

    issued = client.post("/api/api-keys", headers=auth_headers(user))

    assert issued.status_code == 201
    payload = issued.json()["data"]["api_key"]
    assert payload["key"]
    stored = db_session.scalar(select(ApiKey).where(ApiKey.id == payload["id"]))
    assert stored.user_id == user.id
    assert stored.key_hash != payload["key"]
    assert payload["key"] not in stored.key_hash

    listed = client.get("/api/api-keys", headers=auth_headers(user))
    assert listed.status_code == 200
    assert listed.json()["data"] == {
        "api_keys": [{"id": payload["id"], "created_at": payload["created_at"]}]
    }
    assert "key_hash" not in listed.text
    assert '"key"' not in listed.text
    assert client.get(
        "/api/v1/public/projects",
        headers={"X-API-Key": payload["key"]},
    ).status_code == 200


def test_key_owner_is_hidden_from_other_users(client, user_factory, auth_headers):
    owner = user_factory()
    stranger = user_factory()
    issued = client.post("/api/api-keys", headers=auth_headers(owner)).json()["data"]["api_key"]

    assert client.delete(
        f"/api/api-keys/{issued['id']}", headers=auth_headers(stranger),
    ).status_code == 404
    assert client.post(
        f"/api/api-keys/{issued['id']}/rotate", headers=auth_headers(stranger),
    ).status_code == 404


def test_rotate_atomically_replaces_key(client, user_factory, auth_headers):
    user = user_factory()
    old = client.post("/api/api-keys", headers=auth_headers(user)).json()["data"]["api_key"]

    response = client.post(
        f"/api/api-keys/{old['id']}/rotate", headers=auth_headers(user),
    )

    assert response.status_code == 200
    new = response.json()["data"]["api_key"]
    assert new["id"] != old["id"]
    assert new["key"] != old["key"]
    assert client.get(
        "/api/v1/public/projects", headers={"X-API-Key": old["key"]},
    ).status_code == 401
    assert client.get(
        "/api/v1/public/projects", headers={"X-API-Key": new["key"]},
    ).status_code == 200


def test_revoke_invalidates_key(client, user_factory, auth_headers):
    user = user_factory()
    issued = client.post("/api/api-keys", headers=auth_headers(user)).json()["data"]["api_key"]

    response = client.delete(
        f"/api/api-keys/{issued['id']}", headers=auth_headers(user),
    )

    assert response.status_code == 200
    assert response.json() == {"success": True, "data": {}}
    assert client.get(
        "/api/v1/public/projects", headers={"X-API-Key": issued["key"]},
    ).status_code == 401


def test_migration_hashes_existing_plaintext_keys(database_engine, alembic_config):
    user_id = uuid4()
    key_id = uuid4()
    raw_key = "legacy-plaintext-api-key"
    try:
        command.downgrade(alembic_config, "add_banner_comments")
        with database_engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO users (id, email, username, password_hash) "
                "VALUES (:id, :email, :username, :password_hash)"
            ), {
                "id": user_id,
                "email": "legacy-key@example.com",
                "username": "legacy_key_user",
                "password_hash": "$argon2id$legacy-placeholder",
            })
            connection.execute(text(
                "INSERT INTO api_keys (id, user_id, key) VALUES (:id, :user_id, :key)"
            ), {"id": key_id, "user_id": user_id, "key": raw_key})

        command.upgrade(alembic_config, "head")
        with database_engine.connect() as connection:
            stored = connection.execute(
                text("SELECT key_hash FROM api_keys WHERE id = :id"),
                {"id": key_id},
            ).scalar_one()
        assert stored == hash_api_key(raw_key)

        command.downgrade(alembic_config, "add_banner_comments")
        with database_engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM api_keys")).scalar_one() == 0
    finally:
        command.upgrade(alembic_config, "head")
