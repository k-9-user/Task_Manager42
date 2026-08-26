from typing import Any
from urllib.parse import urlsplit


USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 50
USERNAME_PATTERN = r"^[A-Za-z0-9._-]+$"
AVATAR_MAX_LENGTH = 2048

def normalize_email(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().lower()
    return value


def validate_username(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return value.strip()


def validate_avatar(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    avatar = value.strip()
    if (
        not avatar
        or len(avatar) > AVATAR_MAX_LENGTH
        or "\\" in avatar
        or any(
            character.isspace()
            or ord(character) < 32
            or ord(character) == 127
            for character in avatar
        )
    ):
        raise ValueError("avatar must be a safe HTTPS URL or root-relative path")

    try:
        parsed = urlsplit(avatar)
        parsed_port = parsed.port
        is_https_url = (
            parsed.scheme == "https"
            and bool(parsed.netloc)
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
            and (parsed_port is None or 1 <= parsed_port <= 65_535)
        )
    except ValueError as exc:
        raise ValueError(
            "avatar must be a safe HTTPS URL or root-relative path"
        ) from exc

    is_root_relative = (
        not parsed.scheme
        and not parsed.netloc
        and avatar.startswith("/")
        and not avatar.startswith("//")
    )
    if not is_https_url and not is_root_relative:
        raise ValueError("avatar must be a safe HTTPS URL or root-relative path")
    return avatar
