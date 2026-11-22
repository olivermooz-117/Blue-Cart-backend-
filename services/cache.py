"""Search-result cache with optional Redis and a thread-safe memory fallback."""

import json
import logging
import threading
import time

from flask import current_app, has_app_context

from config import Config

logger = logging.getLogger(__name__)


class TTLCache:
    def __init__(self, ttl_seconds=600, max_entries=200):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                self._store.pop(key, None)
                return None
            return entry["value"]

    def set(self, key, value, ttl_seconds=None):
        with self._lock:
            if len(self._store) >= self.max_entries and key not in self._store:
                oldest = next(iter(self._store))
                self._store.pop(oldest)
            self._store[key] = {
                "value": value,
                "expires_at": time.time() + (
                    self.ttl if ttl_seconds is None else ttl_seconds
                ),
            }

    def clear(self):
        with self._lock:
            self._store.clear()


class SearchCache:
    key_prefix = "bluecart:search:"

    def __init__(self, max_entries=200):
        self._memory = TTLCache(max_entries=max_entries)
        self._clients = {}
        self._lock = threading.Lock()

    @staticmethod
    def _settings():
        if has_app_context():
            config = current_app.config
            ttl = config.get(
                "SEARCH_CACHE_TTL_SECONDS", Config.SEARCH_CACHE_TTL_SECONDS
            )
            redis_url = config.get("REDIS_URL", "")
        else:
            ttl = Config.SEARCH_CACHE_TTL_SECONDS
            redis_url = Config.REDIS_URL
        try:
            ttl = max(0, int(ttl))
        except (TypeError, ValueError):
            logger.warning("Invalid SEARCH_CACHE_TTL_SECONDS; using the default")
            ttl = Config.SEARCH_CACHE_TTL_SECONDS
        return ttl, redis_url

    def _redis_client(self, redis_url):
        if not redis_url:
            return None, None

        try:
            import redis
        except ImportError:
            logger.warning("REDIS_URL is configured but the redis package is unavailable")
            return None, None

        with self._lock:
            client = self._clients.get(redis_url)
            if client is None:
                try:
                    client = redis.Redis.from_url(
                        redis_url,
                        decode_responses=True,
                        socket_connect_timeout=0.25,
                        socket_timeout=0.25,
                    )
                except (redis.exceptions.RedisError, TypeError, ValueError) as exc:
                    logger.warning("Redis cache setup failed; using memory: %s", exc)
                    return None, redis
                self._clients[redis_url] = client
        return client, redis

    def get(self, key):
        _, redis_url = self._settings()
        client, redis = self._redis_client(redis_url)
        redis_key = self.key_prefix + key
        if client is not None:
            try:
                value = client.get(redis_key)
                if value is not None:
                    return json.loads(value)
            except (redis.exceptions.RedisError, json.JSONDecodeError, TypeError, ValueError) as exc:
                logger.warning("Redis cache read failed; using memory: %s", exc)
        return self._memory.get(key)

    def set(self, key, value):
        ttl, redis_url = self._settings()
        self._memory.set(key, value, ttl_seconds=ttl)
        client, redis = self._redis_client(redis_url)
        if client is None or ttl <= 0:
            return
        try:
            client.setex(self.key_prefix + key, ttl, json.dumps(value))
        except (redis.exceptions.RedisError, TypeError, ValueError) as exc:
            logger.warning("Redis cache write failed; using memory: %s", exc)

    def clear(self):
        self._memory.clear()


search_cache = SearchCache(max_entries=200)


def cache_get(key):
    return search_cache.get(key)


def cache_set(key, value):
    return search_cache.set(key, value)


def cache_clear():
    return search_cache.clear()
