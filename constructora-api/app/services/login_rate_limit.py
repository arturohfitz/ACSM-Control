from time import monotonic

from fastapi import HTTPException, status

from app.core.config import settings


_attempts: dict[str, tuple[int, float, float]] = {}


def _purge(now: float) -> None:
    expired = [
        key
        for key, (_, first_seen, locked_until) in _attempts.items()
        if locked_until <= now and now - first_seen > settings.login_window_seconds
    ]
    for key in expired:
        _attempts.pop(key, None)


def assert_login_allowed(key: str) -> None:
    now = monotonic()
    _purge(now)
    entry = _attempts.get(key)
    if entry is None:
        return
    _, _, locked_until = entry
    if locked_until > now:
        remaining = max(1, int(locked_until - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Demasiados intentos fallidos. Intenta de nuevo en {remaining} segundos.",
        )


def register_login_failure(key: str) -> None:
    now = monotonic()
    _purge(now)
    attempts, first_seen, locked_until = _attempts.get(key, (0, now, 0.0))
    if now - first_seen > settings.login_window_seconds:
        attempts, first_seen, locked_until = 0, now, 0.0
    attempts += 1
    if attempts >= settings.login_max_attempts:
        locked_until = now + settings.login_lock_seconds
    _attempts[key] = (attempts, first_seen, locked_until)


def register_login_success(key: str) -> None:
    _attempts.pop(key, None)
