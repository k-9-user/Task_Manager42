from sqlalchemy import update

from app.database import SessionLocal
from app.models.user import User, UserRole


def _make_only_admin(user):
    with SessionLocal() as db:
        db.execute(update(User).values(role=UserRole.USER))
        db.execute(update(User).where(User.id == user["id"]).values(role=UserRole.ADMIN))
        db.commit()


def test_admin_routes_need_the_admin_role(client, signup):
    _, user_headers = signup()
    admin, admin_headers = signup()
    _make_only_admin(admin)

    assert client.get("/api/users", headers=user_headers).status_code == 403
    assert client.get("/api/users", headers=admin_headers).status_code == 200


def test_the_last_active_admin_cannot_be_demoted_or_banned(client, signup):
    admin, headers = signup()
    _make_only_admin(admin)

    demote = client.put(f"/api/users/{admin['id']}/role", headers=headers, json={"role": "user"})
    ban = client.put(f"/api/users/{admin['id']}/status", headers=headers, json={"status": "banned"})

    assert demote.status_code == ban.status_code == 409
