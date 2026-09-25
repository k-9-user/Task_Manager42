import math
import time
from threading import Lock

from fastapi import HTTPException, status

from app.auth.api_key_auth import hash_api_key


class ApiKeyRateLimiter:
    """Fixed window per API key, in memory: resets on restart, not shared between processes."""

    def __init__(self, max_requests: int = 60, window_seconds: float = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[float, int]] = {}
        self._lock = Lock()

    def check(self, api_key: str) -> None:
        """Count one request for this key, or raise HTTP 429 once its window is full."""

        key = hash_api_key(api_key)
        now = time.monotonic()
        with self._lock:
            self._windows = {
                other: window
                for other, window in self._windows.items()
                if now - window[0] < self.window_seconds
            }
            started, count = self._windows.get(key, (now, 0))
            if count >= self.max_requests:
                retry_after = max(1, math.ceil(started + self.window_seconds - now))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                    headers={"Retry-After": str(retry_after)},
                )
            self._windows[key] = (started, count + 1)
