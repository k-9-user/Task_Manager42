from sqlalchemy import select

from app.database import SessionLocal
from app.models.user import User


def test_register_then_log_in_by_email_or_username(client, signup, password):
    user, headers = signup()

    for identifier in (user["email"], user["username"]):
        response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
        assert response.status_code == 200
        assert response.json()["data"]["token"]

    me = client.get("/api/users/me", headers=headers)
    assert me.json()["data"]["user"]["username"] == user["username"]


def test_login_refuses_a_wrong_password(client, signup, password):
    user, _ = signup()

    response = client.post(
        "/api/auth/login", json={"identifier": user["email"], "password": password + "x"}
    )

    assert response.status_code == 401
    assert response.json() == {"success": False, "error": "Invalid email, username or password"}


def test_passwords_are_stored_as_salted_argon2_hashes(signup, password):
    user, _ = signup()

    with SessionLocal() as db:
        stored = db.scalar(select(User.password_hash).where(User.id == user["id"]))

    assert stored.startswith("$argon2id$")
    assert password not in stored


def test_server_side_validation_rejects_bad_input(client, password):
    bad_bodies = [
        {"email": "not-an-email", "username": "valid_name", "password": password},
        {"email": "valid@example.com", "username": "x", "password": password},
        {"email": "valid@example.com", "username": "bob'; DROP TABLE users;--", "password": password},
        {"email": "valid@example.com", "username": "valid_name", "password": "short"},
        {"email": "valid@example.com", "username": "valid_name", "password": password, "role": "admin"},
    ]

    for body in bad_bodies:
        response = client.post("/api/auth/register", json=body)
        assert response.status_code == 422, body
        assert response.json() == {"success": False, "error": "Invalid request"}
