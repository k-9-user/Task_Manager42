from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_database_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_database_settings().database_url.get_secret_value(),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
