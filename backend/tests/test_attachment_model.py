from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from app.models.attachment import Attachment


def test_attachment_table_name():
    assert Attachment.__tablename__ == "attachments"


def test_attachment_columns():
    assert list(Attachment.__table__.columns.keys()) == [
        "id",
        "task_id",
        "file_url",
        "file_name",
        "uploaded_by",
        "created_at",
    ]


def test_attachment_id_column():
    column = Attachment.__table__.c.id

    assert isinstance(column.type, UUID)
    assert column.primary_key is True
    assert column.default is not None


def test_attachment_task_id_column():
    column = Attachment.__table__.c.task_id

    assert isinstance(column.type, UUID)
    assert column.nullable is False
    assert {foreign_key.target_fullname for foreign_key in column.foreign_keys} == {
        "tasks.id"
    }


def test_attachment_file_url_column():
    column = Attachment.__table__.c.file_url

    assert isinstance(column.type, String)
    assert column.nullable is False


def test_attachment_file_name_column():
    column = Attachment.__table__.c.file_name

    assert isinstance(column.type, String)
    assert column.nullable is False


def test_attachment_uploaded_by_column():
    column = Attachment.__table__.c.uploaded_by

    assert isinstance(column.type, UUID)
    assert column.nullable is False
    assert {foreign_key.target_fullname for foreign_key in column.foreign_keys} == {
        "users.id"
    }


def test_attachment_created_at_column():
    column = Attachment.__table__.c.created_at

    assert isinstance(column.type, DateTime)
    assert column.type.timezone is True
    assert column.nullable is False
    assert column.server_default is not None
