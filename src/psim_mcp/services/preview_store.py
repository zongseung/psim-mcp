"""Token-based preview state management.

Replaces the global `_pending_preview` variable in tools/circuit.py
with a token-based store that supports multiple concurrent previews.
"""
import time
import uuid


class PreviewStore:
    """In-memory store for circuit preview states, keyed by token."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self, ttl: int = DEFAULT_TTL):
        self._store: dict[str, dict] = {}
        self._ttl = ttl

    def save(self, preview_data: dict) -> str:
        """Save preview data and return a unique token."""
        self._cleanup_expired()
        token = uuid.uuid4().hex[:12]
        self._store[token] = {
            "data": preview_data,
            "created_at": time.time(),
        }
        return token

    def get(self, token: str) -> dict | None:
        """Retrieve preview data by token. Returns None if expired or not found."""
        self._cleanup_expired()
        entry = self._store.get(token)
        if entry is None:
            return None
        if time.time() - entry["created_at"] > self._ttl:
            del self._store[token]
            return None
        return entry["data"]

    def delete(self, token: str) -> bool:
        """Delete a preview by token. Returns True if it existed."""
        return self._store.pop(token, None) is not None

    def _cleanup_expired(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v["created_at"] > self._ttl]
        for k in expired:
            del self._store[k]


# Module-level singleton
_default_store = PreviewStore()


def get_preview_store() -> PreviewStore:
    return _default_store
