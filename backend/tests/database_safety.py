"""Allow destructive test setup only against the dedicated local test database."""

from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError


def validate_test_database_url(value: str | None) -> URL:
    message = (
        "TEST_DATABASE_URL must name taskmanager_test on test-db or loopback, "
        "with PostgreSQL credentials and no connection query overrides"
    )
    try:
        url = make_url(value or "")
        valid = (
            url.drivername in {"postgresql", "postgresql+psycopg2"}
            and url.host in {"test-db", "localhost", "127.0.0.1", "::1"}
            and url.database == "taskmanager_test"
            and bool(url.username)
            and bool(url.password)
            and not url.query
            and (url.port is None or 1 <= url.port <= 65535)
        )
    except (ArgumentError, TypeError, ValueError):
        raise ValueError(message) from None
    if not valid:
        raise ValueError(message)
    return url
