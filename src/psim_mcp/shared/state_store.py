"""Unified state management.

Manages shared state (preview tokens, design sessions, simulation results)
across services with TTL-based expiration.

This is an evolution of ``services.preview_store.PreviewStore`` into a
general-purpose key-value store while maintaining full backward compatibility.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


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
                self._delete_associated_files(entry.get("data", {}))
                return None
            return entry["data"]

    def delete(self, token: str) -> bool:
        """Delete entry by *token*.  Returns ``True`` if it existed.

        Also removes any associated on-disk files (e.g. SVG previews).
        """
        with self._lock:
            entry = self._store.pop(token, None)
            if entry is None:
                return False
            self._delete_associated_files(entry.get("data", {}))
            return True

    def cleanup_expired(self) -> int:
        """Remove all expired entries.  Returns the number removed."""
        return self._cleanup_expired()

    @staticmethod
    def _delete_associated_files(data: dict) -> None:
        """Remove on-disk files referenced by an expired store entry."""
        svg_path = data.get("svg_path") if isinstance(data, dict) else None
        if svg_path and isinstance(svg_path, str):
            try:
                if os.path.isfile(svg_path):
                    os.remove(svg_path)
                    logger.debug("Cleaned up expired SVG: %s", svg_path)
            except OSError:
                pass

    def _cleanup_expired(self) -> int:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, v in self._store.items() if now > v["expires_at"]]
            for k in expired:
                entry = self._store.pop(k)
                self._delete_associated_files(entry.get("data", {}))
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
