import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException, status


@dataclass(slots=True)
class _RateLimitWindow:
    request_count: int
    started_at: float


class ApiKeyRateLimiter:
    """A fixed-window, per-API-key limiter for the current project/demo.

    State is kept in memory, resets when the backend restarts, and is not shared
    across backend processes. A multi-instance production deployment would need
    shared state such as Redis.
    """

    def __init__(
        self,
        max_requests: int = 60,
        window_seconds: float = 60,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than zero")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than zero")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._records: dict[str, _RateLimitWindow] = {}
        self._lock = Lock()

    def check(self, api_key: str) -> None:
        """Record an allowed request or raise HTTP 429 when its limit is reached."""
        if not api_key:
            raise ValueError("api_key must not be empty")

        key_identifier = hashlib.sha256(api_key.encode("utf-8")).hexdigest()

        with self._lock:
            now = self._clock()
            self._cleanup_expired(now)
            window = self._records.get(key_identifier)

            if window is None:
                self._records[key_identifier] = _RateLimitWindow(
                    request_count=1,
                    started_at=now,
                )
                return

            if window.request_count >= self.max_requests:
                retry_after = max(
                    1,
                    math.ceil(
                        window.started_at + self.window_seconds - now,
                    ),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )

            window.request_count += 1

    def _cleanup_expired(self, now: float) -> None:
        expired_identifiers = [
            identifier
            for identifier, window in self._records.items()
            if now - window.started_at >= self.window_seconds
        ]
        for identifier in expired_identifiers:
            del self._records[identifier]
