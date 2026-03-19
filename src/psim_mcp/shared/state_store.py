"""Unified state management.

Manages shared state (preview tokens, design sessions, simulation results)
across services with TTL-based expiration.

This is an evolution of ``services.preview_store.PreviewStore`` into a
general-purpose key-value store while maintaining full backward compatibility.
"""

from __future__ import annotations

import secrets
import threading
import time
from typing import Any


class StateStore:
    """TTL-based in-memory state store.

    Thread-safe key-value store with automatic expiration.
    Replaces and extends the original ``PreviewStore``.
    """

    def __init__(self, default_ttl: int = 3600, *, ttl: int | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        # Accept ``ttl`` keyword for backward compat with PreviewStore(ttl=N).
        self._default_ttl = ttl if ttl is not None else default_ttl
        self._lock = threading.Lock()

    def save(self, data: dict, ttl: int | None = None, key: str | None = None) -> str:
        """Save *data* and return a unique token.

        Parameters
        ----------
        data:
            Arbitrary dict to store.
        ttl:
            Time-to-live in seconds.  Defaults to the store's default TTL.
        key:
            Optional explicit key.  When *None* a random hex token is generated.
        """
        self._cleanup_expired()
        token = key or secrets.token_hex(6)
        with self._lock:
            self._store[token] = {
                "data": data,
                "expires_at": time.monotonic() + (ttl or self._default_ttl),
            }
        return token

    def get(self, token: str) -> dict | None:
        """Retrieve data by *token*.  Returns ``None`` if expired or missing."""
        with self._lock:
            entry = self._store.get(token)
            if entry is None:
                return None
            if time.monotonic() > entry["expires_at"]:
                del self._store[token]
                return None
            return entry["data"]

    def delete(self, token: str) -> bool:
        """Delete entry by *token*.  Returns ``True`` if it existed."""
        with self._lock:
            return self._store.pop(token, None) is not None

    def cleanup_expired(self) -> int:
        """Remove all expired entries.  Returns the number removed."""
        return self._cleanup_expired()

    def _cleanup_expired(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._store.items() if now > v["expires_at"]]
            for k in expired:
                del self._store[k]
            return len(expired)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_default_store: StateStore | None = None


def get_state_store(ttl: int = 3600) -> StateStore:
    """Return the default :class:`StateStore` singleton."""
    global _default_store
    if _default_store is None:
        _default_store = StateStore(default_ttl=ttl)
    return _default_store
