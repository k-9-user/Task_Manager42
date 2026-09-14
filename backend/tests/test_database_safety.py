import pytest

from tests.database_safety import validate_test_database_url


@pytest.mark.parametrize("host", ["test-db", "localhost", "127.0.0.1", "[::1]"])
def test_test_database_guard_accepts_dedicated_local_database(host):
    url = validate_test_database_url(
        f"postgresql://test-only:test-only@{host}:5432/taskmanager_test"
    )
    assert url.database == "taskmanager_test"


@pytest.mark.parametrize("value", [
    None,
    "",
    "not-a-url",
    "sqlite:///taskmanager_test",
    "postgresql://test-only:test-only@db/taskmanager_test",
    "postgresql://test-only:test-only@production.example/taskmanager_test",
    "postgresql://test-only:test-only@test-db/taskmanager",
    "postgresql://test-only:test-only@test-db/taskmanager_test_backup",
    "postgresql://test-db/taskmanager_test",
    "postgresql://test-only@test-db/taskmanager_test",
    "postgresql://test-only:test-only@test-db/taskmanager_test?host=db",
    "postgresql://test-only:test-only@test-db/taskmanager_test?options=-csearch_path=public",
])
def test_test_database_guard_rejects_unsafe_targets_without_echoing_credentials(value):
    with pytest.raises(ValueError) as error:
        validate_test_database_url(value)
    assert "test-only" not in str(error.value)
