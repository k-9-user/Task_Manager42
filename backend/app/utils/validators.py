from typing import Any
from urllib.parse import unquote, urlsplit


USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"
AVATAR_MAX_LENGTH = 2048
DISPLAY_NAME_MAX_LENGTH = 100
STATUS_REASON_MAX_LENGTH = 500


def has_control_characters(value: str) -> bool:
    """Return whether value contains a C0 or DEL control character."""

    return any(
        ord(character) < 0x20 or ord(character) == 0x7F for character in value
    )


def has_control_or_space_characters(value: str) -> bool:
    """Return whether value contains whitespace or a control character."""

    return any(character.isspace() for character in value) or has_control_characters(
        value
    )


def has_unsafe_url_characters(value: str) -> bool:
    """Return whether value cannot be trusted as a single-line URL or path."""

    return "\\" in value or has_control_or_space_characters(value)


def is_safe_https_url(value: str, *, allow_fragment: bool = True) -> bool:
    """Return whether value is an HTTPS URL with no credentials and a sane port."""

    try:
        parsed = urlsplit(value)
        parsed_port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.hostname is not None
        and parsed.username is None
        and parsed.password is None
        and (allow_fragment or not parsed.fragment)
        and (parsed_port is None or 1 <= parsed_port <= 65_535)
    )


def is_safe_root_relative_path(value: str) -> bool:
    """Return whether value is an absolute local path with no traversal."""

    parsed = urlsplit(value)
    return (
        not parsed.scheme
        and not parsed.netloc
        and value.startswith("/")
        and not value.startswith("//")
        and not parsed.query
        and not parsed.fragment
        and not {".", ".."}.intersection(unquote(parsed.path).split("/"))
    )


def normalize_email(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def validate_username(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_display_name(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    display_name = value.strip()
    if not display_name or has_control_characters(display_name):
        raise ValueError("display_name must contain printable characters")
    return display_name


def validate_status_reason(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    reason = value.strip()
    if not reason or has_control_characters(reason):
        raise ValueError("reason must contain printable characters")
    return reason


def validate_avatar(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    avatar = value.strip()
    if (
        not avatar
        or len(avatar) > AVATAR_MAX_LENGTH
        or has_unsafe_url_characters(avatar)
    ):
        raise ValueError("avatar must be a safe HTTPS URL or root-relative path")

    if not is_safe_https_url(avatar) and not is_safe_root_relative_path(avatar):
        raise ValueError("avatar must be a safe HTTPS URL or root-relative path")
    return avatar
