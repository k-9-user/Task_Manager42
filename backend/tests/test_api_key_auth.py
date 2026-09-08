from inspect import signature
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.api_key_auth import (
    authenticate_api_key,
    generate_api_key,
    get_current_api_user,
)


def test_generate_api_key_returns_nonempty_string():
    api_key = generate_api_key()

    assert isinstance(api_key, str)
    assert api_key
    assert len(api_key) >= 32


def test_generate_api_key_returns_distinct_values():
    assert generate_api_key() != generate_api_key()


def test_authenticate_api_key_returns_matching_user():
    api_key = SimpleNamespace(user_id="user-id")
    expected_user = object()
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [api_key, expected_user]

    user = authenticate_api_key("valid-test-key", db)

    assert user is expected_user
    assert db.scalar.call_count == 2


def test_authenticate_api_key_rejects_unknown_key():
    raw_api_key = "super-secret-test-key"
    db = MagicMock(spec=Session)
    db.scalar.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        authenticate_api_key(raw_api_key, db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert raw_api_key not in str(exc_info.value.detail)
    db.scalar.assert_called_once()


def test_authenticate_api_key_rejects_orphaned_key():
    raw_api_key = "orphaned-secret-test-key"
    api_key = SimpleNamespace(user_id="missing-user-id")
    db = MagicMock(spec=Session)
    db.scalar.side_effect = [api_key, None]

    with pytest.raises(HTTPException) as exc_info:
        authenticate_api_key(raw_api_key, db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert raw_api_key not in str(exc_info.value.detail)
    assert db.scalar.call_count == 2


def test_authenticate_api_key_rejects_missing_key():
    db = MagicMock(spec=Session)

    with pytest.raises(HTTPException) as exc_info:
        authenticate_api_key(None, db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    db.scalar.assert_not_called()


def test_get_current_api_user_uses_x_api_key_header():
    parameter = signature(get_current_api_user).parameters["x_api_key"]

    assert parameter.default.alias == "X-API-Key"


def test_get_current_api_user_authenticates_header_value():
    raw_api_key = "valid-header-test-key"
    expected_user = object()
    db = MagicMock(spec=Session)

    with patch(
        "app.auth.api_key_auth.authenticate_api_key",
        return_value=expected_user,
    ) as authenticate:
        user = get_current_api_user(raw_api_key, db)

    assert user is expected_user
    authenticate.assert_called_once_with(raw_api_key, db)
