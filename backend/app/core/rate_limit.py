"""Rate limiting por ventana fija respaldado en Redis (en memoria para los tests)."""

from __future__ import annotations

import contextlib
import threading
import time
from typing import Protocol

import redis

from .config import get_settings
from .errors import RateLimitedError
from .logging import log


class _Store(Protocol):
    def hit(self, key: str, window_s: int) -> int: ...
    def reset(self, key: str) -> None: ...


class RedisStore:
    def __init__(self, url: str) -> None:
        self.r = redis.Redis.from_url(url, socket_timeout=2, socket_connect_timeout=2)

    def hit(self, key: str, window_s: int) -> int:
        pipe = self.r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_s, nx=True)
        count, _ = pipe.execute()
        return int(count)

    def reset(self, key: str) -> None:
        self.r.delete(key)


class MemoryStore:
    def __init__(self) -> None:
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, window_s: int) -> int:
        now = time.monotonic()
        with self._lock:
            count, exp = self._data.get(key, (0, now + window_s))
            if now > exp:
                count, exp = 0, now + window_s
            self._data[key] = (count + 1, exp)
            return count + 1

    def reset(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class RateLimiter:
    def __init__(self, store: _Store) -> None:
        self.store = store

    def check(self, bucket: str, identity: str, limit: int, window_s: int) -> None:
        key = f"rl:{bucket}:{identity}"
        try:
            count = self.store.hit(key, window_s)
        except redis.RedisError:
            # Para los buckets de autenticación fallamos cerrado, para el resto abierto.
            log.warning("rate_limit_store_unavailable", bucket=bucket)
            if bucket.startswith("auth"):
                raise RateLimitedError("Servicio temporalmente no disponible, inténtalo en un momento.") from None
            return
        if count > limit:
            raise RateLimitedError("Demasiadas solicitudes. Espera un momento antes de volver a intentarlo.")

    def reset(self, bucket: str, identity: str) -> None:
        with contextlib.suppress(redis.RedisError):
            self.store.reset(f"rl:{bucket}:{identity}")


_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        s = get_settings()
        _limiter = RateLimiter(MemoryStore() if s.environment == "test" else RedisStore(s.redis_url))
    return _limiter
