"""Small per-client sliding-window rate limiter (no external dependencies).

Requests are grouped into buckets (expensive job submissions, model inference,
single searches, everything else). Each bucket allows ``limit`` requests per
``window`` seconds per client address. Behind a reverse proxy, start uvicorn
with ``--proxy-headers --forwarded-allow-ips=<proxy address>`` so the client
address is the visitor's address and not the proxy's.

Set KLINKPPI_RATE_LIMITS=off to disable (e.g. local development), or scale all
limits with KLINKPPI_RATE_LIMIT_SCALE (e.g. 2 doubles every limit).
"""
from __future__ import annotations

import math
import os
import re
import threading
from collections import deque
from time import monotonic

# (bucket, HTTP method, path regex). First match wins.
RULES = [
    ("embedding", "POST", re.compile(r"^/collection/jobs/[^/]+/embeddings$")),
    ("alignment", "POST", re.compile(r"^/collection/jobs/[^/]+/alignments$")),
    ("job", "POST", re.compile(r"^/collection/jobs(/[^/]+/(run|rerun))?$")),
    ("job", "POST", re.compile(r"^/species-ppi/jobs$")),
    ("search", "GET", re.compile(r"^/search$")),
    ("export", "POST", re.compile(r"^/(mitab|parquet)$|^/species-ppi/jobs/[^/]+/(mitab|parquet)$")),
    ("lookup", "GET", re.compile(r"^/collection/jobs/[^/]+/(shared-go|sequence)$")),
]
# bucket -> (requests, window seconds)
LIMITS = {
    "embedding": (10, 600),
    "alignment": (60, 600),
    "job": (30, 600),
    "search": (60, 600),
    "export": (60, 600),
    "lookup": (240, 600),
    "default": (1200, 60),
}
EXEMPT = {"/health"}


class RateLimiter:
    def __init__(self, limits=None, scale=None, enabled=None):
        if enabled is None:
            enabled = os.environ.get("KLINKPPI_RATE_LIMITS", "on").strip().lower() not in {"off", "0", "false", "no"}
        if scale is None:
            try:
                scale = float(os.environ.get("KLINKPPI_RATE_LIMIT_SCALE", "1"))
            except ValueError:
                scale = 1.0
        self.enabled = enabled
        self.limits = {name: (max(1, int(count * scale)), window) for name, (count, window) in (limits or LIMITS).items()}
        self._hits: dict[tuple[str, str], deque] = {}
        self._lock = threading.Lock()
        self._calls = 0

    @staticmethod
    def bucket(method: str, path: str) -> str:
        for name, rule_method, pattern in RULES:
            if method == rule_method and pattern.match(path):
                return name
        return "default"

    def check(self, client: str, method: str, path: str) -> tuple[bool, int, str]:
        """Record a request; return (allowed, retry_after_seconds, bucket)."""
        if not self.enabled or path in EXEMPT or method == "OPTIONS":
            return True, 0, ""
        name = self.bucket(method, path)
        limit, window = self.limits[name]
        now = monotonic()
        with self._lock:
            self._calls += 1
            if self._calls % 1000 == 0:
                self._prune(now)
            hits = self._hits.setdefault((client, name), deque())
            while hits and now - hits[0] >= window:
                hits.popleft()
            if len(hits) >= limit:
                return False, max(1, math.ceil(window - (now - hits[0]))), name
            hits.append(now)
        return True, 0, name

    def _prune(self, now):
        longest = max(window for _, window in self.limits.values())
        for key in [key for key, hits in self._hits.items() if not hits or now - hits[-1] >= longest]:
            del self._hits[key]

    def describe(self):
        return {name: {"requests": count, "window_seconds": window} for name, (count, window) in self.limits.items()}
