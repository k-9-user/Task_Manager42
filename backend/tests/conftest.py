"""
Fixtures partagées pour les tests B (projects/tasks/gdpr).

⚠️ Ces tests ont besoin de `app.database` (Base, get_db), `app.models.user`
et `app.auth.dependencies.get_current_user`, livrés par Personne A — pas
encore présents dans ce dossier `backend/` sur cette branche (seulement dans
`Partie-A/` pour l'instant). Ils sont écrits pour tourner dès que ses
fichiers seront fusionnés ici, exactement comme les routers eux-mêmes.

Nécessite une vraie base Postgres : les modèles utilisent le type UUID
spécifique à Postgres (`sqlalchemy.dialects.postgresql.UUID`), incompatible
avec SQLite. Pointer `TEST_DATABASE_URL` vers une DB de test dédiée, jamais
la DB de dev — ce fichier crée/détruit tout le schéma dessus.

Pas de dépendance à `app/main.py` (pas encore livré / pas assigné) : on
construit ici une appli FastAPI de test minimale, avec seulement les routers
B (projects, tasks, gdpr) et le même exception handler `{success, error}`
que celui documenté pour le vrai `main.py`.
"""

import os
import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import get_current_user
from app.database import Base, get_db
from app.models.user import User
from app.routers import gdpr, notifications, projects, tasks

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://user:password@localhost:5432/taskmanager_test"
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False)


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(projects.router)
    test_app.include_router(tasks.router)
    test_app.include_router(gdpr.router)
    test_app.include_router(notifications.router)

    @test_app.exception_handler(HTTPException)
    async def _http_exception_handler(request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content={"success": False, "error": exc.detail}
        )

    return test_app


app = _build_test_app()


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session():
    """Une session par test, dans une transaction annulée à la fin — aucun
    test ne pollue les suivants, pas besoin de nettoyer la DB à la main.

    Le code testé (routers) appelle lui-même `db.commit()`/`db.rollback()`
    (ex: `add_member` sur IntegrityError) — un simple `connection.begin()`
    se retrouverait "déassocié" dès le premier commit interne. On utilise
    donc un SAVEPOINT (`begin_nested`) redémarré automatiquement à chaque
    fin de transaction interne, pattern standard SQLAlchemy pour ce cas."""

    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def make_user(db_session):
    """Factory : crée un vrai user en base (nécessaire pour les FK) et le renvoie."""

    def _make(email: str | None = None, username: str | None = None) -> User:
        suffix = uuid.uuid4().hex[:8]
        user = User(
            email=email or f"user-{suffix}@test.dev",
            username=username or f"user_{suffix}",
        )
        db_session.add(user)
        db_session.flush()
        return user

    return _make


@pytest.fixture
def client(db_session, make_user):
    """TestClient avec `get_db`/`get_current_user` substitués. Utilisateur
    connecté par défaut : un nouvel utilisateur de test, accessible via
    `client.current_user`. Change d'utilisateur avec la fixture `login_as`."""

    current_user = make_user()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = lambda: current_user

    test_client = TestClient(app)
    test_client.current_user = current_user
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def login_as(client):
    """Change l'utilisateur connecté en cours de test (ex: pour vérifier
    qu'un viewer se fait bien refuser une action)."""

    def _login_as(user: User) -> None:
        app.dependency_overrides[get_current_user] = lambda: user

    return _login_as
