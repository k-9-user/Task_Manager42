"""Load every model into the shared metadata for the app and Alembic."""

from app.models.user import User
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.notification import Notification
from app.models.attachment import Attachment
from app.models.comment import Comment
from app.models.project_message import ProjectMessage
from app.models.api_key import ApiKey
from app.models.oauth_handoff import OAuthHandoff

__all__ = [
    "User",
    "Project",
    "ProjectMember",
    "Task",
    "Notification",
    "Attachment",
    "Comment",
    "ProjectMessage",
    "ApiKey",
    "OAuthHandoff",
]
