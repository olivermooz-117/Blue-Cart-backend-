"""Small thread-safe in-memory TTL cache for search results."""

import threading
import time


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

    def set(self, key, value):
        with self._lock:
            if len(self._store) >= self.max_entries and key not in self._store:
                oldest = next(iter(self._store))
                self._store.pop(oldest)
            self._store[key] = {
                "value": value,
                "expires_at": time.time() + self.ttl,
            }

    def clear(self):
        with self._lock:
            self._store.clear()


search_cache = TTLCache(ttl_seconds=600, max_entries=200)


def cache_get(key):
    return search_cache.get(key)


def cache_set(key, value):
    return search_cache.set(key, value)


def cache_clear():
    return search_cache.clear()
