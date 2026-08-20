import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException, status

from app.utils.rate_limiter import ApiKeyRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.current_time = 0.0

    def __call__(self) -> float:
        return self.current_time

    def advance(self, seconds: float) -> None:
        self.current_time += seconds


def test_rate_limiter_defaults():
    limiter = ApiKeyRateLimiter()

    assert limiter.max_requests == 60
    assert limiter.window_seconds == 60


def test_requests_up_to_limit_are_allowed():
    limiter = ApiKeyRateLimiter(max_requests=3, window_seconds=60)

    for _ in range(3):
        assert limiter.check("allowed-test-key") is None


def test_request_over_limit_is_rejected():
    raw_api_key = "rate-limited-secret-key"
    limiter = ApiKeyRateLimiter(max_requests=3, window_seconds=60)

    for _ in range(3):
        limiter.check(raw_api_key)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(raw_api_key)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert exc_info.value.detail == "Rate limit exceeded"
    assert raw_api_key not in str(exc_info.value.detail)


def test_api_keys_have_independent_limits():
    limiter = ApiKeyRateLimiter(max_requests=1, window_seconds=60)

    limiter.check("key-a")
    with pytest.raises(HTTPException):
        limiter.check("key-a")

    assert limiter.check("key-b") is None


def test_window_resets_after_expiration():
    clock = FakeClock()
    limiter = ApiKeyRateLimiter(
        max_requests=2,
        window_seconds=60,
        clock=clock,
    )

    limiter.check("reset-test-key")
    limiter.check("reset-test-key")
    clock.advance(61)

    assert limiter.check("reset-test-key") is None


def test_raw_api_key_is_not_stored():
    raw_api_key = "raw-secret-that-must-not-be-stored"
    identifier = hashlib.sha256(raw_api_key.encode("utf-8")).hexdigest()
    limiter = ApiKeyRateLimiter()

    limiter.check(raw_api_key)

    assert raw_api_key not in limiter._records
    assert identifier in limiter._records


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("max_requests", 0),
        ("max_requests", -1),
        ("window_seconds", 0),
        ("window_seconds", -1),
    ],
)
def test_invalid_configuration_is_rejected(parameter, value):
    with pytest.raises(ValueError):
        ApiKeyRateLimiter(**{parameter: value})


def test_empty_api_key_is_rejected():
    limiter = ApiKeyRateLimiter()

    with pytest.raises(ValueError):
        limiter.check("")


def test_retry_after_reports_remaining_window():
    clock = FakeClock()
    limiter = ApiKeyRateLimiter(
        max_requests=1,
        window_seconds=60,
        clock=clock,
    )
    limiter.check("retry-after-test-key")
    clock.advance(15)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check("retry-after-test-key")

    assert exc_info.value.headers == {"Retry-After": "45"}


def test_expired_records_are_removed_during_checks():
    clock = FakeClock()
    stale_api_key = "stale-test-key"
    stale_identifier = hashlib.sha256(stale_api_key.encode("utf-8")).hexdigest()
    limiter = ApiKeyRateLimiter(window_seconds=60, clock=clock)
    limiter.check(stale_api_key)
    clock.advance(61)

    limiter.check("active-test-key")

    assert stale_identifier not in limiter._records


def test_concurrent_requests_share_one_protected_counter():
    limiter = ApiKeyRateLimiter(max_requests=25, window_seconds=60)

    def attempt_request(_: int) -> bool:
        try:
            limiter.check("concurrent-test-key")
        except HTTPException as exc:
            assert exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            return False
        return True

    with ThreadPoolExecutor(max_workers=8) as executor:
        outcomes = list(executor.map(attempt_request, range(100)))

    assert sum(outcomes) == 25
