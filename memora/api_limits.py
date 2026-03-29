"""
API request limits and pagination safeguards for Memora.

Centralised constants and helpers used by both the Flask app and
Vercel serverless handlers to enforce consistent limits.
"""

import time
from collections import defaultdict

# ── Pagination ──
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 25
MAX_OFFSET = 10_000

# ── Search ──
MAX_QUERY_LENGTH = 200
MAX_SEARCH_RESULTS = 50

# ── Request body ──
MAX_REQUEST_BYTES = 1_048_576  # 1 MB

# ── Rate limiting (in-memory, per-process) ──
RATE_LIMIT_WINDOW = 60        # seconds
RATE_LIMIT_MAX = 120           # requests per window per IP


def parse_limit(raw, default: int = DEFAULT_PAGE_SIZE) -> int:
    """Clamp a user-supplied limit to [1, MAX_PAGE_SIZE]."""
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return default
    return max(1, min(val, MAX_PAGE_SIZE))


def parse_offset(raw) -> int:
    """Clamp a user-supplied offset to [0, MAX_OFFSET]."""
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(val, MAX_OFFSET))


def paginated(results: list, limit: int, offset: int) -> dict:
    """Wrap a result list in a pagination metadata envelope."""
    return {
        "results": results,
        "limit": limit,
        "offset": offset,
        "count": len(results),
    }


# ── In-memory rate limiter ──

class RateLimiter:
    """Simple sliding-window rate limiter keyed by IP address."""

    def __init__(self, max_requests: int = RATE_LIMIT_MAX, window: int = RATE_LIMIT_WINDOW):
        self.max_requests = max_requests
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window
        hits = self._hits[key]
        # Prune old entries
        self._hits[key] = hits = [t for t in hits if t > cutoff]
        if len(hits) >= self.max_requests:
            return False
        hits.append(now)
        return True

    def remaining(self, key: str) -> int:
        now = time.time()
        cutoff = now - self.window
        hits = [t for t in self._hits[key] if t > cutoff]
        return max(0, self.max_requests - len(hits))
