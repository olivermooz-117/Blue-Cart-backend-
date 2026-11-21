"""Search-result cache and per-IP rate limiter.

Backends:
- In-memory (default): simple dict, resets on restart — fine for a
  single-instance deployment.
- Redis: used when ``REDIS_URL`` is set; falls back to in-memory if the
  ``redis`` package isn't installed or Redis is unreachable.

Public interface (unchanged): ``cache_get(query)``, ``cache_set(query,
results)``, ``rate_limit_allowed(ip)``.
"""

import json
import logging
import os
import time
from collections import defaultdict

from config import Config

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(getattr(Config, "SEARCH_CACHE_TTL_SECONDS", 12 * 60))
RATE_LIMIT_REQUESTS = int(getattr(Config, "RATE_LIMIT_REQUESTS", 30))
RATE_LIMIT_WINDOW_SECONDS = int(getattr(Config, "RATE_LIMIT_WINDOW_SECONDS", 60))
REDIS_URL = os.environ.get("REDIS_URL") or getattr(Config, "REDIS_URL", None)

_CACHE_KEY_PREFIX = "bluecart:search_cache:"
_RATE_KEY_PREFIX = "bluecart:rate_limit:"


def _normalize_query(query):
    return " ".join(query.lower().split())


# ---------------------------------------------------------------------------
# In-memory backends (default)
# ---------------------------------------------------------------------------
class _InMemoryResultCache:
    def __init__(self, ttl_seconds):
        self.ttl = ttl_seconds
        self._store = {}

    def get(self, key):
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() > entry["expires_at"]:
            self._store.pop(key, None)
            return None
        return entry["results"]

    def set(self, key, results):
        self._store[key] = {
            "results": results,
            "expires_at": time.time() + self.ttl,
        }


class _InMemoryRateLimiter:
    def __init__(self, max_requests, window_seconds):
        self.max_requests = max_requests
        self.window = window_seconds
        self._log = defaultdict(list)

    def allowed(self, ip):
        now = time.time()
        window_start = now - self.window
        stamps = self._log[ip]
        self._log[ip] = [t for t in stamps if t > window_start]
        if len(self._log[ip]) >= self.max_requests:
            return False
        self._log[ip].append(now)
        return True


# ---------------------------------------------------------------------------
# Redis backends (optional, only when REDIS_URL is set)
# ---------------------------------------------------------------------------
class _RedisResultCache:
    def __init__(self, client, ttl_seconds):
        self.client = client
        self.ttl = ttl_seconds

    def _key(self, key):
        return f"{_CACHE_KEY_PREFIX}{key}"

    def get(self, key):
        raw = self.client.get(self._key(key))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (ValueError, TypeError):
            self.client.delete(self._key(key))
            return None

    def set(self, key, results):
        self.client.setex(self._key(key), self.ttl, json.dumps(results))


class _RedisRateLimiter:
    """Sliding-window rate limiter backed by a Redis sorted set per IP."""

    def __init__(self, client, max_requests, window_seconds):
        self.client = client
        self.max_requests = max_requests
        self.window = window_seconds

    def _key(self, ip):
        return f"{_RATE_KEY_PREFIX}{ip}"

    def allowed(self, ip):
        now = time.time()
        window_start = now - self.window
        key = self._key(ip)

        pipe = self.client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.expire(key, self.window)
        _, count, _ = pipe.execute()

        if count >= self.max_requests:
            return False

        pipe = self.client.pipeline()
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, self.window)
        pipe.execute()
        return True


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
def _build_result_cache():
    if not REDIS_URL:
        return _InMemoryResultCache(CACHE_TTL_SECONDS)
    try:
        import redis as redis_lib  # type: ignore
    except ImportError:
        logger.warning(
            "REDIS_URL is set but the 'redis' package is not installed; "
            "falling back to in-memory cache. (pip install redis)"
        )
        return _InMemoryResultCache(CACHE_TTL_SECONDS)
    try:
        client = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        logger.info("Using Redis search-result cache (%s)", REDIS_URL)
        return _RedisResultCache(client, CACHE_TTL_SECONDS)
    except Exception as exc:  # pragma: no cover - Redis may be down in dev
        logger.warning("Redis unavailable (%s); falling back to in-memory cache", exc)
        return _InMemoryResultCache(CACHE_TTL_SECONDS)


def _build_rate_limiter():
    if not REDIS_URL:
        return _InMemoryRateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)
    try:
        import redis as redis_lib  # type: ignore
    except ImportError:
        logger.warning(
            "REDIS_URL is set but the 'redis' package is not installed; "
            "falling back to in-memory rate limiter. (pip install redis)"
        )
        return _InMemoryRateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)
    try:
        client = redis_lib.Redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        logger.info("Using Redis rate limiter (%s)", REDIS_URL)
        return _RedisRateLimiter(
            client, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS
        )
    except Exception as exc:  # pragma: no cover - Redis may be down in dev
        logger.warning("Redis unavailable (%s); falling back to in-memory rate limiter", exc)
        return _InMemoryRateLimiter(RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW_SECONDS)


_result_cache = _build_result_cache()
_rate_limiter = _build_rate_limiter()


# ---------------------------------------------------------------------------
# Public interface (unchanged — routes/search.py calls these directly)
# ---------------------------------------------------------------------------
def cache_get(query):
    key = _normalize_query(query)
    return _result_cache.get(key)


def cache_set(query, results):
    key = _normalize_query(query)
    _result_cache.set(key, results)


def rate_limit_allowed(ip):
    return _rate_limiter.allowed(ip)
