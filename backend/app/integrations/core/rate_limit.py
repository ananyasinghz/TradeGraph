"""Simple token-bucket style rate limit placeholder for providers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """In-process limiter; replace with Redis-backed limiter for multi-worker."""

    max_calls: int = 60
    period_seconds: float = 60.0
    _timestamps: list[float] = field(default_factory=list)

    def allow(self) -> bool:
        now = time.monotonic()
        cutoff = now - self.period_seconds
        self._timestamps = [t for t in self._timestamps if t >= cutoff]
        if len(self._timestamps) >= self.max_calls:
            return False
        self._timestamps.append(now)
        return True

    def wait_seconds(self) -> float:
        if self.allow():
            return 0.0
        if not self._timestamps:
            return 0.0
        oldest = self._timestamps[0]
        return max(0.0, self.period_seconds - (time.monotonic() - oldest))
