from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.api_key import ApiKey


def test_api_key_table_name():
    assert ApiKey.__tablename__ == "api_keys"


def test_api_key_columns():
    assert list(ApiKey.__table__.columns.keys()) == [
        "id",
        "user_id",
        "key",
        "created_at",
    ]


def test_api_key_id_column():
    column = ApiKey.__table__.c.id

    assert isinstance(column.type, UUID)
    assert column.primary_key is True
    assert column.default is not None


def test_api_key_user_id_column():
    column = ApiKey.__table__.c.user_id

    assert isinstance(column.type, UUID)
    assert column.nullable is False
    assert {foreign_key.target_fullname for foreign_key in column.foreign_keys} == {
        "users.id"
    }


def test_api_key_key_column():
    column = ApiKey.__table__.c.key

    assert isinstance(column.type, String)
    assert column.nullable is False
    assert column.unique is True


def test_api_key_created_at_column():
    column = ApiKey.__table__.c.created_at

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.server_default is not None
