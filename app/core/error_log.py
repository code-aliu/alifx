"""
Lightweight in-memory error log — captures the last 100 unhandled 500s.
No DB required. Resets on service restart (acceptable for an operational tool).
"""
from collections import deque
from datetime import datetime

_errors: deque[dict] = deque(maxlen=100)


def log_error(route: str, method: str, error: str, status: int = 500) -> None:
    _errors.appendleft({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "route": route,
        "method": method,
        "error": str(error)[:300],
        "status": status,
    })


def get_recent_errors(limit: int = 20) -> list[dict]:
    return list(_errors)[:limit]


def clear_errors() -> None:
    _errors.clear()
